"""Recall do pré-filtro medido pelos itens barrados do gabarito.

O que estes testes protegem é a **ponderação**. Contar 78 positivos aprovados contra 5 barrados dá
94% de recall; ponderando pela população de cada estrato, dá 36%. A diferença não é detalhe de
estatística: é a diferença entre publicar "o filtro pega quase tudo" e "o filtro perde dois terços".
"""
import csv

import pytest

from eval import prefilter_recall as pr


@pytest.fixture
def fake_data(monkeypatch, tmp_path):
    """Dois estratos com taxas de amostragem muito diferentes, como nos dados reais."""
    population = tmp_path / "pop.csv"
    with population.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["period", "status", "n"])
        w.writerow(["baseline", "aprovado", 1_000])
        w.writerow(["baseline", "barrado", 99_000])
    monkeypatch.setattr(pr, "POPULATION", population)

    strata = tmp_path / "strata.csv"
    with strata.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "period", "prefilter_status"])
        for n in range(10):
            w.writerow([f"ap{n}", "baseline", "aprovado"])
        for n in range(10):
            w.writerow([f"ba{n}", "baseline", "barrado"])
    monkeypatch.setattr(pr, "STRATA", strata)

    # 8 de 10 aprovados são positivos; 1 de 10 barrados é positivo.
    rows = [{"item_id": f"ap{n}", "label": 1 if n < 8 else 0, "text": "t"} for n in range(10)]
    rows += [{"item_id": f"ba{n}", "label": 1 if n < 1 else 0, "text": "t"} for n in range(10)]
    monkeypatch.setattr(pr, "read_gold", lambda: rows)
    return rows


def test_recall_is_weighted_by_population(fake_data):
    """Sem ponderar: 8/(8+1) = 89%. Ponderando: 800 contra 9.900 positivos = 7,5%."""
    labels = pr.labels_by_stratum({1})
    assert labels[("baseline", "aprovado")] == (8, 10)
    assert labels[("baseline", "barrado")] == (1, 10)

    est = pr.estimate(pr.read_population(), labels)
    assert est["recall"] == pytest.approx(0.075, abs=0.01)
    assert est["recall"] < 0.5  # o que o número ingênuo (89%) esconderia


def test_labels_by_stratum_respects_the_code_set(fake_data):
    """`2` e `3` são camadas separadas: a série padrão conta só o código 1."""
    only_br = pr.labels_by_stratum({1})
    with_verbal = pr.labels_by_stratum({1, 3})
    assert only_br[("baseline", "aprovado")][0] == 8
    assert with_verbal[("baseline", "aprovado")][0] == 8  # nenhum `3` nestes dados


def test_report_needs_the_population_file(monkeypatch, tmp_path):
    """Melhor falhar do que relatar recall sem os pesos dos estratos."""
    monkeypatch.setattr(pr, "POPULATION", tmp_path / "ausente.csv")
    with pytest.raises(SystemExit, match="não existe"):
        pr.read_population()


def test_gold_items_outside_the_strata_file_are_ignored(fake_data, monkeypatch):
    """Item sem estrato não pode entrar com peso arbitrário; some da contagem."""
    rows = fake_data + [{"item_id": "sem-estrato", "label": 1, "text": "t"}]
    monkeypatch.setattr(pr, "read_gold", lambda: rows)
    labels = pr.labels_by_stratum({1})
    assert sum(n for _pos, n in labels.values()) == 20
