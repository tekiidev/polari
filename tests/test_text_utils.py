from pipeline.classify.prefilter import matches_prefilter
from pipeline.geocode.ibge import normalize


def test_normalize_removes_accents_and_punctuation():
    assert normalize("São Luís ") == "sao luis"
    assert normalize("Santa Bárbara d'Oeste") == "santa barbara d oeste"


def test_prefilter_requires_violence_and_context():
    assert matches_prefilter("Eleitor foi agredido na saída da urna")
    assert not matches_prefilter("Hoje o tempo está agradável")
    assert not matches_prefilter("Houve uma agressão no trânsito")
