"""IDs com hash e link original criptografado: o DID do autor nunca aparece em claro."""
from datetime import datetime, timezone

import pytest
from cryptography.fernet import InvalidToken

from pipeline.models import RawItem
from pipeline.privacy import decrypt_ref, encrypt_ref, item_id

KEY = "k" * 40
OTHER_KEY = "x" * 40
URI = "at://did:plc:abc123xyz/app.bsky.feed.post/3kq2abc"


def test_item_id_is_stable_and_hides_did():
    a = item_id("bluesky", URI, secret=KEY)
    assert a == item_id("bluesky", URI, secret=KEY)
    assert a == item_id("bluesky", f"  {URI}\n", secret=KEY)
    assert len(a) == 32 and "did" not in a


def test_item_id_depends_on_source_and_key():
    base = item_id("bluesky", URI, secret=KEY)
    assert base != item_id("rss", URI, secret=KEY)
    assert base != item_id("bluesky", URI, secret=OTHER_KEY)


def test_missing_or_short_key_fails_loudly():
    with pytest.raises(RuntimeError, match="POLARI_SECRET_KEY"):
        item_id("bluesky", URI, secret="")
    with pytest.raises(RuntimeError):
        item_id("bluesky", URI, secret="curta")


def test_ref_roundtrip_and_wrong_key_rejected():
    token = encrypt_ref(URI, secret=KEY)
    assert "did:plc" not in token
    assert decrypt_ref(token, secret=KEY) == URI
    with pytest.raises(InvalidToken):
        decrypt_ref(token, secret=OTHER_KEY)


def test_raw_item_never_dumps_source_ref():
    item = RawItem(
        source="bluesky",
        item_id=item_id("bluesky", URI, secret=KEY),
        text="texto",
        created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        source_ref=URI,
    )
    assert "did:plc" not in item.model_dump_json()
    assert "did:plc" not in repr(item)
    assert item.source_ref == URI


def test_raw_item_rejects_unhashed_id():
    with pytest.raises(ValueError):
        RawItem(source="bluesky", item_id=URI, text="t", created_at=datetime.now(timezone.utc))
