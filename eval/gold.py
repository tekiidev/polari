"""Gabarito humano de 200 itens: sorteio, rotulagem no terminal e congelamento.

    python -m eval.gold sample            # sorteia os 200 itens a rotular
    python -m eval.gold label             # rotula no terminal (retomável)
    python -m eval.gold status            # quanto falta, por estrato
    python -m eval.gold freeze            # congela e imprime o SHA-256
    python -m eval.gold review            # revisão cega da errata de 12/11 (retomável)
    python -m eval.gold errata            # registra a errata: hash novo, anterior no histórico

O gabarito é a régua de tudo (CLAUDE.md). Três decisões que o protegem:

1. **Separado do desenvolvimento.** Os 147 itens da Fase 2 (`prefilter_sample.csv`) ficam para
   ajustar o prompt; nenhum deles entra aqui. Ajustar o prompt no mesmo conjunto em que se mede o
   F1 produz número otimista.
2. **Inclui itens barrados pelo pré-filtro.** Sem isso o recall do pré-filtro só pode ser medido
   na amostra usada para corrigi-lo, que é o viés declarado em `docs/prefilter.md`.
3. **Rotulagem cega.** O arquivo a rotular não diz período nem se o item foi aprovado: saber
   enviesaria o rótulo. Os estratos ficam em `gold_strata.csv`.

Códigos (`eval/labeling_guide.md`): 0 não é; 1 Brasil; 2 outro país; 3 violência verbal no Brasil.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from pipeline.classify.prefilter import prefilter_rules
from pipeline.config import ROOT
from pipeline.storage import RawStore
from pipeline.study.windows import local_day, period_of

PRIVATE = ROOT / "eval" / "labeled_private"
GOLD = PRIVATE / "gold.jsonl"
STRATA = PRIVATE / "gold_strata.csv"
DEV_SAMPLE = PRIVATE / "prefilter_sample.csv"
FROZEN = ROOT / "eval" / "gold.frozen.json"  # só o hash e as contagens: vai para o git

SEED = 20261110
VALID_CODES = {0, 1, 2, 3}

# 200 itens. Aprovados dominam porque são a entrada real do classificador (18.145 itens); os
# barrados existem para medir o recall do pré-filtro sem viés, e 60 é o mínimo para um intervalo
# que signifique algo. Dentro de cada status, divide-se por período para a régua não ficar colada
# a um momento da eleição.
SIZES: dict[tuple[str, str], int] = {
    ("baseline", "aprovado"): 30,
    ("campanha_1t", "aprovado"): 40,
    ("entre_turnos", "aprovado"): 40,
    ("pos_eleicao", "aprovado"): 30,
    ("baseline", "barrado"): 15,
    ("campanha_1t", "barrado"): 15,
    ("entre_turnos", "barrado"): 15,
    ("pos_eleicao", "barrado"): 15,
}


def dev_ids() -> set[str]:
    """IDs já usados no conjunto de desenvolvimento: nunca entram no gabarito."""
    if not DEV_SAMPLE.exists():
        return set()
    with DEV_SAMPLE.open(encoding="utf-8") as f:
        return {row["item_id"] for row in csv.DictReader(f)}


def sample(store: RawStore, start: date, end: date, seed: int = SEED) -> None:
    excluded = dev_ids()
    pools: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for item in store.iter_items("bluesky", start, end):
        if item.item_id in excluded:
            continue
        period = period_of(local_day(item.created_at))
        if period is None:
            continue
        status = "aprovado" if prefilter_rules(item.text, item.queries) else "barrado"
        pools.setdefault((period, status), []).append((item.item_id, item.text))

    rng = random.Random(seed)
    chosen: list[tuple[str, str, str, str]] = []
    for key in sorted(SIZES):
        pool = sorted(pools.get(key, []))  # ordem estável: o sorteio é reprodutível
        want = SIZES[key]
        if len(pool) < want:
            print(f"aviso: estrato {key} tem {len(pool)} itens, menos que os {want} pedidos")
        for item_id, text in rng.sample(pool, min(want, len(pool))):
            chosen.append((item_id, text, *key))
    rng.shuffle(chosen)  # mistura os estratos: a ordem não insinua o rótulo

    PRIVATE.mkdir(parents=True, exist_ok=True)
    with GOLD.open("w", encoding="utf-8") as f:
        for item_id, text, _period, _status in chosen:
            f.write(json.dumps({"item_id": item_id, "text": text, "label": None},
                               ensure_ascii=False) + "\n")
    with STRATA.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "period", "prefilter_status"])
        for item_id, _text, period, status in chosen:
            w.writerow([item_id, period, status])
    print(f"{len(chosen)} itens em {GOLD}")
    print(f"estratos (não abra antes de rotular): {STRATA}")


def read_gold() -> list[dict]:
    if not GOLD.exists():
        raise SystemExit(f"{GOLD} não existe. Rode: python -m eval.gold sample")
    with GOLD.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_gold(rows: list[dict]) -> None:
    tmp = GOLD.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(GOLD)  # troca atômica: Ctrl-C no meio não corrompe o que já foi rotulado


GUIA = """\
0 = não é violência política
1 = violência política no Brasil
2 = violência política em outro país (mesma régua)
3 = violência verbal no Brasil (xingamento a quem tem papel político, sem ameaça)

d = difícil (marca para revisar depois, sem rótulo)   v = voltar   s = salvar e sair
Dúvida sobre a régua: eval/labeling_guide.md. Na dúvida entre dois códigos, use o mais grave.
"""


def label() -> None:
    """Rotula no terminal, uma vez por item, retomável. Salva a cada rótulo."""
    rows = read_gold()
    print(GUIA)
    i = 0
    while i < len(rows):
        row = rows[i]
        if row.get("label") is not None:
            i += 1
            continue
        done = sum(1 for r in rows if r.get("label") is not None)
        print("─" * 72)
        print(f"item {i + 1}/{len(rows)}  ·  {done} rotulados  ·  {len(rows) - done} restantes")
        print("─" * 72)
        print(row["text"])
        print("─" * 72)
        answer = input("rótulo [0/1/2/3/d/v/s]: ").strip().lower()

        if answer == "s":
            write_gold(rows)
            print(f"salvo. {done} rotulados. Retome com: python -m eval.gold label")
            return
        if answer == "v":
            # Volta ao item rotulado anterior e limpa o rótulo, para corrigir.
            j = next((k for k in range(i - 1, -1, -1) if rows[k].get("label") is not None), None)
            if j is None:
                print("não há item anterior rotulado.")
                continue
            rows[j]["label"] = None
            rows[j].pop("hard", None)
            i = j
            continue
        if answer == "d":
            row["hard"] = True
            print("marcado como difícil; rotule agora com 0-3 (o 'difícil' fica registrado).")
            continue
        if answer.isdigit() and int(answer) in VALID_CODES:
            row["label"] = int(answer)
            row["labeled_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            write_gold(rows)
            i += 1
            continue
        print(f"resposta inválida: {answer!r}")

    write_gold(rows)
    print(f"completo: {len(rows)} itens rotulados. Congele com: python -m eval.gold freeze")


# Pistas de que um item rotulado `0` pode ter virado `1` com a regra "afirmação basta"
# (guia, 10/11): o texto afirma ou discute violência política sem descrever um ato.
REVISION_HINTS = [
    "ameaç", "ameac", "perseguiç", "perseguic", "intimidaç", "intimidac",
    "violência polít", "violencia polit", "violência elei", "violencia elei",
    "interfer", "ingerênc", "ingerenc", "soberania",
    "sofrendo", "sofrem", "vítima", "vitima", "atacad", "hostiliz",
    "pesquisa", "relatório", "relatorio", "levantamento", "dados mostram",
]


def revise(reason: str = "afirmação basta (10/11)") -> None:
    """Revisa só os itens cuja régua mudou, em vez de rotular 200 de novo.

    Mostra os itens marcados `0` cujo texto tem pista da regra nova. Enter mantém o rótulo;
    1/2/3 troca. O que não casa com nenhuma pista não é mostrado: a regra não o afeta.
    """
    rows = read_gold()
    pending = [
        (i, r) for i, r in enumerate(rows)
        if r.get("label") == 0 and any(h in r["text"].lower() for h in REVISION_HINTS)
    ]
    if not pending:
        print("nenhum item `0` com pista da regra nova. Nada a revisar.")
        return

    print(f"{len(pending)} de {len(rows)} itens a revisar (motivo: {reason}).")
    print("Enter mantém o 0. Digite 1/2/3 para trocar. 's' sai e salva.\n")
    changed = 0
    for n, (idx, row) in enumerate(pending, 1):
        print("─" * 72)
        print(f"revisão {n}/{len(pending)}  ·  rótulo atual: 0")
        print("─" * 72)
        print(row["text"])
        print("─" * 72)
        answer = input("novo rótulo [Enter=mantém 0 / 1 / 2 / 3 / s]: ").strip().lower()
        if answer == "s":
            break
        if answer == "":
            continue
        if answer.isdigit() and int(answer) in VALID_CODES:
            rows[idx]["label"] = int(answer)
            rows[idx]["revised_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            rows[idx]["revision_reason"] = reason
            write_gold(rows)
            changed += 1
        else:
            print(f"resposta inválida: {answer!r} — mantido 0")
    print(f"\n{changed} rótulos alterados. Confira: python -m eval.gold status")


# Errata de 12/11/2026. Critérios tirados das exclusões **escritas** do guia, aplicados aos 200 itens
# com qualquer rótulo, sem consultar previsão de modelo. Origem declarada: foram formulados depois de
# ler os falsos negativos do `gpt-5.4-mini` no gabarito — por isso valem para todos os itens, e não
# só para os que o modelo errou, e não há critério feito sob medida para um caso isolado.
ERRATA_ID = "errata-2026-11-12"
ERRATA_RULES = {
    # Guia, regra de interferência: "Empresas e plataformas não entram aqui."
    "plataforma": r"big ?techs?|\bmeta\b|plataformas?|\bx corp|twitter|\bgoogle|tiktok|whatsapp"
                  r"|telegram|facebook|instagram",
    # Guia: interferência conta quando um **Estado estrangeiro** interfere e o texto afirma isso.
    # "Interferir nas eleições" dito de ator doméstico, ou como especulação, não é essa regra.
    "interferencia": r"interf[eê]r|ingerênc|ingerenc|soberan|\btrump|\beua\b|estados unidos|tarifa"
                     r"|sanç|sanc[oõ]|magnitsky|embaixad",
    # Guia, "O que não entra": fraude, corrupção e desinformação sem violência são outro fenômeno.
    "fora_do_escopo": r"corrup|fraud|propina|rachadinh|lavagem|desvio|emendas?\b|desinforma"
                      r"|fake ?news",
}

ERRATA_GUIDE = """\
Revisão cega (errata de 12/11). Você vê só o texto: nem o rótulo atual, nem o de nenhum modelo.
Aplique o guia escrito (eval/labeling_guide.md), em especial:

  • Interferência estrangeira conta quando o texto AFIRMA que um GOVERNO ou ESTADO de outro país
    interfere na política brasileira. Opinião sobre o tema, especulação, ou "interferir nas
    eleições" dito de ator brasileiro (ministro, juiz, partido) não é essa regra.
  • Empresas e plataformas (Meta, X, big techs) NÃO entram na interferência.
  • Fraude, corrupção, desinformação e "a eleição foi roubada" sem violência: 0.
  • Continua valendo: afirmação basta; o cargo de quem comete basta; simetria.

0 / 1 / 2 / 3 = rótulo   d = não sei (mantém o rótulo atual e marca difícil)   s = salvar e sair
"""


def errata_candidates(rows: list[dict]) -> list[tuple[int, list[str]]]:
    """Índices dos itens que algum critério da errata alcança, com os nomes dos critérios."""
    out = []
    for i, r in enumerate(rows):
        low = r["text"].lower()
        hits = [name for name, pattern in ERRATA_RULES.items() if re.search(pattern, low)]
        if hits:
            out.append((i, hits))
    return out


def apply_review(row: dict, answer: str, now: str) -> bool:
    """Aplica uma resposta da revisão cega a um item. Devolve se o rótulo mudou.

    Guarda o rótulo anterior em `previous_label`: a errata precisa poder ser desfeita e auditada.
    `d` mantém o rótulo atual — na dúvida, o julgamento original fica.
    """
    row.setdefault("errata", {})[ERRATA_ID] = now
    if answer == "d":
        row["hard"] = True
        return False
    new = int(answer)
    if new == row["label"]:
        return False
    row["previous_label"] = row["label"]
    row["label"] = new
    row["revised_at"] = now
    row["revision_reason"] = f"{ERRATA_ID}: reaplicação do guia escrito"
    return True


def review() -> None:
    """Rerrotula às cegas os itens que os critérios da errata alcançam. Retomável."""
    rows = read_gold()
    pending = [
        (i, hits) for i, hits in errata_candidates(rows)
        if ERRATA_ID not in rows[i].get("errata", {})
    ]
    total = len(errata_candidates(rows))
    if not pending:
        print(f"revisão completa ({total} itens). Registre com: python -m eval.gold errata")
        return
    print(ERRATA_GUIDE)
    print(f"{len(pending)} de {total} itens a revisar.\n")
    changed = 0
    for n, (idx, _hits) in enumerate(pending, 1):
        print("─" * 72)
        print(f"item {total - len(pending) + n}/{total}")
        print("─" * 72)
        print(rows[idx]["text"])
        print("─" * 72)
        while True:
            answer = input("rótulo [0/1/2/3, d, s]: ").strip().lower()
            if answer == "s" or answer == "d" or (answer.isdigit() and int(answer) in VALID_CODES):
                break
            print(f"resposta inválida: {answer!r}")
        if answer == "s":
            break
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        changed += apply_review(rows[idx], answer, now)
        write_gold(rows)
    print(f"\n{changed} rótulos alterados nesta sessão.")
    print("Ao terminar todos: python -m eval.gold errata")


def errata() -> None:
    """Congela o gabarito revisado, guardando o hash anterior e o que mudou.

    O `eval/run.py` passa a aceitar o hash novo; o antigo fica em `history`, com data e motivo, e os
    resultados de antes continuam reproduzíveis com `eval.metrics --original-gold`.
    """
    rows = read_gold()
    candidates = errata_candidates(rows)
    unreviewed = [i for i, _ in candidates if ERRATA_ID not in rows[i].get("errata", {})]
    if unreviewed:
        raise SystemExit(f"{len(unreviewed)} itens da errata ainda não revisados: python -m eval.gold review")
    if not FROZEN.exists():
        raise SystemExit("não há congelamento anterior: use freeze, não errata.")

    previous = json.loads(FROZEN.read_text(encoding="utf-8"))
    digest = gold_hash(rows)
    if digest == previous["sha256"]:
        print("nenhum rótulo mudou: o hash é o mesmo, nada a registrar.")
        return
    transitions = Counter(
        f"{r['previous_label']}→{r['label']}" for r in rows
        if ERRATA_ID in r.get("revision_reason", "")
    )
    counts = Counter(r["label"] for r in rows)
    history = previous.pop("history", [])
    history.append(previous)
    FROZEN.write_text(
        json.dumps(
            {
                "sha256": digest,
                "n": len(rows),
                "by_code": {str(c): counts.get(c, 0) for c in sorted(VALID_CODES)},
                "hard": sum(1 for r in rows if r.get("hard")),
                "frozen_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "errata": {
                    "id": ERRATA_ID,
                    "reviewed": len(candidates),
                    "changed": sum(transitions.values()),
                    "transitions": dict(sorted(transitions.items())),
                    "rules": sorted(ERRATA_RULES),
                    "reason": "reaplicação cega do guia escrito a itens de interferência, "
                              "plataforma e fora do escopo; ver docs/eval-llm.md",
                },
                "note": "Hash de (item_id, label). Texto e rótulos ficam fora do git.",
                "history": history,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"SHA-256 novo: {digest}")
    print(f"anterior:     {previous['sha256']}  (guardado em history)")
    print(f"{sum(transitions.values())} de {len(candidates)} revisados mudaram: "
          + ", ".join(f"{k} ×{v}" for k, v in sorted(transitions.items())))


def status() -> None:
    rows = read_gold()
    labeled = [r for r in rows if r.get("label") is not None]
    print(f"{len(labeled)}/{len(rows)} rotulados ({len(rows) - len(labeled)} restantes)")
    if labeled:
        counts = Counter(r["label"] for r in labeled)
        print("por código: " + "  ".join(f"{c}={counts.get(c, 0)}" for c in sorted(VALID_CODES)))
        hard = sum(1 for r in labeled if r.get("hard"))
        print(f"marcados como difíceis: {hard}")
        if not STRATA.exists():
            return
        with STRATA.open(encoding="utf-8") as f:
            strata = {row["item_id"]: row for row in csv.DictReader(f)}
        by_stratum: Counter[tuple[str, str]] = Counter()
        for r in labeled:
            s = strata.get(r["item_id"])
            if s:
                by_stratum[(s["period"], s["prefilter_status"])] += 1
        print("\nrotulados por estrato (só depois de rotular, para não enviesar):")
        for key in sorted(SIZES):
            print(f"  {key[0]:<14} {key[1]:<9} {by_stratum.get(key, 0):>3}/{SIZES[key]}")


def gold_hash(rows: list[dict]) -> str:
    """Hash do conteúdo que importa: id e rótulo, em ordem de id.

    Não inclui o texto (que não muda) nem o horário da rotulagem (que muda sem mudar a régua).
    """
    payload = json.dumps(
        [[r["item_id"], r["label"]] for r in sorted(rows, key=lambda r: r["item_id"])],
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def freeze() -> None:
    rows = read_gold()
    missing = [r for r in rows if r.get("label") is None]
    if missing:
        raise SystemExit(f"{len(missing)} itens sem rótulo. Congele só o gabarito completo.")
    digest = gold_hash(rows)
    counts = Counter(r["label"] for r in rows)
    FROZEN.write_text(
        json.dumps(
            {
                "sha256": digest,
                "n": len(rows),
                "by_code": {str(c): counts.get(c, 0) for c in sorted(VALID_CODES)},
                "hard": sum(1 for r in rows if r.get("hard")),
                "frozen_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "note": "Hash de (item_id, label). Texto e rótulos ficam fora do git.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"SHA-256: {digest}")
    print(f"registrado em {FROZEN} (este arquivo vai para o git)")
    print("Anote o hash em docs/decisions/escolha-llm.md antes de rodar qualquer modelo.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="sorteia os itens a rotular")
    s.add_argument("--start", type=date.fromisoformat, default=date(2026, 6, 1))
    s.add_argument("--end", type=date.fromisoformat, default=date(2026, 11, 4))
    sub.add_parser("label", help="rotula no terminal (retomável)")
    sub.add_parser("revise", help="revisa só os itens afetados por mudança de régua")
    sub.add_parser("status", help="progresso por código e por estrato")
    sub.add_parser("freeze", help="congela e imprime o SHA-256")
    sub.add_parser("review", help="revisão cega dos itens da errata (retomável)")
    sub.add_parser("errata", help="registra a errata com o hash anterior no histórico")
    args = parser.parse_args()

    if args.cmd == "sample":
        sample(RawStore(), args.start, args.end)
    elif args.cmd == "label":
        label()
    elif args.cmd == "revise":
        revise()
    elif args.cmd == "status":
        status()
    elif args.cmd == "review":
        review()
    elif args.cmd == "errata":
        errata()
    else:
        freeze()


if __name__ == "__main__":
    main()
