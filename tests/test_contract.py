"""Garante que o schema JSON e os modelos Pydantic nunca divergem."""
import json

import pytest
from pydantic import ValidationError

from pipeline.config import settings
from pipeline.models import (
    Classification,
    PerpetratorType,
    ReportNature,
    TargetType,
    ViolenceType,
)

VALID = {
    "is_political_violence": True,
    "violence_type": "ameaca",
    "report_nature": "relato_primeira_mao",
    "target_type": "eleitor",
    "perpetrator_type": "indeterminado",
    "vinculo_eleitoral": True,
    "country": "BR",
    "city_mentioned": "Caxias",
    "uf_mentioned": "MA",
    "confidence": 0.9,
    "rationale": "Ameaça relatada pelo próprio autor.",
}

NEGATIVE = {
    **VALID,
    "is_political_violence": False,
    "violence_type": "nenhum",
    "target_type": "nenhum",
    "perpetrator_type": "nenhum",
    "report_nature": "opiniao_ou_ironia",
    "vinculo_eleitoral": False,
}


def load_schema() -> dict:
    return json.loads(settings.schema_path.read_text(encoding="utf-8"))


def test_valid_payload_parses():
    assert Classification.model_validate(VALID).violence_type is ViolenceType.AMEACA


@pytest.mark.parametrize(
    "field,bad",
    [("violence_type", "xingamento"), ("confidence", 1.5), ("uf_mentioned", "maranhao")],
)
def test_invalid_payloads_rejected(field, bad):
    with pytest.raises(ValidationError):
        Classification.model_validate({**VALID, field: bad})


@pytest.mark.parametrize(
    "field,enum",
    [
        ("violence_type", ViolenceType),
        ("report_nature", ReportNature),
        ("target_type", TargetType),
        ("perpetrator_type", PerpetratorType),
    ],
)
def test_schema_enums_match_models(field, enum):
    schema_values = set(load_schema()["properties"][field]["enum"])
    assert schema_values == {e.value for e in enum}


def test_schema_required_matches_model_fields():
    assert set(load_schema()["required"]) == set(Classification.model_fields)


@pytest.mark.parametrize(
    "enum", [ViolenceType, ReportNature, TargetType, PerpetratorType]
)
def test_prompt_mentions_every_enum_value(enum):
    """O prompt tem de listar todos os valores: o LLM não vê o schema JSON."""
    prompt = settings.prompt_path.read_text(encoding="utf-8")
    for value in (e.value for e in enum):
        assert value in prompt, f"{enum.__name__}.{value} ausente do prompt"


def test_negative_payload_parses():
    assert Classification.model_validate(NEGATIVE).label_code() == 0


@pytest.mark.parametrize(
    "override,reason",
    [
        # O bug que o schema v1 aceitava: tipo preenchido com o total negativo.
        ({"violence_type": "ameaca"}, "tipo sem violência"),
        ({"target_type": "candidato"}, "alvo sem violência"),
        ({"perpetrator_type": "apoiador"}, "autor sem violência"),
    ],
)
def test_negative_rejects_filled_fields(override, reason):
    with pytest.raises(ValidationError):
        Classification.model_validate({**NEGATIVE, **override})


@pytest.mark.parametrize(
    "override,reason",
    [
        ({"violence_type": "nenhum"}, "violência sem tipo"),
        ({"target_type": "nenhum"}, "violência sem alvo"),
        ({"perpetrator_type": "nenhum"}, "violência sem autor"),
        (
            {"violence_type": "interferencia_estrangeira", "perpetrator_type": "apoiador"},
            "interferência sem Estado estrangeiro",
        ),
    ],
)
def test_positive_rejects_empty_fields(override, reason):
    with pytest.raises(ValidationError):
        Classification.model_validate({**VALID, **override})


@pytest.mark.parametrize(
    "override,code",
    [
        ({}, 1),
        ({"country": "AR"}, 2),
        ({"violence_type": "ofensa"}, 3),
        # País estrangeiro vence a ofensa: a camada de fora do Brasil é uma só.
        ({"violence_type": "ofensa", "country": "US"}, 2),
    ],
)
def test_label_code(override, code):
    assert Classification.model_validate({**VALID, **override}).label_code() == code


def test_agente_politico_is_accepted_as_perpetrator():
    """Régua de 11/11: o cargo de quem comete basta, e a vítima pode não ter papel político.

    O caso que motivou a regra ("senador teria agredido mulher em hospital") precisa ser
    representável: alvo `indeterminado` com autor `agente_politico`.
    """
    item = Classification.model_validate(
        {
            **VALID,
            "violence_type": "agressao_fisica",
            "target_type": "indeterminado",
            "perpetrator_type": "agente_politico",
            "vinculo_eleitoral": False,
        }
    )
    assert item.perpetrator_type is PerpetratorType.AGENTE_POLITICO
    assert item.label_code() == 1


def test_agente_politico_still_requires_violence():
    """O valor novo não abre exceção na coerência: autor preenchido exige violência."""
    with pytest.raises(ValidationError):
        Classification.model_validate({**NEGATIVE, "perpetrator_type": "agente_politico"})


def test_platform_interference_is_code_1_with_its_own_type():
    """Decisão de 12/11: plataforma conta, mas como tipo próprio, para o mapa poder separar a camada."""
    item = Classification.model_validate(
        {
            **VALID,
            "violence_type": "interferencia_plataforma",
            "target_type": "instituicao",
            "perpetrator_type": "plataforma",
        }
    )
    assert item.label_code() == 1


@pytest.mark.parametrize(
    "violence_type,perpetrator_type",
    [
        ("interferencia_plataforma", "estado_estrangeiro"),  # Estado não é plataforma
        ("interferencia_estrangeira", "plataforma"),  # e plataforma não é Estado
    ],
)
def test_the_two_interference_types_do_not_mix(violence_type, perpetrator_type):
    """Sem isso, a camada de plataforma vazaria para a série principal pela porta do Estado."""
    with pytest.raises(ValidationError):
        Classification.model_validate(
            {**VALID, "violence_type": violence_type, "perpetrator_type": perpetrator_type}
        )
