"""Métricas da avaliação: F1 com intervalo, simetria, custo e latência.

    python -m eval.metrics --backend gemini --set dev
    python -m eval.metrics --set gold --compare gemini qwen gemma
    python -m eval.metrics --set mirrored --compare gemini qwen gemma

Métrica principal (`docs/decisions/escolha-llm.md`): **F1 do código `1`** — violência política no
Brasil contra todo o resto — com intervalo de 95% por bootstrap. Comparar dois modelos usa
bootstrap **pareado**: reamostra os mesmos itens para os dois, porque o que interessa é a diferença
no mesmo conjunto, e o intervalo pareado é mais estreito que dois intervalos separados.

Item que falhou conta como negativo previsto, nunca é descartado: descartar erro infla o F1.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pipeline.config import ROOT

RESULTS = ROOT / "eval" / "results"
POSITIVE = 1  # o código que a série padrão usa
BOOTSTRAP = 10_000
SEED = 2026


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def load_results(backend: str, dataset: str, run: int = 1, original_gold: bool = False) -> list[dict]:
    path = RESULTS / f"{backend}__{dataset}__run{run}.jsonl"
    if not path.exists():
        raise SystemExit(f"{path} não existe. Rode: python -m eval.run --backend {backend} --set {dataset}")
    with path.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if dataset == "gold" and not original_gold:
        rows = with_current_gold(rows)
    return rows


def with_current_gold(rows: list[dict]) -> list[dict]:
    """Troca o rótulo gravado na execução pelo do gabarito vigente.

    Cada linha de resultado guarda o rótulo de ouro do momento em que rodou. Depois de uma errata,
    ler esse campo daria o número antigo sem aviso. A previsão do modelo não depende do rótulo, então
    recalcular contra o gabarito novo é válido sem rodar o modelo de novo.
    """
    from eval.gold import read_gold

    current = {r["item_id"]: r["label"] for r in read_gold()}
    changed = sum(1 for r in rows if r["item_id"] in current and current[r["item_id"]] != r["gold"])
    if changed:
        print(f"(gabarito vigente: {changed} rótulos diferem dos da execução; "
              "o número da execução sai com --original-gold)")
    return [{**r, "gold": current.get(r["item_id"], r["gold"])} for r in rows]


def f1_from_arrays(gold: np.ndarray, pred: np.ndarray) -> float:
    tp = int(np.sum((gold == POSITIVE) & (pred == POSITIVE)))
    fp = int(np.sum((gold != POSITIVE) & (pred == POSITIVE)))
    fn = int(np.sum((gold == POSITIVE) & (pred != POSITIVE)))
    denom = 2 * tp + fp + fn
    return 2 * tp / denom if denom else 0.0


def arrays(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Rótulo de ouro e previsto. Falha vira -1: conta como "não é o positivo", não é descartada."""
    gold = np.array([r["gold"] for r in rows])
    pred = np.array([r["predicted"] if r["predicted"] is not None else -1 for r in rows])
    return gold, pred


def counts_of(rows: list[dict]) -> Counts:
    gold, pred = arrays(rows)
    return Counts(
        tp=int(np.sum((gold == POSITIVE) & (pred == POSITIVE))),
        fp=int(np.sum((gold != POSITIVE) & (pred == POSITIVE))),
        fn=int(np.sum((gold == POSITIVE) & (pred != POSITIVE))),
        tn=int(np.sum((gold != POSITIVE) & (pred != POSITIVE))),
    )


def bootstrap_ci(gold: np.ndarray, pred: np.ndarray, n: int = BOOTSTRAP) -> tuple[float, float]:
    rng = np.random.default_rng(SEED)
    size = len(gold)
    scores = [
        f1_from_arrays(gold[idx], pred[idx])
        for idx in (rng.integers(0, size, size) for _ in range(n))
    ]
    return float(np.percentile(scores, 2.5)), float(np.percentile(scores, 97.5))


def paired_diff_ci(
    gold: np.ndarray, pred_a: np.ndarray, pred_b: np.ndarray, n: int = BOOTSTRAP
) -> tuple[float, float, float]:
    """Diferença de F1 (A − B) com intervalo pareado: reamostra os mesmos itens para os dois.

    Se o intervalo contém zero, é empate estatístico — e aí decidem os critérios de desempate,
    não o F1. Com ~200 itens esse é o resultado mais provável, e é por isso que a ordem de
    desempate foi escrita antes de rodar.
    """
    rng = np.random.default_rng(SEED)
    size = len(gold)
    diffs = []
    for _ in range(n):
        idx = rng.integers(0, size, size)
        diffs.append(f1_from_arrays(gold[idx], pred_a[idx]) - f1_from_arrays(gold[idx], pred_b[idx]))
    point = f1_from_arrays(gold, pred_a) - f1_from_arrays(gold, pred_b)
    return point, float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def operational(rows: list[dict]) -> dict:
    """Taxa de JSON inválido, latência e tokens: os eliminatórios operacionais."""
    n = len(rows)
    invalid = sum(1 for r in rows if r.get("invalid_json"))
    failed = sum(1 for r in rows if r["predicted"] is None)
    lat = np.array([r["latency_s"] for r in rows])
    tok_in = sum(r["input_tokens"] or 0 for r in rows)
    tok_out = sum(r["output_tokens"] or 0 for r in rows)
    return {
        "n": n,
        "invalid_json_pct": 100 * invalid / n if n else 0.0,
        "failed_pct": 100 * failed / n if n else 0.0,
        "retried_pct": 100 * sum(1 for r in rows if r["attempts"] > 1) / n if n else 0.0,
        "latency_median_s": float(np.median(lat)) if n else 0.0,
        "latency_p95_s": float(np.percentile(lat, 95)) if n else 0.0,
        "tokens_in": tok_in,
        "tokens_out": tok_out,
        "tokens_in_per_item": tok_in / n if n else 0,
        "tokens_out_per_item": tok_out / n if n else 0,
    }


def field_accuracy(rows: list[dict]) -> dict[str, float]:
    """Acurácia dos campos descritivos nos verdadeiros positivos.

    Só onde gold e previsto são o positivo: comparar `violence_type` num item que o modelo nem
    considerou violência não diz nada.
    """
    both = [r for r in rows if r["gold"] == POSITIVE and r["predicted"] == POSITIVE and r["fields"]]
    if not both:
        return {}
    out = {}
    for field in ("violence_type", "report_nature", "target_type", "perpetrator_type"):
        values = Counter(r["fields"][field] for r in both)
        out[f"{field}_mais_comum"] = f"{values.most_common(1)[0][0]} ({values.most_common(1)[0][1]}/{len(both)})"
    return out


def coverage_warning(rows: list[dict]) -> str | None:
    """Alerta quando falha de infraestrutura domina o resultado.

    Item que falhou conta como negativo previsto — correto quando a falha é do modelo (JSON
    inválido, recusa), porque esconder isso infla o F1. Mas quando a falha é de cota ou rede, o
    modelo nunca viu o item, e o F1 vira um número sobre a API, não sobre o classificador.
    Medido em 10/11: o Gemini deu F1 0,194 com 126/147 itens bloqueados por cota; nos 21 que
    rodaram, 0,857. Sem este aviso, o relatório diria que o modelo é ruim.
    """
    n = len(rows)
    if not n:
        return None
    api_failures = sum(1 for r in rows if r["error"] and r["error"].startswith("api:"))
    if api_failures / n > 0.05:
        return (
            f"ATENÇÃO: {api_failures}/{n} itens falharam por erro de API (cota, rede), não pelo "
            f"modelo.\n  O F1 abaixo inclui esses itens como negativos e NÃO mede o "
            f"classificador.\n  Use --only-completed para ver o F1 dos itens que o modelo de fato "
            f"classificou,\n  e repita a execução antes de registrar o resultado."
        )
    return None


def report_single(
    backend: str, dataset: str, run: int = 1, only_completed: bool = False, original_gold: bool = False
) -> None:
    rows = load_results(backend, dataset, run, original_gold)
    warning = coverage_warning(rows)
    if only_completed:
        rows = [r for r in rows if r["predicted"] is not None]
        if not rows:
            raise SystemExit("nenhum item foi classificado com sucesso.")
    c = counts_of(rows)
    gold, pred = arrays(rows)
    lo, hi = bootstrap_ci(gold, pred)
    op = operational(rows)

    print(f"\n{'=' * 64}")
    print(f"{backend} · {dataset} · execução {run} · modelo {rows[0]['model_id']}")
    scope = "só os itens classificados" if only_completed else "todos os itens"
    print(f"prompt {rows[0]['prompt_version']} · {op['n']} itens ({scope})")
    print("=" * 64)
    if warning:
        print(f"\n{warning}")
    print(f"\nCódigo {POSITIVE} (violência política no Brasil)")
    print(f"  F1        {c.f1:.3f}  (IC 95%: {lo:.3f} – {hi:.3f})")
    print(f"  precisão  {c.precision:.3f}")
    print(f"  recall    {c.recall:.3f}")
    print(f"  TP {c.tp}  FP {c.fp}  FN {c.fn}  TN {c.tn}")

    print("\nEliminatórios operacionais")
    flag = "REPROVA" if op["invalid_json_pct"] > 2 else "ok"
    print(f"  JSON inválido      {op['invalid_json_pct']:.1f}%  (limite 2%) [{flag}]")
    print(f"  falha total        {op['failed_pct']:.1f}%")
    print(f"  precisou repetir   {op['retried_pct']:.1f}%")
    sec_flag = "REPROVA" if op["latency_median_s"] > 7 else "ok"
    print(f"  latência mediana   {op['latency_median_s']:.1f}s  (limite ~7s/item) [{sec_flag}]")
    print(f"  latência p95       {op['latency_p95_s']:.1f}s")
    print(f"  tokens por item    {op['tokens_in_per_item']:.0f} entrada / {op['tokens_out_per_item']:.0f} saída")

    # Projeção para a Fase 4: é o eliminatório que de fato discrimina modelos locais.
    hours = 25_000 * op["latency_median_s"] / 3600
    print(f"  projeção 25 mil itens: {hours:.1f} h  (limite 48 h)")

    acc = field_accuracy(rows)
    if acc:
        print("\nCampos descritivos (nos verdadeiros positivos)")
        for k, v in acc.items():
            print(f"  {k:<28} {v}")

    errors = Counter(r["error"].split(":")[0] for r in rows if r["error"])
    if errors:
        print("\nErros por tipo")
        for kind, n in errors.most_common():
            print(f"  {kind:<10} {n}")


def report_compare(backends: list[str], dataset: str, run: int = 1, original_gold: bool = False) -> None:
    """Compara modelos no mesmo conjunto, com intervalo pareado da diferença."""
    data = {b: load_results(b, dataset, run, original_gold) for b in backends}
    common = set.intersection(*({r["item_id"] for r in rows} for rows in data.values()))
    print(f"\n{'=' * 64}")
    print(f"Comparação · {dataset} · {len(common)} itens em comum")
    print("=" * 64)

    aligned = {}
    for b, rows in data.items():
        kept = sorted((r for r in rows if r["item_id"] in common), key=lambda r: r["item_id"])
        aligned[b] = kept

    gold = np.array([r["gold"] for r in next(iter(aligned.values()))])
    print(f"\n{'modelo':<10} {'F1':>7} {'IC 95%':>17} {'prec':>7} {'rec':>7} {'JSON inv':>9} {'s/item':>8}")
    for b in backends:
        rows = aligned[b]
        _, pred = arrays(rows)
        c = counts_of(rows)
        lo, hi = bootstrap_ci(gold, pred)
        op = operational(rows)
        print(
            f"{b:<10} {c.f1:>7.3f} {f'{lo:.3f}–{hi:.3f}':>17} {c.precision:>7.3f} "
            f"{c.recall:>7.3f} {op['invalid_json_pct']:>8.1f}% {op['latency_median_s']:>8.1f}"
        )

    print("\nDiferenças pareadas (A − B). Intervalo contendo zero = empate estatístico:")
    for i, a in enumerate(backends):
        for b in backends[i + 1 :]:
            _, pred_a = arrays(aligned[a])
            _, pred_b = arrays(aligned[b])
            point, lo, hi = paired_diff_ci(gold, pred_a, pred_b)
            tie = "EMPATE" if lo <= 0 <= hi else "diferença"
            print(f"  {a} − {b}: {point:+.3f}  (IC 95%: {lo:+.3f} a {hi:+.3f})  [{tie}]")


def report_symmetry(backends: list[str], run: int = 1) -> None:
    """Assimetria nos pares espelhados: o eliminatório mais duro (limite 5%).

    Mede duas coisas, porque taxa sozinha não distingue ruído de viés:
      - quantos pares recebem rótulos diferentes entre A e B;
      - se as divergências têm direção (sempre o mesmo lado virando positivo) ou são aleatórias.
    """
    print(f"\n{'=' * 64}")
    print("Simetria · pares espelhados")
    print("=" * 64)
    for b in backends:
        rows = {r["item_id"]: r for r in load_results(b, "mirrored", run)}
        pairs: dict[str, dict[str, dict]] = {}
        for item_id, row in rows.items():
            pair_id, side = item_id.split("::")
            pairs.setdefault(pair_id, {})[side] = row

        complete = {p: s for p, s in pairs.items() if "a" in s and "b" in s}
        diverged = []
        for pair_id, sides in complete.items():
            pa, pb = sides["a"]["predicted"], sides["b"]["predicted"]
            if pa != pb:
                diverged.append((pair_id, pa, pb))

        n = len(complete)
        pct = 100 * len(diverged) / n if n else 0.0
        # Direção: A positivo e B não, contra o inverso. Desequilíbrio = viés de lado.
        a_pos = sum(1 for _p, pa, pb in diverged if pa == POSITIVE and pb != POSITIVE)
        b_pos = sum(1 for _p, pa, pb in diverged if pb == POSITIVE and pa != POSITIVE)
        flag = "REPROVA" if pct > 5 else "ok"
        print(f"\n{b}: {len(diverged)}/{n} pares divergentes = {pct:.1f}%  (limite 5%) [{flag}]")
        if diverged:
            print(f"  direção: {a_pos} vezes só o lado A positivo, {b_pos} vezes só o lado B")
            if a_pos and b_pos and abs(a_pos - b_pos) <= 1:
                print("  divergência sem direção clara: parece instabilidade, não viés de lado")
            elif a_pos or b_pos:
                print("  divergência com direção: indício de viés de lado, não de ruído")
            for pair_id, pa, pb in diverged[:10]:
                print(f"    {pair_id}: A={pa} B={pb}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend")
    parser.add_argument("--set", dest="dataset", required=True, choices=["dev", "gold", "mirrored"])
    parser.add_argument("--run", type=int, default=1)
    parser.add_argument("--compare", nargs="+", help="dois ou mais backends para comparar")
    parser.add_argument(
        "--only-completed",
        action="store_true",
        help="ignora itens que falharam por erro de API (diagnóstico, nunca resultado oficial)",
    )
    parser.add_argument(
        "--original-gold",
        action="store_true",
        help="usa o rótulo gravado na execução, não o do gabarito vigente (reproduz o número de antes da errata)",
    )
    args = parser.parse_args()

    if args.dataset == "mirrored":
        report_symmetry(args.compare or [args.backend], args.run)
    elif args.compare:
        report_compare(args.compare, args.dataset, args.run, args.original_gold)
    elif args.backend:
        report_single(args.backend, args.dataset, args.run, args.only_completed, args.original_gold)
    else:
        raise SystemExit("informe --backend ou --compare")


if __name__ == "__main__":
    main()
