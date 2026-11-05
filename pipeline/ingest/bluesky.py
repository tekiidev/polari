"""Coletor do Bluesky (AT Protocol).

Pontos que você precisa entender para implementar:
  1. A busca de posts exige login. Use App Password (nunca a senha principal):
       POST https://bsky.social/xrpc/com.atproto.server.createSession
       body: {"identifier": <handle>, "password": <app password>}  -> accessJwt
  2. Busca:
       GET https://bsky.social/xrpc/app.bsky.feed.searchPosts
       params: q, since, until, lang, limit (<=100), cursor
       header: Authorization: Bearer <accessJwt>
     Pagine com `cursor` até atingir `limit` ou acabar.
  3. Mapeie cada post para RawItem: item_id("bluesky", uri) -> item_id, uri -> source_ref, record.text -> text,
     record.createdAt -> created_at. NÃO guarde handle/DID do autor.
  4. Respeite rate limits (faça backoff em 429) e confira a doc atual da API.

Consultas sugeridas (lang=pt): combine termos de violência + contexto eleitoral
(veja a lista inicial em pipeline/classify/prefilter.py).
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pipeline.ingest.base import Source
from pipeline.models import RawItem


class BlueskySource(Source):
    name = "bluesky"

    def __init__(self, handle: str, app_password: str, queries: list[str]):
        self.handle = handle
        self.app_password = app_password
        self.queries = queries

    def fetch(self, since: datetime, until: datetime | None = None, limit: int = 500) -> Iterable[RawItem]:
        # TODO(D1): login -> loop de queries -> paginação -> yield RawItem
        raise NotImplementedError("Implemente a coleta do Bluesky (veja o docstring).")
