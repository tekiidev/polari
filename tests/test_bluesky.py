"""Coletor do Bluesky com HTTP simulado: paginação, mapeamento para RawItem e privacidade."""
from datetime import date, datetime, timezone

import httpx

from pipeline.ingest.bluesky import BlueskyClient, BlueskySource, to_item
from pipeline.study.windows import day_bounds

KEY = "k" * 40
SINCE, UNTIL = day_bounds(date(2026, 10, 4))  # 03:00Z de 04/10 a 03:00Z de 05/10


def post(n: int, created: str = "2026-10-04T15:00:00Z", **extra) -> dict:
    return {"uri": f"at://did:plc:autor{n}/app.bsky.feed.post/{n}", "indexedAt": "2026-10-04T15:00:01Z",
            "record": {"text": f"post {n}", "createdAt": created, "langs": ["pt"]}, **extra}


def fake_api(pages: list[dict], calls: list[dict] | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("createSession"):
            return httpx.Response(200, json={"accessJwt": "jwt"})
        params = dict(request.url.params)
        if calls is not None:
            calls.append(params)
        i = int(params.get("cursor", 0))
        return httpx.Response(200, json=pages[i])
    return httpx.MockTransport(handler)


def source(pages: list[dict], calls: list[dict] | None = None) -> BlueskySource:
    client = BlueskyClient("h", "p", transport=fake_api(pages, calls), pause=0)
    return BlueskySource(["eleição"], client=client, secret=KEY)


def test_paginates_until_cursor_ends():
    pages = [{"posts": [post(1), post(2)], "cursor": "1"}, {"posts": [post(3)]}]
    calls: list[dict] = []
    items = list(source(pages, calls).search("eleição", SINCE, UNTIL))
    assert [i.text for i in items] == ["post 1", "post 2", "post 3"]
    assert calls[0]["since"] == "2026-10-04T03:00:00Z" and calls[0]["until"] == "2026-10-05T03:00:00Z"
    assert calls[0]["lang"] == "pt" and calls[1]["cursor"] == "1"


def test_limit_and_duplicates_across_pages():
    pages = [{"posts": [post(1), post(2)], "cursor": "1"}, {"posts": [post(2), post(3)], "cursor": "2"},
             {"posts": [post(4)]}]
    assert len(list(source(pages).search("eleição", SINCE, UNTIL))) == 4
    assert len(list(source(pages).search("eleição", SINCE, UNTIL, limit=3))) == 3


def test_item_has_no_author_outside_source_ref():
    item = to_item(post(7), "eleição", SINCE, UNTIL, secret=KEY)
    assert "did:plc" not in item.model_dump_json()
    assert item.source_ref.startswith("at://did:plc:autor7")
    assert item.queries == ["eleição"] and item.lang == "pt"


def test_forged_created_at_falls_back_to_indexed_at():
    item = to_item(post(1, created="2010-01-01T00:00:00Z"), "q", SINCE, UNTIL, secret=KEY)
    assert item.created_at == datetime(2026, 10, 4, 15, 0, 1, tzinfo=timezone.utc)


def test_link_card_is_appended_to_text():
    p = post(1, embed={"external": {"title": "Vereadora é morta a tiros", "description": "Crime em MG"}})
    p["record"]["text"] = "Absurdo."
    assert to_item(p, "q", SINCE, UNTIL, secret=KEY).text == "Absurdo.\n\n[link] Vereadora é morta a tiros — Crime em MG"


def test_retries_after_rate_limit(monkeypatch):
    monkeypatch.setattr("pipeline.ingest.bluesky.time.sleep", lambda s: None)
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("createSession"):
            return httpx.Response(200, json={"accessJwt": "jwt"})
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "1"})
        return httpx.Response(200, json={"posts": [post(1)]})

    client = BlueskyClient("h", "p", transport=httpx.MockTransport(handler), pause=0)
    assert len(list(BlueskySource(["q"], client=client, secret=KEY).search("q", SINCE, UNTIL))) == 1


def test_retries_after_timeout(monkeypatch):
    monkeypatch.setattr("pipeline.ingest.bluesky.time.sleep", lambda s: None)
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("createSession"):
            return httpx.Response(200, json={"accessJwt": "jwt"})
        state["n"] += 1
        if state["n"] == 1:
            raise httpx.ReadTimeout("lento", request=request)
        return httpx.Response(200, json={"posts": [post(1)]})

    client = BlueskyClient("h", "p", transport=httpx.MockTransport(handler), pause=0)
    assert len(list(BlueskySource(["q"], client=client, secret=KEY).search("q", SINCE, UNTIL))) == 1


def test_bluesky_urls_never_logged_even_at_debug(caplog):
    import logging
    logging.getLogger("httpx").setLevel(logging.DEBUG)  # simula outra biblioteca mudando o nível
    with caplog.at_level(logging.DEBUG, logger="httpx"):
        logging.getLogger("httpx").info("HTTP Request: GET https://bsky.social/xrpc/x?cursor=did:plc:abc")
        logging.getLogger("httpx").info("HTTP Request: GET https://huggingface.co/api/x")
    assert "did:plc" not in caplog.text and "huggingface" in caplog.text
