"""Consultas ao Bluesky, por família. A própria consulta é um filtro: post que nenhuma consulta
traz não chega ao pré-filtro nem ao classificador. O recall que importa é o de consulta + pré-filtro.

Como a busca do Bluesky se comporta (medido em 05/11/2026):
  - AND entre as palavras; aspas quase não mudam o resultado ("bala de borracha": 68 × 69);
  - ignora acento ("eleicao" = "eleição"), mas NÃO faz stemming: "vereadora assassinada" (13)
    não acha "vereadora assassinado" (3). Por isso feminino e masculino aparecem separados;
  - `hitsTotal` trava em 10.000.

Famílias (escopo em eval/labeling_guide.md):
  - contexto: denominador eleitoral, os mesmos termos da Fase 1, para comparar com docs/feasibility.md;
  - cargo: cargo político + violência, sem palavra eleitoral ("Vereadora foi morta a tiros");
  - evento: ato/manifestação + agressão ou repressão policial;
  - espectro: identificação política + agressão, inclusive casos isolados ("bolsonarista mata petista").

Pares com volume desprezível ou só ruído saem depois da medição (`python -m pipeline.ingest.queries`).
"""
from __future__ import annotations

from itertools import product

CONTEXT = ["eleição", "eleições", "candidato", "voto"]

_ROLES_F = ["vereadora", "prefeita", "deputada", "candidata"]
_ROLES_M = ["vereador", "prefeito", "deputado", "candidato"]
_HARM = ["assassinad{}", "mort{}", "balead{}", "esfaquead{}", "agredid{}", "ameaçad{}", "atacad{}"]
ROLE = ([f"{r} {h.format('a')}" for r, h in product(_ROLES_F, _HARM)]
        + [f"{r} {h.format('o')}" for r, h in product(_ROLES_M, _HARM)]
        + [f"{r} tiros" for r in _ROLES_F + _ROLES_M])

_EVENTS = ["ato", "manifestação", "protesto", "passeata", "carreata", "comício"]
_AGGRESSION = ["agredido", "agredida", "agredidos", "pancadaria", "confronto", "briga", "espancado",
               "feridos", "bala de borracha", "spray de pimenta", "bomba de gás", "polícia reprime",
               "repressão"]
EVENT = [f"{e} {a}" for e, a in product(_EVENTS, _AGGRESSION)]

_SIDES = ["petista", "bolsonarista", "lulista", "esquerdista", "de esquerda", "de direita",
          "camisa do PT", "camisa do Bolsonaro"]
_ACTS = ["matou", "mata", "assassinado", "espancado", "agredido", "agride", "esfaqueado", "ameaçado"]
SPECTRUM = ([f"{s} {a}" for s, a in product(_SIDES, _ACTS)]
            + ["discussão política morto", "discussão política matou", "briga política morto",
               "motivação política crime", "por causa de política agredido", "por política matou"])

FAMILIES: dict[str, list[str]] = {"contexto": CONTEXT, "cargo": ROLE, "evento": EVENT, "espectro": SPECTRUM}


def family_of(query: str) -> str:
    for name, qs in FAMILIES.items():
        if query in qs:
            return name
    raise KeyError(query)


def all_queries() -> list[str]:
    return [q for qs in FAMILIES.values() for q in qs]


def main() -> None:
    """Mede o volume de cada consulta no período inteiro (1 requisição por consulta)."""
    import argparse
    import csv
    import sys
    from datetime import date

    from pipeline.ingest.bluesky import BlueskyClient
    from pipeline.study.windows import day_bounds

    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=date.fromisoformat, default=date(2026, 6, 1))
    ap.add_argument("--end", type=date.fromisoformat, required=True)
    args = ap.parse_args()
    client = BlueskyClient()
    since, until = day_bounds(args.start)[0], day_bounds(args.end)[1]
    w = csv.writer(sys.stdout)
    w.writerow(["family", "query", "hits_total"])
    for name, qs in FAMILIES.items():
        for q in qs:
            w.writerow([name, q, client.hits(q, since, until)])


if __name__ == "__main__":
    main()
