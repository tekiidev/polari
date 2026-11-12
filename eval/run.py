"""Roda um backend num conjunto de itens e grava os resultados, um por linha.

    python -m eval.run --backend qwen --set dev            # 147 itens de desenvolvimento
    python -m eval.run --backend gemini --set dev --limit 20   # teste rápido
    python -m eval.run --backend gemini --set gold         # execução única no gabarito
    python -m eval.run --backend qwen --set mirrored       # pares espelhados

Dois conjuntos, nunca misturados (`docs/decisions/escolha-llm.md`):
  - **dev** (147 itens da Fase 2): onde o prompt é ajustado. Pode rodar quantas vezes quiser.
  - **gold** (200 itens congelados): executado uma vez por modelo, depois do congelamento. Este
    script confere o SHA-256 antes de rodar e **recusa** rodar se o gabarito mudou.

Os resultados ficam em `eval/results/<backend>__<set>__<run>.jsonl`, fora do git: eles contêm o
texto bruto da resposta do modelo e precisam do item para serem interpretados.

Retomável: se o arquivo já existe, os itens já classificados são pulados. Cota esgotada no meio não
perde o que já foi feito.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from eval import gold as gold_mod
from pipeline.classify.backends import CANDIDATES, ClassifyResult, classify_one, make_backend
from pipeline.config import ROOT

RESULTS = ROOT / "eval" / "results"
PRIVATE = ROOT / "eval" / "labeled_private"
DEV_SAMPLE = PRIVATE / "prefilter_sample.csv"
MIRRORED = PRIVATE / "mirrored_pairs.jsonl"


def load_dev() -> list[tuple[str, str, int]]:
    """147 itens rotulados na Fase 2: o conjunto de desenvolvimento."""
    if not DEV_SAMPLE.exists():
        raise SystemExit(f"{DEV_SAMPLE} não existe.")
    with DEV_SAMPLE.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for row in rows:
        label = row.get("is_political_violence", "").strip()
        if label == "":
            continue  # item sem rótulo: não serve para comparar
        out.append((row["item_id"], row["text"], int(label)))
    return out


def load_gold() -> list[tuple[str, str, int]]:
    """200 itens congelados. Recusa rodar se o hash não bate com o registrado."""
    rows = gold_mod.read_gold()
    frozen_path = gold_mod.FROZEN
    if not frozen_path.exists():
        raise SystemExit("gabarito não congelado. Rode: python -m eval.gold freeze")
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    current = gold_mod.gold_hash(rows)
    if current != frozen["sha256"]:
        raise SystemExit(
            "O gabarito mudou depois do congelamento.\n"
            f"  registrado: {frozen['sha256']}\n"
            f"  atual:      {current}\n"
            "Rótulo corrigido depois do congelamento exige errata registrada em\n"
            "docs/decisions/escolha-llm.md, com o F1 antes e depois. Não rode em silêncio."
        )
    return [(r["item_id"], r["text"], r["label"]) for r in rows]


def load_mirrored() -> list[tuple[str, str, int]]:
    """Pares espelhados: cada lado vira um item, embaralhados para o modelo não ver o par junto."""
    if not MIRRORED.exists():
        raise SystemExit(f"{MIRRORED} não existe. Rode: python -m eval.mirrored write")
    with MIRRORED.open(encoding="utf-8") as f:
        pairs = [json.loads(line) for line in f if line.strip()]
    items = []
    for p in pairs:
        items.append((f"{p['pair_id']}::a", p["a"], p["label"]))
        items.append((f"{p['pair_id']}::b", p["b"], p["label"]))
    # Ordem alternada A,B,A,B viraria contexto se algum backend mantivesse estado; separa os lados.
    items.sort(key=lambda it: (it[0].split("::")[1], it[0]))
    return items


LOADERS = {"dev": load_dev, "gold": load_gold, "mirrored": load_mirrored}


def result_path(backend: str, dataset: str, run: int) -> Path:
    return RESULTS / f"{backend}__{dataset}__run{run}.jsonl"


def already_done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as f:
        return {json.loads(line)["item_id"] for line in f if line.strip()}


def append_result(path: Path, result: ClassifyResult, gold_label: int) -> None:
    row = {
        "item_id": result.item_id,
        "gold": gold_label,
        "predicted": result.classification.label_code() if result.ok else None,
        "model_id": result.model_id,
        "prompt_version": result.prompt_version,
        "latency_s": round(result.latency_s, 3),
        "attempts": result.attempts,
        "error": result.error,
        "invalid_json": result.invalid_json,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "fields": result.classification.model_dump(mode="json") if result.ok else None,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run(backend_name: str, dataset: str, run_n: int, limit: int | None, model_id: str | None) -> None:
    items = LOADERS[dataset]()
    if limit:
        items = items[:limit]

    kwargs = {"model_id": model_id} if model_id else {}
    backend = make_backend(backend_name, **kwargs)
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = result_path(backend_name, dataset, run_n)
    done = already_done(path)
    todo = [it for it in items if it[0] not in done]

    print(f"backend {backend_name} ({backend.model_id}) · conjunto {dataset} · execução {run_n}")
    if done:
        print(f"retomando: {len(done)} já feitos, {len(todo)} restantes")
    print(f"{len(todo)} itens a classificar. Resultados: {path}")

    started = time.monotonic()
    errors = 0
    for n, (item_id, text, gold_label) in enumerate(todo, 1):
        result = classify_one(backend, item_id, text)
        append_result(path, result, gold_label)
        if not result.ok:
            errors += 1
        elapsed = time.monotonic() - started
        rate = elapsed / n
        eta = rate * (len(todo) - n)
        sys.stdout.write(
            f"\r{n}/{len(todo)} · {rate:.1f}s por item · erros {errors} · faltam ~{eta / 60:.1f} min   "
        )
        sys.stdout.flush()
    print()

    total = len(todo)
    if total:
        print(f"concluído em {(time.monotonic() - started) / 60:.1f} min · {errors}/{total} erros")
    print(f"avalie com: python -m eval.metrics --backend {backend_name} --set {dataset}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", required=True, help=f"candidatos: {', '.join(CANDIDATES)}")
    parser.add_argument("--set", dest="dataset", required=True, choices=sorted(LOADERS))
    parser.add_argument("--run", type=int, default=1, help="nº da execução (2 mede estabilidade)")
    parser.add_argument("--limit", type=int, help="só os N primeiros itens (teste rápido)")
    parser.add_argument("--model-id", help="sobrescreve o modelo do backend")
    args = parser.parse_args()
    run(args.backend, args.dataset, args.run, args.limit, args.model_id)


if __name__ == "__main__":
    main()
