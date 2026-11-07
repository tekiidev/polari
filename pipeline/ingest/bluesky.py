"""Coletor do Bluesky (AT Protocol), via `app.bsky.feed.searchPosts` com login por App Password.

Privacidade: o URI do post e o cursor da paginação contêm o DID do autor. O URI só sai daqui em
`RawItem.source_ref` (o RawStore grava criptografado); o cursor nunca sai da memória. A URL de cada
página leva o cursor, então um filtro no logger do httpx descarta todo registro sobre o Bluesky.
Filtro, e não só nível: outra biblioteca (o huggingface_hub) pode baixar o nível do logger.

Texto do item = texto do post + título e descrição do cartão de link, se houver. Muitos posts
de notícia são só um comentário curto ("Absurdo.") sobre o cartão; sem ele não há o que classificar.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from datetime import datetime, timezone

import httpx

from pipeline.config import settings
from pipeline.ingest.base import Source
from pipeline.models import RawItem
from pipeline.privacy import item_id

log = logging.getLogger(__name__)


def _drop_bluesky(record: logging.LogRecord) -> bool:
    return "bsky" not in record.getMessage()


logging.getLogger("httpx").addFilter(_drop_bluesky)

XRPC = "https://bsky.social/xrpc"
PAGE_SIZE = 100  # máximo aceito pela API


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(ts: str | None) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
    except ValueError:
        return None
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class BlueskyClient:
    """Sessão autenticada com backoff em 429/5xx e renovação do token expirado."""

    def __init__(self, handle: str | None = None, app_password: str | None = None,
                 transport: httpx.BaseTransport | None = None, pause: float = 0.3):
        self.handle = handle if handle is not None else settings.bluesky_handle
        self.app_password = app_password if app_password is not None else settings.bluesky_app_password
        self.client = httpx.Client(timeout=30, transport=transport)
        self.pause = pause
        self._login()

    def _login(self) -> None:
        r = self.client.post(f"{XRPC}/com.atproto.server.createSession",
                             json={"identifier": self.handle, "password": self.app_password})
        r.raise_for_status()
        self.client.headers["Authorization"] = f"Bearer {r.json()['accessJwt']}"

    def search(self, params: dict) -> dict:
        for attempt in range(6):
            try:
                r = self.client.get(f"{XRPC}/app.bsky.feed.searchPosts", params=params)
            except httpx.TransportError as e:  # timeout, conexão caída
                wait = 2 ** attempt * 5
                log.warning("%s; esperando %ss", type(e).__name__, wait)
                time.sleep(wait)
                continue
            if r.status_code == 200:
                time.sleep(self.pause)
                return r.json()
            if r.status_code in (400, 401) and "xpired" in r.text:
                self._login()
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                wait = int(r.headers.get("retry-after", 0)) or 2 ** attempt * 5
                log.warning("HTTP %s; esperando %ss", r.status_code, wait)
                time.sleep(wait)
                continue
            r.raise_for_status()
        raise RuntimeError("Bluesky: tentativas esgotadas")

    def hits(self, q: str, since: datetime, until: datetime) -> int:
        """Estimativa do total (`hitsTotal` da primeira página); superestima ~2,6% (docs/feasibility.md)."""
        data = self.search({"q": q, "lang": "pt", "since": _iso(since), "until": _iso(until), "limit": 1})
        return int(data.get("hitsTotal") or 0)


def to_item(post: dict, query: str, since: datetime, until: datetime, secret: str | None = None) -> RawItem:
    record = post.get("record") or {}
    # createdAt é escolhido pelo cliente e pode ser forjado; fora da janela pedida, vale o indexedAt.
    created = _parse(record.get("createdAt"))
    if created is None or not since <= created < until:
        created = _parse(post.get("indexedAt")) or since
    text = (record.get("text") or "").strip()
    external = ((post.get("embed") or {}).get("external")
                or ((record.get("embed") or {}).get("external")) or {})
    card = " — ".join(s.strip() for s in (external.get("title"), external.get("description")) if s and s.strip())
    if card:
        text = f"{text}\n\n[link] {card}" if text else f"[link] {card}"
    langs = record.get("langs") or []
    return RawItem(source="bluesky", item_id=item_id("bluesky", post["uri"], secret=secret), text=text,
                   created_at=created, lang=langs[0] if langs else None, queries=[query],
                   source_ref=post["uri"])


class BlueskySource(Source):
    name = "bluesky"

    def __init__(self, queries: list[str], client: BlueskyClient | None = None, secret: str | None = None):
        self.queries = queries
        self._client = client
        self.secret = secret
        self.last_hits_total: int | None = None  # `hitsTotal` da última busca, para detectar corte

    @property
    def client(self) -> BlueskyClient:
        if self._client is None:
            self._client = BlueskyClient()
        return self._client

    def search(self, q: str, since: datetime, until: datetime, limit: int | None = None) -> Iterator[RawItem]:
        """Todos os posts de uma consulta em [since, until), paginando até acabar ou atingir `limit`."""
        params = {"q": q, "lang": "pt", "sort": "latest", "since": _iso(since), "until": _iso(until),
                  "limit": PAGE_SIZE}
        seen: set[str] = set()
        self.last_hits_total = None
        while True:
            data = self.client.search(params)
            if self.last_hits_total is None:
                self.last_hits_total = int(data.get("hitsTotal") or 0)
            posts = data.get("posts") or []
            for p in posts:
                if p["uri"] in seen:
                    continue
                seen.add(p["uri"])
                yield to_item(p, q, since, until, self.secret)
                if limit is not None and len(seen) >= limit:
                    return
            if not posts or not data.get("cursor"):
                return
            params["cursor"] = data["cursor"]

    def fetch(self, since: datetime, until: datetime | None = None, limit: int = 500) -> Iterator[RawItem]:
        until = until or datetime.now(timezone.utc)
        for q in self.queries:
            yield from self.search(q, since, until, limit)
