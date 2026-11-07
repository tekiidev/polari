"""Backfill: retomada pelo checkpoint, idempotência, dia em aberto e detecção de corte."""
import json
from datetime import date, datetime, timedelta, timezone

from pipeline.ingest.backfill import backfill, checkpoint_for
from pipeline.models import RawItem
from pipeline.privacy import item_id
from pipeline.storage import RawStore

KEY = "k" * 40


class FakeSource:
    name = "bluesky"

    def __init__(self, queries, per_slice=2, hits_total=None, fail_on=None):
        self.queries, self.per_slice, self.hits_total, self.fail_on = queries, per_slice, hits_total, fail_on
        self.calls: list[tuple[str, datetime]] = []
        self.last_hits_total = None

    def search(self, q, since, until):
        if (q, since) == self.fail_on:
            raise RuntimeError("queda simulada")
        self.calls.append((q, since))
        self.last_hits_total = self.hits_total if self.hits_total is not None else self.per_slice
        for n in range(self.per_slice):
            uri = f"at://did:plc:x/app.bsky.feed.post/{since.date()}-{n}"
            yield RawItem(source="bluesky", item_id=item_id("bluesky", uri, secret=KEY), text="t",
                          created_at=since + timedelta(hours=1), queries=[q], source_ref=uri)


NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


def test_resumes_from_checkpoint_without_refetching(tmp_path):
    store = RawStore(tmp_path, secret=KEY)
    src = FakeSource(["a", "b"])
    oct2 = datetime(2026, 10, 2, 3, 0, tzinfo=timezone.utc)
    src.fail_on = ("b", oct2)
    try:
        backfill(src, store, date(2026, 10, 1), date(2026, 10, 3), now=NOW)
    except RuntimeError:
        pass
    assert len(src.calls) == 3  # 01/10 a, b; 02/10 a

    src2 = FakeSource(["a", "b"])
    totals = backfill(src2, store, date(2026, 10, 1), date(2026, 10, 3), now=NOW)
    assert totals["skipped"] == 3 and totals["slices"] == 3
    assert [q for q, _ in src2.calls] == ["b", "a", "b"]


def test_same_posts_from_two_queries_are_not_duplicated(tmp_path):
    store = RawStore(tmp_path, secret=KEY)
    totals = backfill(FakeSource(["a", "b"]), store, date(2026, 10, 1), date(2026, 10, 1), now=NOW)
    assert totals == {"slices": 2, "skipped": 0, "fetched": 4, "new": 2, "suspect": 0}
    items = list(store.iter_items("bluesky", date(2026, 10, 1), date(2026, 10, 1)))
    assert len(items) == 2 and all(i.queries == ["a", "b"] for i in items)


def test_open_day_is_collected_but_not_marked_done(tmp_path):
    store = RawStore(tmp_path, secret=KEY)
    backfill(FakeSource(["a"]), store, date(2026, 11, 4), date(2026, 11, 6), now=NOW)
    ckpt = checkpoint_for(store, "bluesky")
    assert ckpt.done(date(2026, 11, 4), "a")
    assert not ckpt.done(date(2026, 11, 5), "a")  # hoje: ainda chegam posts
    assert "2026-11-06" not in ckpt.data  # futuro: nem consultado


def test_truncation_is_flagged_and_checkpoint_has_only_counts(tmp_path):
    store = RawStore(tmp_path, secret=KEY)
    totals = backfill(FakeSource(["a"], per_slice=10, hits_total=100), store,
                      date(2026, 10, 1), date(2026, 10, 1), now=NOW)
    assert totals["suspect"] == 1
    raw = checkpoint_for(store, "bluesky").path.read_text("utf-8")
    assert json.loads(raw)["2026-10-01"]["a"] == {"fetched": 10, "new": 10, "hits_total": 100, "suspect": True}
    assert "did:plc" not in raw


def test_weekly_chunks_cover_range_once(tmp_path):
    src = FakeSource(["a"])
    backfill(src, RawStore(tmp_path, secret=KEY), date(2026, 10, 1), date(2026, 10, 15), chunk_days=7, now=NOW)
    # ancoradas em 01/06 (segunda): 28/09–04/10, 05–11, 12–18 (cortada em 15/10)
    assert [s.date() for _, s in src.calls] == [date(2026, 9, 28), date(2026, 10, 5), date(2026, 10, 12)]
    ckpt = checkpoint_for(RawStore(tmp_path, secret=KEY), "bluesky")
    assert ckpt.done(date(2026, 10, 5), "a") and not ckpt.done(date(2026, 10, 12), "a")

    src2 = FakeSource(["a"])
    backfill(src2, RawStore(tmp_path, secret=KEY), date(2026, 10, 1), date(2026, 10, 25), chunk_days=7, now=NOW)
    assert [s.date() for _, s in src2.calls] == [date(2026, 10, 12), date(2026, 10, 19)]
