"""RawStore: idempotência, dia local, link criptografado em disco e remoção de posts apagados."""
from datetime import date, datetime, timezone

from pipeline.models import RawItem
from pipeline.privacy import item_id
from pipeline.storage import RawStore

KEY = "k" * 40


def make(uri: str, created_at: datetime, text: str = "texto") -> RawItem:
    return RawItem(source="bluesky", item_id=item_id("bluesky", uri, secret=KEY), text=text,
                   created_at=created_at, lang="pt", source_ref=uri)


OCT4 = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
A = make("at://did:plc:aaa/app.bsky.feed.post/1", OCT4)
B = make("at://did:plc:bbb/app.bsky.feed.post/2", OCT4)


def test_put_is_idempotent(tmp_path):
    store = RawStore(tmp_path, secret=KEY)
    assert store.put([A, B]) == 2
    assert store.put([A, B, A]) == 0
    assert len(list(store.iter_items("bluesky", date(2026, 10, 4), date(2026, 10, 4)))) == 2


def test_partition_uses_local_day(tmp_path):
    # 01:30 UTC de 26/10 = 22:30 de 25/10 em Brasília
    late = make("at://did:plc:ccc/app.bsky.feed.post/3", datetime(2026, 10, 26, 1, 30, tzinfo=timezone.utc))
    RawStore(tmp_path, secret=KEY).put([late])
    assert (tmp_path / "source=bluesky" / "day=2026-10-25" / "items.parquet").exists()


def test_did_never_on_disk_in_clear(tmp_path):
    store = RawStore(tmp_path, secret=KEY)
    store.put([A])
    for f in tmp_path.rglob("*"):
        if f.is_file():
            assert b"did:plc" not in f.read_bytes()
    (back,) = store.iter_items("bluesky", date(2026, 10, 4), date(2026, 10, 4))
    assert back.source_ref == A.source_ref and back.created_at == A.created_at


def test_delete_removes_items_and_empty_partition(tmp_path):
    store = RawStore(tmp_path, secret=KEY)
    store.put([A, B])
    assert store.delete("bluesky", date(2026, 10, 4), {A.item_id}) == 1
    assert [i.item_id for i in store.iter_items("bluesky", date(2026, 10, 4), date(2026, 10, 4))] == [B.item_id]
    assert store.delete("bluesky", date(2026, 10, 4), {B.item_id}) == 1
    assert not (tmp_path / "source=bluesky" / "day=2026-10-04" / "items.parquet").exists()
