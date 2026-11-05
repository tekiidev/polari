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
import time
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path

import httpx

from pipeline.config import ROOT, settings
from pipeline.study.windows import EVENTS, PERIODS, TZ, period_of

log = logging.getLogger("feasibility")

OUT_DIR = ROOT / "docs" / "feasibility"
BSKY = "https://bsky.social/xrpc"

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


def day_bounds_utc(d: date) -> tuple[str, str]:
    """[00:00, 24:00) do dia local, em UTC ISO (o que a API espera)."""
    start = datetime.combine(d, dtime(0), TZ).astimezone(timezone.utc)
    end = datetime.combine(d + timedelta(days=1), dtime(0), TZ).astimezone(timezone.utc)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return start.strftime(fmt), end.strftime(fmt)


class Bluesky:
    def __init__(self) -> None:
        self.client = httpx.Client(timeout=30)
        self._login()

    def _login(self) -> None:
        r = self.client.post(f"{BSKY}/com.atproto.server.createSession",
                             json={"identifier": settings.bluesky_handle,
                                   "password": settings.bluesky_app_password})
        r.raise_for_status()
        self.client.headers["Authorization"] = f"Bearer {r.json()['accessJwt']}"

    def search(self, params: dict) -> dict:
        for attempt in range(6):
            r = self.client.get(f"{BSKY}/app.bsky.feed.searchPosts", params=params)
            if r.status_code == 200:
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

    def hits(self, q: str, d: date) -> int:
        since, until = day_bounds_utc(d)
        data = self.search({"q": q, "lang": "pt", "since": since, "until": until, "limit": 1})
        return int(data.get("hitsTotal") or 0)

    def paginate_count(self, q: str, d: date) -> int:
        since, until = day_bounds_utc(d)
        params = {"q": q, "lang": "pt", "since": since, "until": until, "limit": 100}
        uris: set[str] = set()
        while True:
            data = self.search(params)
            posts = data.get("posts", [])
            uris |= {p["uri"] for p in posts}  # só em memória, para deduplicar
            if not posts or not data.get("cursor"):
                return len(uris)
            params["cursor"] = data["cursor"]
            time.sleep(0.5)


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
            time.sleep(0.3)
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
