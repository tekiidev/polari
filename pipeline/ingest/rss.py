"""Coletor de notícias por RSS (ex.: Google News com query, feeds de portais).

Dicas:
  - `feedparser.parse(url)` devolve entries com title, summary, link, published_parsed.
  - Para o texto a classificar, use title + summary (não faça scraping do corpo da matéria).
  - item_id = pipeline.privacy.item_id("rss", url); a URL vai em source_ref (gravada criptografada).
  - Notícias são o "ground truth" para cruzar com o discurso das redes.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pipeline.ingest.base import Source
from pipeline.models import RawItem


class RssSource(Source):
    name = "rss"

    def __init__(self, feed_urls: list[str]):
        self.feed_urls = feed_urls

    def fetch(self, since: datetime, until: datetime | None = None, limit: int = 500) -> Iterable[RawItem]:
        # TODO(D1): parse de cada feed -> filtrar por data -> yield RawItem
        raise NotImplementedError("Implemente a coleta por RSS (veja o docstring).")
