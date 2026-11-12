"""Recall do pré-filtro medido sem viés, a partir dos itens barrados do gabarito.

    python -m eval.prefilter_recall population   # conta a população por período × status
    python -m eval.prefilter_recall report       # a estimativa e a tabela

A medição da Fase 2 (`docs/prefilter.md`) é otimista e o documento diz por quê: os 62% foram
calculados na **mesma** amostra que serviu para corrigir o pré-filtro. Corrigir o filtro com os
erros de uma amostra e depois medir nela é medir o ajuste, não o filtro.

Esta medição não tem esse problema. O gabarito da Fase 3 foi sorteado depois de o pré-filtro estar
congelado, inclui 60 itens **barrados** de propósito, e foi rotulado às cegas: quem rotulou não
sabia se o item havia passado ou não (`eval/gold.py`, `gold_strata.csv` separado).

A estratificação aqui é por **período** (baseline, campanha do 1º turno, entre turnos, pós-eleição),
não por família de consulta como na Fase 2. Os dois recortes respondem perguntas diferentes e
nenhum substitui o outro: por família diz qual consulta alimenta o filtro, por período diz se ele
falha mais em algum momento da eleição — que é o que importa para uma série temporal.

A estatística é a mesma da Fase 2 (`pipeline.classify.recall.estimate`): os positivos de cada
estrato são a população vezes a proporção rotulada, e o intervalo de 90% vem de Monte Carlo com
Beta de Jeffreys por estrato. Reaproveitada de propósito — dois estimadores diferentes para o
mesmo número dariam uma diferença impossível de atribuir.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date

from eval.gold import STRATA, read_gold
from pipeline.classify.prefilter import prefilter_rules
from pipeline.classify.recall import DEFINITIONS, estimate
from pipeline.config import ROOT, settings
from pipeline.storage import RawStore
from pipeline.study.windows import local_day, period_of

POPULATION = ROOT / "eval" / "labeled_private" / "gold_population.csv"
PERIODS = ("baseline", "campanha_1t", "entre_turnos", "pos_eleicao")


def count_population(start: date, end: date) -> dict[tuple[str, str], int]:
    """Itens da população em cada período × status, para ponderar os estratos.

    Sem isso o recall sairia de 78/(78+5): os 60 barrados representam centenas de milhares de
    itens e os 140 aprovados representam alguns milhares, então contá-los lado a lado
    superestimaria o recall por uma ordem de magnitude.
    """
    store = RawStore(settings.raw_dir)
    counts: Counter[tuple[str, str]] = Counter()
    for item in store.iter_items("bluesky", start, end):
        period = period_of(local_day(item.created_at))
        if period is None:
            continue
        status = "aprovado" if prefilter_rules(item.text, item.queries) else "barrado"
        counts[(period, status)] += 1
    return dict(counts)


def write_population(counts: dict[tuple[str, str], int]) -> None:
    with POPULATION.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["period", "status", "n"])
        w.writerows((*k, n) for k, n in sorted(counts.items()))
    print(f"{sum(counts.values())} itens em {POPULATION}")


def read_population() -> dict[tuple[str, str], int]:
    if not POPULATION.exists():
        raise SystemExit(
            f"{POPULATION} não existe. Rode: python -m eval.prefilter_recall population"
        )
    with POPULATION.open(encoding="utf-8", newline="") as f:
        return {(r["period"], r["status"]): int(r["n"]) for r in csv.DictReader(f)}


def read_strata() -> dict[str, tuple[str, str]]:
    if not STRATA.exists():
        raise SystemExit(f"{STRATA} não existe: sem o estrato não há como ponderar.")
    with STRATA.open(encoding="utf-8", newline="") as f:
        return {r["item_id"]: (r["period"], r["prefilter_status"]) for r in csv.DictReader(f)}


def labels_by_stratum(codes: set[int]) -> dict[tuple[str, str], tuple[int, int]]:
    """`{estrato: (positivos, rotulados)}` para o conjunto de códigos que conta como positivo."""
    strata = read_strata()
    out: dict[tuple[str, str], list[int]] = {}
    for row in read_gold():
        key = strata.get(row["item_id"])
        if key is None:
            continue
        acc = out.setdefault(key, [0, 0])
        acc[1] += 1
        if row["label"] in codes:
            acc[0] += 1
    return {k: (v[0], v[1]) for k, v in out.items()}


def report() -> str:
    population = read_population()
    strata = read_strata()
    gold = {r["item_id"]: r["label"] for r in read_gold()}

    lines = ["# Recall do pré-filtro sem viés (gabarito da Fase 3)", ""]
    lines.append(f"Gabarito: {len(gold)} itens, {sum(1 for i in strata.values() if i[1] == 'barrado')}"
                 " barrados de propósito, rotulados às cegas.")
    lines.append("")
    lines.append("| período | status | população | rotulados | `1` | `2` | `3` |")
    lines.append("|---|---|---|---|---|---|---|")
    for key in sorted(population):
        counts: Counter[int] = Counter(
            gold[i] for i, s in strata.items() if s == key and i in gold
        )
        total = sum(counts.values())
        lines.append(
            f"| {key[0]} | {key[1]} | {population[key]} | {total} "
            f"| {counts[1]} | {counts[2]} | {counts[3]} |"
        )
    lines.append("")

    for name, codes in DEFINITIONS.items():
        labels = labels_by_stratum(codes)
        est = estimate(population, labels)
        lines.append(
            f"- **Recall ({name}):** {est['recall']:.1%} "
            f"({est['low']:.1%} a {est['high']:.1%})"
        )
    lines.append("")

    # Onde o filtro falha importa mais que o número: um recall uniforme só baixa a escala da série,
    # enquanto um recall que varia por período distorce a forma da curva, que é o que o mapa mostra.
    lines.append("## Por período (positivos `1` barrados)")
    lines.append("")
    lines.append("| período | barrados rotulados | positivos | população barrada |")
    lines.append("|---|---|---|---|")
    for period in PERIODS:
        key = (period, "barrado")
        ids = [i for i, s in strata.items() if s == key and i in gold]
        pos = sum(1 for i in ids if gold[i] == 1)
        lines.append(f"| {period} | {len(ids)} | {pos} | {population.get(key, 0)} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    pop = sub.add_parser("population", help="conta a população por período × status")
    pop.add_argument("--from", dest="start", default="2026-06-01")
    pop.add_argument("--to", dest="end", default="2026-11-04")
    sub.add_parser("report", help="estimativa e tabela")
    args = parser.parse_args()

    if args.cmd == "population":
        write_population(
            count_population(date.fromisoformat(args.start), date.fromisoformat(args.end))
        )
    else:
        print(report())


if __name__ == "__main__":
    main()
