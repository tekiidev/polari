"""Orquestrador: python -m pipeline.run [--dry-run] [--backfill-from AAAA-MM-DD --backfill-to AAAA-MM-DD]

Etapas: (backfill) -> ingest -> prefilter -> classify -> geocode -> aggregate -> health.
Cada etapa deve ser idempotente (reexecutar não duplica) e logar contagens de entrada/saída.
Sem argumentos de backfill, roda a coleta incremental desde a última execução.
"""
from __future__ import annotations

import argparse
import logging
from datetime import date

from pipeline.study.windows import EVENTS, PERIODS

log = logging.getLogger("pipeline")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="não chama APIs; só valida a estrutura")
    parser.add_argument("--backfill-from", type=date.fromisoformat, help="início do backfill (AAAA-MM-DD)")
    parser.add_argument("--backfill-to", type=date.fromisoformat, help="fim do backfill (AAAA-MM-DD)")
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

    # TODO(D3): montar fontes -> (backfill | fetch incremental) -> prefilter -> classify
    #           -> resolve_city -> build_outputs -> append_run_metrics
    raise NotImplementedError("Conecte as etapas do pipeline.")


if __name__ == "__main__":
    main()
