"""Métricas: F1, intervalo pareado e simetria, verificados contra casos de resposta conhecida."""
import json

import numpy as np
import pytest

from eval import metrics


def rows_from(pairs, **extra):
    """pairs = [(gold, predicted), ...]"""
    return [
        {
            "item_id": f"i{n}",
            "gold": g,
            "predicted": p,
            "model_id": "m",
            "prompt_version": "v2",
            "latency_s": 1.0,
            "attempts": 1,
            "error": None,
            "invalid_json": False,
            "input_tokens": 10,
            "output_tokens": 5,
            "fields": None,
            **extra,
        }
        for n, (g, p) in enumerate(pairs)
    ]


def test_perfect_prediction():
    c = metrics.counts_of(rows_from([(1, 1), (1, 1), (0, 0)]))
    assert c.f1 == 1.0 and c.precision == 1.0 and c.recall == 1.0


def test_f1_known_value():
    # 2 TP, 1 FP, 1 FN -> precisão 2/3, recall 2/3, F1 2/3
    c = metrics.counts_of(rows_from([(1, 1), (1, 1), (0, 1), (1, 0)]))
    assert c.tp == 2 and c.fp == 1 and c.fn == 1
    assert c.f1 == pytest.approx(2 / 3, abs=1e-9)


def test_failure_counts_as_negative_not_discarded():
    """Descartar erro inflaria o F1: item com previsão None conta como negativo previsto."""
    rows = rows_from([(1, 1), (1, None)])
    c = metrics.counts_of(rows)
    assert c.tp == 1 and c.fn == 1  # o None entrou como falso negativo
    assert c.f1 == pytest.approx(2 / 3, abs=1e-9)


def test_other_codes_are_negative_for_the_default_series():
    """A série padrão é só o código 1: 2 e 3 contam como negativos."""
    c = metrics.counts_of(rows_from([(2, 2), (3, 3), (1, 1)]))
    assert c.tp == 1 and c.fp == 0 and c.fn == 0 and c.tn == 2


def test_predicting_other_code_on_a_positive_is_a_miss():
    c = metrics.counts_of(rows_from([(1, 3)]))
    assert c.fn == 1 and c.tp == 0


def test_bootstrap_ci_brackets_point_estimate():
    rows = rows_from([(1, 1)] * 15 + [(0, 0)] * 15 + [(1, 0)] * 5 + [(0, 1)] * 5)
    gold, pred = metrics.arrays(rows)
    f1 = metrics.counts_of(rows).f1
    lo, hi = metrics.bootstrap_ci(gold, pred, n=2000)
    assert lo <= f1 <= hi and lo < hi


def test_identical_models_tie():
    """Modelos idênticos: diferença zero e intervalo contendo zero."""
    rows = rows_from([(1, 1)] * 10 + [(0, 0)] * 10 + [(1, 0)] * 3)
    gold, pred = metrics.arrays(rows)
    point, lo, hi = metrics.paired_diff_ci(gold, pred, pred, n=2000)
    assert point == 0.0 and lo <= 0 <= hi


def test_clearly_better_model_shows_difference():
    gold = np.array([1] * 20 + [0] * 20)
    good = np.array([1] * 20 + [0] * 20)          # perfeito
    bad = np.array([0] * 20 + [1] * 20)           # tudo errado
    point, lo, hi = metrics.paired_diff_ci(gold, good, bad, n=2000)
    assert point > 0.9 and lo > 0  # intervalo não contém zero


def test_operational_flags_invalid_json():
    rows = rows_from([(1, 1)] * 96 + [(1, None)] * 4, )
    for r in rows:
        if r["predicted"] is None:
            r["invalid_json"] = True
    op = metrics.operational(rows)
    assert op["invalid_json_pct"] == pytest.approx(4.0)
    assert op["failed_pct"] == pytest.approx(4.0)


def test_operational_latency_percentiles():
    rows = rows_from([(1, 1)] * 10)
    for n, r in enumerate(rows):
        r["latency_s"] = float(n)
    op = metrics.operational(rows)
    assert op["latency_median_s"] == pytest.approx(4.5)
    assert op["latency_p95_s"] > op["latency_median_s"]


@pytest.fixture
def results_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "RESULTS", tmp_path)
    return tmp_path


def write_results(results_dir, backend, dataset, rows, run=1):
    path = results_dir / f"{backend}__{dataset}__run{run}.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def mirrored_rows(verdicts):
    """verdicts = {pair_id: (pred_a, pred_b)}"""
    rows = []
    for pair_id, (pa, pb) in verdicts.items():
        for side, pred in (("a", pa), ("b", pb)):
            rows.append(
                {
                    "item_id": f"{pair_id}::{side}",
                    "gold": 1,
                    "predicted": pred,
                    "model_id": "m",
                    "prompt_version": "v2",
                    "latency_s": 1.0,
                    "attempts": 1,
                    "error": None,
                    "invalid_json": False,
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "fields": None,
                }
            )
    return rows


def test_symmetry_reports_pass(results_dir, capsys):
    write_results(results_dir, "m1", "mirrored", mirrored_rows({f"p{n}": (1, 1) for n in range(20)}))
    metrics.report_symmetry(["m1"])
    out = capsys.readouterr().out
    assert "0/20" in out and "[ok]" in out


def test_symmetry_reports_fail_above_limit(results_dir, capsys):
    verdicts = {f"p{n}": (1, 1) for n in range(16)}
    verdicts.update({f"p{n}": (1, 0) for n in range(16, 20)})  # 20% divergente
    write_results(results_dir, "m1", "mirrored", mirrored_rows(verdicts))
    metrics.report_symmetry(["m1"])
    out = capsys.readouterr().out
    assert "20.0%" in out and "REPROVA" in out


def test_symmetry_detects_direction(results_dir, capsys):
    """Divergência sempre no mesmo sentido é viés de lado, não ruído."""
    verdicts = {f"p{n}": (1, 1) for n in range(10)}
    verdicts.update({f"p{n}": (1, 0) for n in range(10, 15)})  # sempre A positivo
    write_results(results_dir, "m1", "mirrored", mirrored_rows(verdicts))
    metrics.report_symmetry(["m1"])
    out = capsys.readouterr().out
    assert "5 vezes só o lado A positivo, 0 vezes" in out
    assert "direção" in out


def test_symmetry_detects_noise(results_dir, capsys):
    """Divergência equilibrada nos dois sentidos parece instabilidade."""
    verdicts = {f"p{n}": (1, 1) for n in range(10)}
    verdicts["p10"] = (1, 0)
    verdicts["p11"] = (0, 1)
    write_results(results_dir, "m1", "mirrored", mirrored_rows(verdicts))
    metrics.report_symmetry(["m1"])
    assert "instabilidade" in capsys.readouterr().out


def test_api_failure_triggers_coverage_warning():
    """Cota esgotada derrubaria o F1 e pareceria modelo ruim: o relatório tem de avisar."""
    rows = rows_from([(1, 1)] * 20 + [(1, None)] * 126)
    for r in rows:
        if r["predicted"] is None:
            r["error"] = "api: ClientError: 429 RESOURCE_EXHAUSTED"
    warning = metrics.coverage_warning(rows)
    assert warning and "126/146" in warning


def test_model_failure_does_not_trigger_coverage_warning():
    """JSON inválido é culpa do modelo e deve pesar no F1, sem aviso de cobertura."""
    rows = rows_from([(1, 1)] * 20 + [(1, None)] * 10)
    for r in rows:
        if r["predicted"] is None:
            r["error"] = "json: Expecting value"
            r["invalid_json"] = True
    assert metrics.coverage_warning(rows) is None


def test_few_api_failures_do_not_warn():
    rows = rows_from([(1, 1)] * 99 + [(1, None)])
    rows[-1]["error"] = "api: timeout"
    assert metrics.coverage_warning(rows) is None


def test_missing_results_file_fails_clearly(results_dir):
    with pytest.raises(SystemExit):
        metrics.load_results("inexistente", "dev")
