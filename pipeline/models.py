"""Modelos de dados. `Classification` espelha schemas/classification.schema.json."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ViolenceType(str, Enum):
    AMEACA = "ameaca"
    OFENSA = "ofensa"
    AGRESSAO_FISICA = "agressao_fisica"
    ATENTADO = "atentado"
    HOMICIDIO = "homicidio"
    VIOLENCIA_DE_GENERO = "violencia_de_genero"
    INTIMIDACAO_INSTITUCIONAL = "intimidacao_institucional"
    OUTRO = "outro"
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
    INSTITUICAO = "instituicao"
    INDETERMINADO = "indeterminado"
    NENHUM = "nenhum"


class Classification(BaseModel):
    is_political_violence: bool
    violence_type: ViolenceType
    report_nature: ReportNature
    target_type: TargetType
    city_mentioned: str | None = None
    uf_mentioned: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(max_length=280)


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
