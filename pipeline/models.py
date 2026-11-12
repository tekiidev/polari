"""Modelos de dados. `Classification` espelha schemas/classification.schema.json."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ViolenceType(str, Enum):
    AMEACA = "ameaca"
    OFENSA = "ofensa"
    AGRESSAO_FISICA = "agressao_fisica"
    ATENTADO = "atentado"
    HOMICIDIO = "homicidio"
    VIOLENCIA_DE_GENERO = "violencia_de_genero"
    INTIMIDACAO_INSTITUCIONAL = "intimidacao_institucional"
    # Interferência de Estado estrangeiro na política brasileira (guia, decisão de 07/11). Tipo
    # próprio porque não é violência contra pessoa: a série precisa poder separá-la.
    INTERFERENCIA_ESTRANGEIRA = "interferencia_estrangeira"
    # Plataforma ou empresa de tecnologia interferindo nas eleições (decisão de 12/11). Tipo
    # separado da interferência de Estado porque o mapa padrão o mostra como camada, não na
    # série principal: uma campanha de pressão copiada e colada viraria pico no mapa.
    INTERFERENCIA_PLATAFORMA = "interferencia_plataforma"
    OUTRO = "outro"
    NENHUM = "nenhum"


class PerpetratorType(str, Enum):
    """Quem cometeu, por função — nunca por lado político (LGPD, e inferência frágil).

    Sem isso, "apoiador agrediu adversário" e "polícia reprimiu ato" caem na mesma contagem.
    """

    APOIADOR = "apoiador"
    AGENTE_DO_ESTADO = "agente_do_estado"
    # Ocupante de cargo eletivo ou dirigente partidário agindo por conta própria (decisão de
    # 11/11): valor separado de `agente_do_estado` porque "senador agrediu alguém" e "PM reprimiu
    # ato" entram na série pelo mesmo critério e a agregação precisa poder distingui-los.
    AGENTE_POLITICO = "agente_politico"
    ESTADO_ESTRANGEIRO = "estado_estrangeiro"
    PLATAFORMA = "plataforma"
    INDETERMINADO = "indeterminado"
    NENHUM = "nenhum"


class ReportNature(str, Enum):
    PRIMEIRA_MAO = "relato_primeira_mao"
    TERCEIROS = "relato_terceiros"
    NOTICIA_COMPARTILHADA = "noticia_compartilhada"
    OPINIAO_OU_IRONIA = "opiniao_ou_ironia"
    BOATO = "boato_nao_verificado"
    INCITACAO = "incitacao"
    INDETERMINADO = "indeterminado"


class TargetType(str, Enum):
    CANDIDATO = "candidato"
    ELEITOR = "eleitor"
    AGENTE_PUBLICO = "agente_publico"
    JORNALISTA = "jornalista"
    APOIADOR = "apoiador"
    # Quem está em ato político sem papel partidário: o caso da repressão policial a manifestação,
    # que o guia inclui e o schema não distinguia de "eleitor".
    MANIFESTANTE = "manifestante"
    LIDERANCA_SOCIAL = "lideranca_social"
    INSTITUICAO = "instituicao"
    INDETERMINADO = "indeterminado"
    NENHUM = "nenhum"


class Classification(BaseModel):
    is_political_violence: bool
    violence_type: ViolenceType
    report_nature: ReportNature
    target_type: TargetType
    perpetrator_type: PerpetratorType
    # Sim só se o próprio texto cita eleição, campanha, candidatura, urna ou voto. Serve para medir
    # que parte do discurso é explicitamente eleitoral em cada período; não é critério de escopo
    # (exigir vínculo eleitoral zeraria a linha de base por definição).
    vinculo_eleitoral: bool
    # País do fato, ISO 3166-1 alfa-2, "BR" quando o texto não identifica outro (guia: "sem país
    # identificável no texto, considere Brasil"). Separa o código 1 do 2 sem precisar do LLM
    # escolher o código.
    country: str = Field(default="BR", pattern=r"^[A-Z]{2}$")
    city_mentioned: str | None = None
    uf_mentioned: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(max_length=280)

    @model_validator(mode="after")
    def check_coherence(self) -> Classification:
        """Barra combinações que o schema aceitava e que corrompem a contagem.

        O LLM erra essas combinações com frequência, e um `violence_type` preenchido junto de
        `is_political_violence = false` entraria na agregação por tipo sem entrar no total.
        """
        if self.is_political_violence:
            if self.violence_type is ViolenceType.NENHUM:
                raise ValueError("is_political_violence=true exige violence_type != 'nenhum'")
            if self.target_type is TargetType.NENHUM:
                raise ValueError("is_political_violence=true exige target_type != 'nenhum'")
            # Autor desconhecido é `indeterminado`, não `nenhum`: senão a agregação por autor não
            # distingue "o texto não diz" de "não houve violência".
            if self.perpetrator_type is PerpetratorType.NENHUM:
                raise ValueError(
                    "is_political_violence=true exige perpetrator_type != 'nenhum'"
                    " (use 'indeterminado' quando o texto não disser)"
                )
        else:
            if self.violence_type is not ViolenceType.NENHUM:
                raise ValueError("is_political_violence=false exige violence_type='nenhum'")
            if self.target_type is not TargetType.NENHUM:
                raise ValueError("is_political_violence=false exige target_type='nenhum'")
            if self.perpetrator_type is not PerpetratorType.NENHUM:
                raise ValueError("is_political_violence=false exige perpetrator_type='nenhum'")
        if self.violence_type is ViolenceType.INTERFERENCIA_ESTRANGEIRA:
            if self.perpetrator_type is not PerpetratorType.ESTADO_ESTRANGEIRO:
                raise ValueError(
                    "interferencia_estrangeira exige perpetrator_type='estado_estrangeiro'"
                )
        if self.violence_type is ViolenceType.INTERFERENCIA_PLATAFORMA:
            if self.perpetrator_type is not PerpetratorType.PLATAFORMA:
                raise ValueError("interferencia_plataforma exige perpetrator_type='plataforma'")
        return self

    def label_code(self) -> int:
        """Código 0–3 do guia de rotulagem, derivado dos campos por regra única.

        O modelo nunca escolhe o código: ele descreve o fato e o código sai daqui, para que a
        régua do gabarito e a do classificador sejam a mesma linha de código.
        """
        if not self.is_political_violence:
            return 0
        if self.country != "BR":
            return 2
        if self.violence_type is ViolenceType.OFENSA:
            return 3
        return 1


class RawItem(BaseModel):
    """Item coletado. Nunca guardamos handle/perfil do autor.

    `item_id` é o hash de `pipeline.privacy.item_id`. `source_ref` (URI/URL original) pode conter o
    DID do autor: fica fora de `model_dump()` e só o RawStore o grava, criptografado.
    """

    source: str  # "bluesky" | "rss" | "gdelt" | ...
    item_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    text: str
    created_at: datetime
    lang: str | None = None
    # Consultas que trouxeram o item: proveniência para medir o recall por família de consulta.
    queries: list[str] = Field(default_factory=list)
    source_ref: str | None = Field(default=None, exclude=True, repr=False)


class ProcessedItem(BaseModel):
    item: RawItem
    classification: Classification
    ibge_code: str | None = None
    # Rastreabilidade: nunca misture versões diferentes na mesma série temporal.
    model_id: str
    prompt_version: str
    classified_at: datetime
