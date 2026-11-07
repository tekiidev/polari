"""Teste de viabilidade (Fase 1): quantos posts existem por dia local, por termo, em cada fonte.

    python -m pipeline.feasibility bluesky --start 2026-06-01 --end 2026-11-02 [--verify]
    python -m pipeline.feasibility summary

Só grava contagens (dia, termo, total) em docs/feasibility/: nenhum texto, URI ou cursor
(o cursor do Bluesky contém o DID do autor). Retoma de onde parou: pares (dia, termo) já
gravados são pulados.

Bluesky: `hitsTotal` da primeira página estima o total do dia. Conferido contra paginação
completa em 3 dias (diferença de 1–4%, posts removidos que entram na contagem mas não voltam);
`--verify` repete a conferência a cada 15 dias e grava em bluesky_verify.csv.
"""
from __future__ import annotations

import argparse
import csv
import logging
from datetime import date, timedelta
from pathlib import Path

from pipeline.config import ROOT
from pipeline.ingest.bluesky import BlueskyClient, BlueskySource
from pipeline.study.windows import EVENTS, PERIODS, day_bounds, period_of

log = logging.getLogger("feasibility")

OUT_DIR = ROOT / "docs" / "feasibility"

# Denominador: posts sobre o contexto eleitoral. A busca do Bluesky faz AND entre palavras;
# os termos se sobrepõem, então NÃO some as colunas (a união exige paginar, Fase 2).
CONTEXT_QUERIES = ["eleição", "eleições", "candidato", "voto"]
# Numerador aproximado: violência + contexto. Lista curta e enviesada para casos centrais;
# serve para estimar ordem de grandeza, não para medir recall.
VIOLENCE_QUERIES = [
    "violência política", "violência eleitoral", "ameaça de morte", "ameaça candidato",
    "ameaça eleição", "agredido eleitor", "agressão eleição", "atentado candidato",
    "candidato baleado", "vereador baleado", "vereadora assassinada", "candidato morto",
    "tiro candidato",
]
QUERIES = CONTEXT_QUERIES + VIOLENCE_QUERIES


class Bluesky(BlueskyClient):
    def hits(self, q: str, d: date) -> int:
        return super().hits(q, *day_bounds(d))

    def paginate_count(self, q: str, d: date) -> int:
        return sum(1 for _ in BlueskySource([q], client=self).search(q, *day_bounds(d)))


def _done(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as f:
        return {(r["day"], r["query"]) for r in csv.DictReader(f)}


def _append(path: Path, fields: list[str], row: dict) -> None:
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow(row)


def run_bluesky(start: date, end: date, verify: bool) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    daily, ver = OUT_DIR / "bluesky_daily.csv", OUT_DIR / "bluesky_verify.csv"
    done, bs = _done(daily), Bluesky()
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    for i, d in enumerate(days):
        for q in QUERIES:
            if (d.isoformat(), q) in done:
                continue
            _append(daily, ["day", "query", "hits_total"], {"day": d, "query": q, "hits_total": bs.hits(q, d)})
        if verify and i % 15 == 0 and (d.isoformat(), "eleição") not in _done(ver):
            est, real = bs.hits("eleição", d), bs.paginate_count("eleição", d)
            _append(ver, ["day", "query", "hits_total", "paginated"],
                    {"day": d, "query": "eleição", "hits_total": est, "paginated": real})
        log.info("%s ok (%d/%d)", d, i + 1, len(days))


def summary() -> str:
    """Tabela por período e por janela D±14, em markdown."""
    with (OUT_DIR / "bluesky_daily.csv").open(encoding="utf-8") as f:
        rows = [(date.fromisoformat(r["day"]), r["query"], int(r["hits_total"])) for r in csv.DictReader(f)]
    groups: dict[str, list[date]] = {p.name: [] for p in PERIODS}
    for d in sorted({r[0] for r in rows}):
        if (name := period_of(d)):
            groups[name].append(d)
    for name, ev in EVENTS.items():
        groups[f"{name} D±14"] = [ev + timedelta(days=k) for k in range(-14, 15)]
    by = {(d, q): n for d, q, n in rows}
    cols = list(groups)
    lines = ["| termo | " + " | ".join(f"{c} (média/dia · total)" for c in cols) + " |",
             "|---|" + "---|" * len(cols)]
    for q in QUERIES:
        cells = []
        for c in cols:
            vals = [by[(d, q)] for d in groups[c] if (d, q) in by]
            cells.append(f"{sum(vals) / len(vals):.1f} · {sum(vals)}" if vals else "—")
        lines.append(f"| {q} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bluesky")
    b.add_argument("--start", type=date.fromisoformat, required=True)
    b.add_argument("--end", type=date.fromisoformat, required=True)
    b.add_argument("--verify", action="store_true")
    sub.add_parser("summary")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # a URL da paginação traz o cursor (com DID)
    if args.cmd == "bluesky":
        run_bluesky(args.start, args.end, args.verify)
    else:
        print(summary())


if __name__ == "__main__":
    main()
