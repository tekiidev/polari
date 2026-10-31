import json
from datetime import datetime, timezone

from pipeline.monitor.health import RunMetrics, append_run_metrics


def make(**over) -> RunMetrics:
    base = dict(
        run_at=datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc),
        source="bluesky",
        collected=200,
        passed_prefilter=50,
        classified=48,
        classification_errors=2,
        political_violence=20,
        geolocated=5,
        llm_requests=50,
        duration_s=12.5,
        model_id="gemini-2.5-flash",
        prompt_version="v1",
    )
    base.update(over)
    return RunMetrics(**base)


def test_rates():
    m = make()
    assert m.prefilter_rate == 0.25
    assert m.error_rate == 2 / 50
    assert m.geolocated_rate == 0.25


def test_rates_do_not_divide_by_zero():
    m = make(collected=0, passed_prefilter=0, classified=0, classification_errors=0,
             political_violence=0, geolocated=0)
    assert (m.prefilter_rate, m.error_rate, m.geolocated_rate) == (0.0, 0.0, 0.0)


def test_append_writes_one_json_line_per_run(tmp_path):
    path = tmp_path / "processed" / "runs.jsonl"
    append_run_metrics(make(), path)
    append_run_metrics(make(source="rss"), path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["source"] for line in lines] == ["bluesky", "rss"]
