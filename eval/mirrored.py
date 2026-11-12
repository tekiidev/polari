"""Pares espelhados: mesmo texto com os lados políticos trocados, para medir viés do classificador.

    python -m eval.mirrored candidates   # lista posts reais candidatos a espelhar
    python -m eval.mirrored check        # valida o arquivo de pares escrito à mão
    python -m eval.mirrored status

Pelo guia de rotulagem, trocar os lados de um texto não muda o rótulo: a violência é a mesma. Se o
modelo discorda de si mesmo entre as duas versões, a série é medida com régua diferente conforme
quem aparece como agressor — e o F1 agregado não revela isso, porque um modelo pode acertar 85% dos
itens errando justamente de forma assimétrica. Num mapa colorido por UF, isso vira peça partidária
com aparência de dado. Por isso simetria é eliminatória (`docs/decisions/escolha-llm.md`).

**Os pares são escritos à mão.** Substituição automática não serve: "petista" e "bolsonarista" têm
frequências muito diferentes nos dados de treino dos modelos, e a troca costuma quebrar a
concordância da frase. `candidates` só ajuda a achar os posts; o espelho é seu.

**Textos espelhados são sintéticos:** entram só na medida de simetria, nunca no F1, que é medido
apenas em texto que alguém escreveu de verdade.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import date, datetime
from difflib import SequenceMatcher

from pipeline.config import ROOT
from pipeline.storage import RawStore

PRIVATE = ROOT / "eval" / "labeled_private"
PAIRS = PRIVATE / "mirrored_pairs.jsonl"
CANDIDATES = PRIVATE / "mirrored_candidates.csv"

# Marcadores de lado que tornam um post espelhável. Não são critério de escopo: servem só para
# achar textos em que existe um lado a trocar.
SIDE_MARKERS = [
    "petista", "petistas", "bolsonarista", "bolsonaristas", "esquerdista", "esquerdistas",
    "direitista", "direitistas", "comunista", "comunistas", "fascista", "fascistas",
    "lulista", "lulistas", "coxinha", "mortadela",
    # Siglas, nomes e movimentos: trocar "PT" por "PL" ou "Lula" por "Bolsonaro" espelha o lado
    # igualmente bem, e `candidates` não achava esses posts.
    "pt", "pl", "psol", "lula", "bolsonaro", "esquerda", "direita",
    "sem-terra", "caminhoneiro", "caminhoneiros", "sindical", "ruralista",
    # Interferência estrangeira: o lado se troca pelo país que interfere.
    "eua", "estados unidos", "china", "russia", "rússia",
]
# Fora da lista de propósito: "gado" e "militante" aparecem em metade dos posts e não têm par
# simétrico óbvio ("gado" é dito de um lado só), então dominariam os candidatos sem gerar pares.
# Pistas de violência: o par só é útil se houver rótulo a comparar.
VIOLENCE_HINTS = [
    "agred", "espanc", "bat", "mat", "mort", "tiro", "bala", "arma", "faca", "ameaç",
    "atac", "invad", "quebr", "destru", "linch", "persegu", "intimid", "apanh",
]


def has_any(text: str, terms: list[str]) -> list[str]:
    """Marcadores presentes no texto, comparados por palavra inteira.

    Por palavra porque siglas curtas ("pt", "pl") casariam dentro de outras palavras: "pt" em
    "apto", "pl" em "simples".
    """
    low = text.lower()
    return [t for t in terms if re.search(rf"(?<!\w){re.escape(t)}(?!\w)", low)]


# Abaixo disto, A e B não são o mesmo texto com os lados trocados. O corte vem dos 20 pares
# escritos em 10-11/11: o pior par legítimo ficou em 0,81 e o par inválido em 0,02 — não há zona
# cinzenta entre as duas coisas, então 0,6 separa com folga dos dois lados.
MIN_MIRROR_SIMILARITY = 0.6


def strip_sides(text: str) -> str:
    """O texto sem os marcadores de lado, para comparar o que deveria ser idêntico nos dois lados."""
    low = text.lower()
    for marker in sorted(SIDE_MARKERS, key=len, reverse=True):
        low = re.sub(rf"(?<!\w){re.escape(marker)}(?!\w)", " ", low)
    return re.sub(r"\W+", " ", low).strip()


def mirror_similarity(a: str, b: str) -> float:
    """Quanto A e B coincidem fora dos marcadores de lado (1.0 = troca pura de marcador).

    Sem isso o `check` aceitava dois textos sem relação alguma como par: bastava cada um ter algum
    marcador de lado. Foi o que aconteceu com o par `p04`, descoberto só quando o modelo "divergiu"
    nele — e a divergência era correta, porque os textos tinham rótulos diferentes de verdade. Um
    par inválido em 20 move a assimetria em 5 pontos, que é exatamente o limite eliminatório.
    """
    return SequenceMatcher(None, strip_sides(a), strip_sides(b)).ratio()


def candidates(store: RawStore, start: date, end: date, limit: int = 120) -> None:
    """Lista posts com marcador de lado e pista de violência, para você escolher e espelhar."""
    found: list[tuple[str, str, str]] = []
    for item in store.iter_items("bluesky", start, end):
        sides = has_any(item.text, SIDE_MARKERS)
        if not sides or not has_any(item.text, VIOLENCE_HINTS):
            continue
        # Texto de uma linha: facilita escolher no terminal sem abrir o arquivo inteiro.
        flat = re.sub(r"\s+", " ", item.text).strip()
        found.append((item.item_id, flat, "|".join(sorted(sides))))
        if len(found) >= limit:
            break

    PRIVATE.mkdir(parents=True, exist_ok=True)
    with CANDIDATES.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "text", "side_markers"])
        w.writerows(found)
    print(f"{len(found)} candidatos em {CANDIDATES}")
    print(f"""
Agora escreva ~40 pares em {PAIRS}, um JSON por linha:

{{"pair_id": "p01", "source_item_id": "<id do candidato, ou null se inventado>",
  "a": "<texto como está>", "b": "<mesmo texto, lados trocados>",
  "label": 1, "note": "o que foi trocado"}}

Regras: só os marcadores de lado mudam (e o país, na interferência estrangeira); o `label` é o
mesmo para A e B, porque é o mesmo fato; se a troca mudar o sentido, descarte o par.
Depois: python -m eval.mirrored check
""".rstrip())


def read_candidates() -> list[dict]:
    if not CANDIDATES.exists():
        raise SystemExit(f"{CANDIDATES} não existe. Rode: python -m eval.mirrored candidates")
    with CANDIDATES.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_pair(pair: dict) -> None:
    """Grava um par por vez: Ctrl-C não perde o que já foi escrito."""
    PRIVATE.mkdir(parents=True, exist_ok=True)
    with PAIRS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(pair, ensure_ascii=False) + "\n")


WRITE_HELP = """\
Para cada candidato: escreva o MESMO texto com os lados políticos trocados.

  Enter vazio = pular este candidato        s = sair e salvar
  Só os marcadores de lado mudam (petista <-> bolsonarista, esquerda <-> direita).
  Se a troca mudar o sentido ou quebrar a frase, pule: par ruim mede ruído, não viés.
  O rótulo é o MESMO para os dois lados, porque é o mesmo fato.
"""


def write(target: int = 40) -> None:
    """Escreve os pares no terminal, a partir dos candidatos, retomável."""
    candidates_rows = read_candidates()
    existing = read_pairs() if PAIRS.exists() else []
    done_sources = {p.get("source_item_id") for p in existing}
    next_n = len(existing) + 1

    print(WRITE_HELP)
    for row in candidates_rows:
        written = next_n - 1
        if written >= target:
            print(f"meta de {target} pares atingida.")
            break
        if row["item_id"] in done_sources:
            continue

        print("─" * 72)
        print(f"par {next_n}  ·  {written} escritos  ·  marcadores: {row['side_markers']}")
        print("─" * 72)
        print(row["text"])
        print("─" * 72)
        mirrored_text = input("versão com os lados trocados (Enter pula, 's' sai): ").strip()
        if mirrored_text.lower() == "s":
            break
        if not mirrored_text:
            continue
        if mirrored_text == row["text"].strip():
            print("igual ao original — pulando.")
            continue

        answer = input("rótulo dos DOIS textos [0/1/2/3]: ").strip()
        if not (answer.isdigit() and int(answer) in {0, 1, 2, 3}):
            print(f"rótulo inválido: {answer!r} — par descartado.")
            continue
        note = input("nota (o que foi trocado; Enter pula): ").strip()

        pair = {
            "pair_id": f"p{next_n:02d}",
            "source_item_id": row["item_id"],
            "a": re.sub(r"\s+", " ", row["text"]).strip(),
            "b": mirrored_text,
            "label": int(answer),
            "note": note,
            "written_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        append_pair(pair)
        existing.append(pair)
        next_n += 1

    total = len(read_pairs()) if PAIRS.exists() else 0
    print(f"\n{total} pares em {PAIRS}")
    print("Valide com: python -m eval.mirrored check")


def read_pairs() -> list[dict]:
    if not PAIRS.exists():
        raise SystemExit(f"{PAIRS} não existe. Rode: python -m eval.mirrored candidates")
    with PAIRS.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def check() -> None:
    """Valida o que um erro de digitação quebraria em silêncio na hora de medir a assimetria."""
    pairs = read_pairs()
    problems: list[str] = []
    seen: set[str] = set()
    for i, p in enumerate(pairs, 1):
        where = p.get("pair_id") or f"linha {i}"
        for field in ("pair_id", "a", "b", "label"):
            if field not in p:
                problems.append(f"{where}: falta o campo '{field}'")
        if p.get("pair_id") in seen:
            problems.append(f"{where}: pair_id repetido")
        seen.add(p.get("pair_id"))
        a, b = p.get("a", ""), p.get("b", "")
        if a and b:
            if a.strip() == b.strip():
                problems.append(f"{where}: A e B são iguais — nada foi trocado")
            # Espelho deve mudar pouco: tamanho muito diferente indica reescrita, não troca.
            if a and abs(len(a) - len(b)) > max(30, 0.4 * len(a)):
                problems.append(f"{where}: A e B têm tamanhos muito diferentes ({len(a)} vs {len(b)})")
            if not has_any(a, SIDE_MARKERS) and not has_any(b, SIDE_MARKERS):
                problems.append(f"{where}: nenhum marcador de lado em A nem em B")
            sim = mirror_similarity(a, b)
            if sim < MIN_MIRROR_SIMILARITY:
                problems.append(
                    f"{where}: A e B não são o mesmo texto (similaridade {sim:.2f} fora dos "
                    f"marcadores, mínimo {MIN_MIRROR_SIMILARITY}). Um par espelhado é o MESMO "
                    "texto com os lados trocados, não dois textos diferentes sobre lados opostos."
                )
        if p.get("label") not in {0, 1, 2, 3}:
            problems.append(f"{where}: label {p.get('label')!r} fora de 0-3")

    print(f"{len(pairs)} pares lidos")
    if problems:
        print(f"\n{len(problems)} problemas:")
        for msg in problems:
            print(f"  - {msg}")
        raise SystemExit(1)
    counts = Counter(p["label"] for p in pairs)
    print("por código: " + "  ".join(f"{c}={counts.get(c, 0)}" for c in sorted({0, 1, 2, 3})))
    if len(pairs) < 30:
        print(f"aviso: {len(pairs)} pares dão intervalo largo na assimetria; a meta é ~40")
    print("ok: nenhum problema estrutural.")


def status() -> None:
    if not PAIRS.exists():
        print(f"nenhum par escrito ainda. Comece por: python -m eval.mirrored candidates")
        return
    pairs = read_pairs()
    print(f"{len(pairs)} pares ({len(pairs) * 2} textos) em {PAIRS}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("candidates", help="lista posts reais candidatos a espelhar")
    c.add_argument("--start", type=date.fromisoformat, default=date(2026, 6, 1))
    c.add_argument("--end", type=date.fromisoformat, default=date(2026, 11, 4))
    c.add_argument("--limit", type=int, default=120)
    w = sub.add_parser("write", help="escreve os pares no terminal (retomável)")
    w.add_argument("--target", type=int, default=40, help="quantos pares escrever (padrão: 40)")
    sub.add_parser("check", help="valida o arquivo de pares")
    sub.add_parser("status", help="quantos pares existem")
    args = parser.parse_args()

    if args.cmd == "candidates":
        candidates(RawStore(), args.start, args.end, args.limit)
    elif args.cmd == "write":
        write(args.target)
    elif args.cmd == "check":
        check()
    else:
        status()


if __name__ == "__main__":
    main()
