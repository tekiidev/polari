"""Estimativa do recall do pré-filtro por estratos."""
import pytest

from pipeline.classify.recall import estimate, primary_family


def test_violence_family_wins_over_context():
    assert primary_family(["eleição", "vereadora morta"]) == "cargo"
    assert primary_family(["voto"]) == "contexto"


def test_recall_weights_strata_by_population():
    # aprovados: 100 itens, metade positiva -> 50; barrados: 1000 itens, 2% positivos -> 20
    pop = {("contexto", "aprovado"): 100, ("contexto", "barrado"): 1000}
    labels = {("contexto", "aprovado"): (10, 20), ("contexto", "barrado"): (1, 50)}
    est = estimate(pop, labels)
    assert est["recall"] == pytest.approx(50 / 70)
    assert est["low"] < est["recall"] < est["high"]


def test_zero_positives_blocked_still_gives_uncertainty():
    pop = {("contexto", "aprovado"): 100, ("contexto", "barrado"): 100_000}
    est = estimate(pop, {("contexto", "aprovado"): (10, 20), ("contexto", "barrado"): (0, 50)})
    assert est["recall"] == 1.0
    assert est["low"] < 0.5  # 0 de 50 num estrato de 100 mil não prova recall alto


def test_report_counts_foreign_cases_only_in_broad_definition(tmp_path, monkeypatch):
    import pipeline.classify.recall as r
    (tmp_path / "s.csv").write_text("item_id,text,is_political_violence\na,t,1\nb,t,2\nc,t,0\nd,t,\ne,t,3\n", "utf-8")
    (tmp_path / "e.csv").write_text("item_id,family,status,rules\na,cargo,aprovado,politica\n"
                                    "b,cargo,aprovado,politica\nc,cargo,barrado,\nd,cargo,barrado,\ne,cargo,barrado,\n", "utf-8")
    (tmp_path / "p.csv").write_text("family,status,n\ncargo,aprovado,10\ncargo,barrado,10\n", "utf-8")
    monkeypatch.setattr(r, "SAMPLE", tmp_path / "s.csv")
    monkeypatch.setattr(r, "STRATA", tmp_path / "e.csv")
    monkeypatch.setattr(r, "POPULATION", tmp_path / "p.csv")
    out = r.report()
    assert "sem rótulo: 1" in out
    assert "| cargo | aprovado | 10 | 2 | 1 | 1 | 0 |" in out and "| cargo | barrado | 10 | 2 | 0 | 0 | 1 |" in out
    assert "**Recall (Brasil, sem ofensa verbal):** 100.0%" in out
    # o xingamento (3) foi barrado: só a definição com ofensa perde recall (5 aprovados de 10 estimados)
    assert "**Recall (Brasil, com ofensa verbal):** 50.0%" in out
    assert "- `politica`: 1 / 1 / 0 / 2" in out
