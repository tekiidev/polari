"""Garante que o schema JSON e os modelos Pydantic nunca divergem."""
import json

import pytest
from pydantic import ValidationError

from pipeline.config import settings
from pipeline.models import Classification, ReportNature, TargetType, ViolenceType

VALID = {
    "is_political_violence": True,
    "violence_type": "ameaca",
    "report_nature": "relato_primeira_mao",
    "target_type": "eleitor",
    "city_mentioned": "Caxias",
    "uf_mentioned": "MA",
    "confidence": 0.9,
    "rationale": "Ameaça relatada pelo próprio autor.",
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
    ],
)
def test_schema_enums_match_models(field, enum):
    schema_values = set(load_schema()["properties"][field]["enum"])
    assert schema_values == {e.value for e in enum}


def test_schema_required_matches_model_fields():
    assert set(load_schema()["required"]) == set(Classification.model_fields)


def test_prompt_mentions_every_enum_value():
    prompt = settings.prompt_path.read_text(encoding="utf-8")
    for value in (e.value for e in ReportNature):
        assert value in prompt
