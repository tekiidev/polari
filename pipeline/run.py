"""Orquestrador: python -m pipeline.run [--dry-run] [--backfill-from AAAA-MM-DD --backfill-to AAAA-MM-DD]
                                       [--no-sync]

Etapas: (backfill) -> ingest -> prefilter -> classify -> geocode -> aggregate -> health.
Cada etapa deve ser idempotente (reexecutar não duplica) e logar contagens de entrada/saída.
Sem argumentos de backfill, roda a coleta incremental desde a última execução.
"""
from __future__ import annotations

import argparse
import logging
from collections import Counter
from datetime import date

from pipeline.classify.prefilter import prefilter_rules
from pipeline.ingest.backfill import backfill
from pipeline.ingest.bluesky import BlueskyClient, BlueskySource
from pipeline.ingest.queries import FAMILIES
from pipeline.remote import RemoteRaw
from pipeline.storage import RawStore
from pipeline.study.windows import EVENTS, PERIODS

log = logging.getLogger("pipeline")

# Fatia por família: contexto é volumoso (fatia diária); as de violência são raras (semanal).
CHUNK_DAYS = {"contexto": 1, "cargo": 7, "evento": 7, "espectro": 7}


def run_backfill(start: date, end: date, sync: bool) -> None:
    store = RawStore()
    remote = RemoteRaw() if sync else None
    if remote:
        remote.pull(store.root)
    client = BlueskyClient()
    try:
        for family, queries in FAMILIES.items():
            totals = backfill(BlueskySource(queries, client=client), store, start, end, CHUNK_DAYS[family])
            log.info("família %-9s %s", family, totals)
    finally:  # envia o que já foi coletado mesmo se a coleta cair no meio
        if remote:
            remote.push(store.root, f"backfill bluesky {start}..{end}")
    prefilter_summary(store, start, end)


def prefilter_summary(store: RawStore, start: date, end: date) -> None:
    rules, n, passed = Counter(), 0, 0
    for item in store.iter_items("bluesky", start, end):
        n += 1
        r = prefilter_rules(item.text, item.queries)
        passed += bool(r)
        rules.update(r)
    log.info("pré-filtro: %d de %d itens passam (%.1f%%); por regra: %s",
             passed, n, 100 * passed / max(n, 1), dict(rules))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="não chama APIs; só valida a estrutura")
    parser.add_argument("--backfill-from", type=date.fromisoformat, help="início do backfill (AAAA-MM-DD)")
    parser.add_argument("--backfill-to", type=date.fromisoformat, help="fim do backfill (AAAA-MM-DD)")
    parser.add_argument("--no-sync", action="store_true", help="não sincroniza o bruto com o HF")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if bool(args.backfill_from) != bool(args.backfill_to):
        parser.error("--backfill-from e --backfill-to devem ser usados juntos")

    if args.dry_run:
        for p in PERIODS:
            log.info("período %-13s %s -> %s", p.name, p.start, p.end or "em aberto")
        for name, day in EVENTS.items():
            log.info("evento  %-14s %s", name, day)
        log.info("dry-run: estrutura ok, nenhuma chamada externa feita")
        return

    if args.backfill_from:
        run_backfill(args.backfill_from, args.backfill_to, sync=not args.no_sync)
        return

    # TODO(Fase 5): fetch incremental -> prefilter -> classify
    #           -> resolve_city -> build_outputs -> append_run_metrics
    raise NotImplementedError("Conecte as etapas do pipeline.")


if __name__ == "__main__":
    main()
