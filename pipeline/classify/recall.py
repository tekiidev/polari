"""Recall do pré-filtro medido contra rótulos humanos, com amostra estratificada.

    python -m pipeline.classify.recall sample --start 2026-06-01 --end 2026-11-04
    (rotule a coluna `is_political_violence` em eval/labeled_private/prefilter_sample.csv)
    python -m pipeline.classify.recall report

Rótulos (eval/labeling_guide.md): 1 = violência política no Brasil (ou envolvendo brasileiros);
2 = violência política pelos mesmos critérios, em outro país; 3 = violência verbal política
(xingamento sem ameaça) no Brasil; 0 = não é. O recall sai para cada definição de `DEFINITIONS`:
a série padrão usa só 1; as outras mostram o peso da ofensa verbal e dos casos de fora.

Estratos = família da consulta que trouxe o item × aprovado/barrado pelo pré-filtro. A família de
um item trazido por várias consultas é a primeira de `PRIORITY` (violência antes de contexto).

Rotulagem cega: o CSV a rotular tem só item_id e texto; o estrato fica em `prefilter_strata.csv`.
Saber que o item foi barrado enviesaria o rótulo.

Estimativa: positivos de cada estrato = N_estrato × proporção rotulada; recall = positivos
aprovados / positivos totais. Intervalo de credibilidade de 90% por Monte Carlo, com Beta de
Jeffreys (k + ½, n − k + ½) em cada estrato. Em estrato grande com poucos rótulos (barrado do
contexto) o intervalo fica largo: o relatório mostra isso em vez de esconder.

Limite: mede o recall do pré-filtro SOBRE o que as consultas trouxeram. O recall das próprias
consultas não se mede pelo Bluesky (não sabemos o que ficou fora delas).
"""
from __future__ import annotations

import argparse
import csv
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import numpy as np

from pipeline.classify.prefilter import prefilter_rules
from pipeline.config import ROOT
from pipeline.ingest.queries import FAMILIES, family_of
from pipeline.storage import RawStore

PRIVATE = ROOT / "eval" / "labeled_private"
SAMPLE = PRIVATE / "prefilter_sample.csv"
STRATA = PRIVATE / "prefilter_strata.csv"
POPULATION = PRIVATE / "prefilter_population.csv"
PRIORITY = ["cargo", "evento", "espectro", "contexto"]
# Itens por estrato. O barrado do contexto recebe mais: é o maior estrato e onde um erro pesa mais.
DEFAULT_SIZES = {"aprovado": 15, "barrado": 20, ("contexto", "barrado"): 50}
SEED = 2026


def primary_family(queries: list[str]) -> str:
    fams = {family_of(q) for q in queries if any(q in qs for qs in FAMILIES.values())}
    return next((f for f in PRIORITY if f in fams), "contexto")


def stratum_of(queries: list[str], text: str) -> tuple[str, str, set[str]]:
    rules = prefilter_rules(text, queries)
    return primary_family(queries), "aprovado" if rules else "barrado", rules


def size_for(family: str, status: str) -> int:
    return DEFAULT_SIZES.get((family, status), DEFAULT_SIZES[status])


def sample(store: RawStore, start: date, end: date, seed: int = SEED) -> dict[tuple[str, str], int]:
    """Sorteia os itens a rotular. Devolve o tamanho de cada estrato na população."""
    pools: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
    for item in store.iter_items("bluesky", start, end):
        fam, status, rules = stratum_of(item.queries, item.text)
        pools[(fam, status)].append((item.item_id, item.text, "|".join(sorted(rules))))
    rng = random.Random(seed)
    chosen = []
    for key in sorted(pools):
        pool = sorted(pools[key])  # ordem estável antes de sortear: reprodutível com a mesma semente
        for item_id, text, rules in rng.sample(pool, min(size_for(*key), len(pool))):
            chosen.append((item_id, text, *key, rules))
    rng.shuffle(chosen)  # mistura os estratos no arquivo a rotular
    PRIVATE.mkdir(parents=True, exist_ok=True)
    with SAMPLE.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "text", "is_political_violence"])
        w.writerows((c[0], c[1], "") for c in chosen)
    with STRATA.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "family", "status", "rules"])
        w.writerows((c[0], c[2], c[3], c[4]) for c in chosen)
    sizes = {k: len(v) for k, v in pools.items()}
    with POPULATION.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["family", "status", "n"])
        w.writerows((*k, n) for k, n in sorted(sizes.items()))
    return sizes


def estimate(population: dict[tuple[str, str], int], labels: dict[tuple[str, str], tuple[int, int]],
             draws: int = 20_000, seed: int = SEED) -> dict:
    """Recall estimado e intervalo de 90%. `labels[estrato] = (positivos, rotulados)`."""
    rng = np.random.default_rng(seed)
    pos = {"aprovado": np.zeros(draws), "barrado": np.zeros(draws)}
    point = {"aprovado": 0.0, "barrado": 0.0}
    for key, n_pop in population.items():
        k, n = labels.get(key, (0, 0))
        status = key[1]
        pos[status] += n_pop * rng.beta(k + 0.5, n - k + 0.5, draws)
        point[status] += n_pop * (k / n if n else 0.0)
    recall = pos["aprovado"] / (pos["aprovado"] + pos["barrado"])
    total = point["aprovado"] + point["barrado"]
    return {"recall": point["aprovado"] / total if total else float("nan"),
            "low": float(np.quantile(recall, 0.05)), "high": float(np.quantile(recall, 0.95)),
            "positives_passed": point["aprovado"], "positives_blocked": point["barrado"]}


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


DEFINITIONS = {"Brasil, sem ofensa verbal": {1}, "Brasil, com ofensa verbal": {1, 3},
               "qualquer país, com ofensa verbal": {1, 2, 3}}


def report() -> str:
    labels_by_id = {r["item_id"]: r["is_political_violence"].strip() for r in _read_csv(SAMPLE)}
    strata = {r["item_id"]: r for r in _read_csv(STRATA)}
    population = {(r["family"], r["status"]): int(r["n"]) for r in _read_csv(POPULATION)}
    counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
    by_rule: dict[str, Counter] = defaultdict(Counter)
    missing = 0
    for item_id, value in labels_by_id.items():
        if value not in {"0", "1", "2", "3"}:
            missing += 1
            continue
        s, y = strata[item_id], int(value)
        counts[(s["family"], s["status"])][y] += 1
        for rule in filter(None, s["rules"].split("|")):
            by_rule[rule][y] += 1
    lines = [f"Itens rotulados: {sum(sum(c.values()) for c in counts.values())} (sem rótulo: {missing})", "",
             "| família | status | população | rotulados | 1 (Brasil) | 2 (outro país) | 3 (verbal) |",
             "|---|---|---|---|---|---|---|"]
    for key in sorted(population):
        c = counts.get(key, Counter())
        lines.append(f"| {key[0]} | {key[1]} | {population[key]} | {sum(c.values())} | {c[1]} | {c[2]} | {c[3]} |")
    lines.append("")
    for name, positive in DEFINITIONS.items():
        labels = {k: (sum(c[v] for v in positive), sum(c.values())) for k, c in counts.items()}
        est = estimate(population, labels)
        lines += [f"**Recall ({name}):** {est['recall']:.1%} (intervalo de 90%: {est['low']:.1%} a {est['high']:.1%}); "
                  f"positivos estimados: {est['positives_passed']:.0f} aprovados, {est['positives_blocked']:.0f} barrados."]
    lines += ["", "Por regra, entre os aprovados rotulados (1 / 2 / 3 / total):", ""]
    for rule, c in sorted(by_rule.items()):
        lines.append(f"- `{rule}`: {c[1]} / {c[2]} / {c[3]} / {sum(c.values())}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--start", type=date.fromisoformat, required=True)
    s.add_argument("--end", type=date.fromisoformat, required=True)
    sub.add_parser("report")
    args = ap.parse_args()
    if args.cmd == "sample":
        sizes = sample(RawStore(), args.start, args.end)
        for k, n in sorted(sizes.items()):
            print(f"{k[0]:9} {k[1]:8} {n:7d}  -> sorteados {min(size_for(*k), n)}")
        print(f"\nRotule: {SAMPLE}")
    else:
        print(report())


if __name__ == "__main__":
    main()
