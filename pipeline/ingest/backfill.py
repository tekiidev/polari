"""Backfill: coleta o passado por dia local e por consulta, retomável e idempotente.

    for fatia de `chunk_days` dias locais em [start, end]:
        for consulta in source.queries:
            pula se (início da fatia, consulta) já está no checkpoint
            source.search(consulta, 00:00 do 1º dia, 24:00 do último) -> RawStore.put -> marca no checkpoint

- Fatias de 1 dia para consultas volumosas (contexto) e de 7 dias para as raras (violência): o
  custo é uma requisição por fatia e consulta, mesmo quando volta vazia. Mantenha o mesmo
  `chunk_days` para a mesma consulta entre execuções, senão o checkpoint não reconhece as fatias.
  As fatias são ancoradas em `ANCHOR` (não em `start`), para coincidirem entre execuções; a primeira
  pode começar antes de `start`. Fatia cortada por `end` é coletada, mas não entra no checkpoint.

- Idempotente: o RawStore deduplica por (source, item_id); refazer uma fatia não duplica.
- Checkpoint por fonte em `data/raw/_checkpoint/<fonte>.json`, junto do bruto (vai para o mesmo
  armazenamento privado e sobrevive ao runner do Actions). Guarda só contagens: nunca o cursor
  da paginação, que contém o DID do autor.
- Um dia só é marcado como concluído `SETTLE` depois de terminar: posts ainda estão chegando e
  sendo indexados. Rodar de novo completa o dia.
- `fetched` bem abaixo do `hitsTotal` da API indica corte da paginação; vai para o log e para o
  checkpoint, para ser conferido (o `hitsTotal` superestima ~2,6%, docs/feasibility.md).
"""
from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from pipeline.models import RawItem
from pipeline.storage import RawStore
from pipeline.study.windows import day_bounds

log = logging.getLogger(__name__)

ANCHOR = date(2026, 6, 1)
SETTLE = timedelta(hours=6)
TRUNCATION_RATIO = 0.85  # abaixo disso do hitsTotal, suspeita de corte
TRUNCATION_MIN_HITS = 50  # em fatias pequenas a diferença relativa é ruído


class QuerySource(Protocol):
    name: str
    queries: list[str]
    last_hits_total: int | None

    def search(self, q: str, since: datetime, until: datetime) -> Iterator[RawItem]: ...


class Checkpoint:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, dict[str, dict]] = json.loads(path.read_text("utf-8")) if path.exists() else {}

    def done(self, day: date, query: str) -> bool:
        return query in self.data.get(day.isoformat(), {})

    def mark(self, day: date, query: str, **stats) -> None:
        self.data.setdefault(day.isoformat(), {})[query] = stats
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1, sort_keys=True), "utf-8")
        os.replace(tmp, self.path)


def checkpoint_for(store: RawStore, source: str) -> Checkpoint:
    return Checkpoint(store.root / "_checkpoint" / f"{source}.json")


def backfill(source: QuerySource, store: RawStore, start: date, end: date, chunk_days: int = 1,
             now: datetime | None = None) -> dict[str, int]:
    """Coleta [start, end] (dias locais, inclusivos). Devolve totais da execução."""
    now = now or datetime.now(timezone.utc)
    ckpt = checkpoint_for(store, source.name)
    totals = {"slices": 0, "skipped": 0, "fetched": 0, "new": 0, "suspect": 0}
    day = start - timedelta(days=(start - ANCHOR).days % chunk_days)
    while day <= end:
        full_last = day + timedelta(days=chunk_days - 1)
        last = min(full_last, end)
        since, until = day_bounds(day)[0], day_bounds(last)[1]
        if since >= now:
            break
        for q in source.queries:
            if ckpt.done(day, q):
                totals["skipped"] += 1
                continue
            items = list(source.search(q, since, min(until, now)))
            new = store.put(items)
            hits = source.last_hits_total or 0
            suspect = hits >= TRUNCATION_MIN_HITS and len(items) < TRUNCATION_RATIO * hits
            level = logging.WARNING if suspect else logging.INFO
            log.log(level, "%s %s %-28r itens=%d novos=%d hitsTotal=%d%s", source.name, day, q,
                    len(items), new, hits, "  <- possível corte da paginação" if suspect else "")
            if last == full_last and until + SETTLE <= now:
                ckpt.mark(day, q, fetched=len(items), new=new, hits_total=hits, suspect=suspect)
            totals["slices"] += 1
            totals["fetched"] += len(items)
            totals["new"] += new
            totals["suspect"] += suspect
        day = last + timedelta(days=1)
    return totals
