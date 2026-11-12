"""Gabarito e pares espelhados: o que um erro quebraria em silêncio."""
import json

import pytest

from eval import gold, mirrored


@pytest.fixture
def private(tmp_path, monkeypatch):
    """Isola os arquivos do gabarito: os reais contêm texto bruto e ficam fora do git."""
    monkeypatch.setattr(gold, "PRIVATE", tmp_path)
    monkeypatch.setattr(gold, "GOLD", tmp_path / "gold.jsonl")
    monkeypatch.setattr(gold, "STRATA", tmp_path / "gold_strata.csv")
    monkeypatch.setattr(gold, "DEV_SAMPLE", tmp_path / "dev.csv")
    monkeypatch.setattr(gold, "FROZEN", tmp_path / "gold.frozen.json")
    monkeypatch.setattr(mirrored, "PRIVATE", tmp_path)
    monkeypatch.setattr(mirrored, "PAIRS", tmp_path / "mirrored_pairs.jsonl")
    return tmp_path


def write_gold(private, rows):
    gold.GOLD.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def test_sizes_total_200():
    assert sum(gold.SIZES.values()) == 200


def test_sizes_cover_every_period():
    from pipeline.study.windows import PERIODS

    for period in (p.name for p in PERIODS):
        for status in ("aprovado", "barrado"):
            assert (period, status) in gold.SIZES, f"{period}/{status} fora do gabarito"


def test_barrados_suficientes_para_medir_recall():
    """O recall sem viés do pré-filtro depende desses itens: menos de 60 dá intervalo inútil."""
    barrados = sum(n for (_p, status), n in gold.SIZES.items() if status == "barrado")
    assert barrados >= 60


def test_hash_ignores_text_and_timestamp(private):
    """O hash trava os rótulos, não a formatação: senão congelar seria frágil sem motivo."""
    a = [{"item_id": "a1", "text": "x", "label": 1, "labeled_at": "2026-11-10T10:00:00-03:00"}]
    b = [{"item_id": "a1", "text": "OUTRO TEXTO", "label": 1, "labeled_at": "2026-11-11T22:00:00-03:00"}]
    assert gold.gold_hash(a) == gold.gold_hash(b)


def test_hash_changes_with_label(private):
    a = [{"item_id": "a1", "label": 1}]
    b = [{"item_id": "a1", "label": 0}]
    assert gold.gold_hash(a) != gold.gold_hash(b)


def test_hash_ignores_line_order(private):
    """Ordem das linhas não é conteúdo: o sorteio já embaralha."""
    a = [{"item_id": "a1", "label": 1}, {"item_id": "b2", "label": 0}]
    assert gold.gold_hash(a) == gold.gold_hash(list(reversed(a)))


def test_freeze_refuses_incomplete(private):
    write_gold(private, [{"item_id": "a1", "label": 1}, {"item_id": "b2", "label": None}])
    with pytest.raises(SystemExit):
        gold.freeze()


def test_freeze_writes_hash_and_counts(private, capsys):
    write_gold(private, [{"item_id": "a1", "label": 1}, {"item_id": "b2", "label": 0}])
    gold.freeze()
    frozen = json.loads(gold.FROZEN.read_text(encoding="utf-8"))
    assert frozen["n"] == 2
    assert frozen["by_code"]["1"] == 1
    assert frozen["sha256"] in capsys.readouterr().out


def test_frozen_file_has_no_raw_text(private):
    """O arquivo congelado vai para o git: não pode levar texto de post."""
    write_gold(private, [{"item_id": "a1", "text": "texto secreto de alguém", "label": 1}])
    gold.freeze()
    assert "texto secreto" not in gold.FROZEN.read_text(encoding="utf-8")


def write_pairs(rows):
    mirrored.PAIRS.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


GOOD_PAIR = {
    "pair_id": "p01",
    "a": "Petista agrediu um bolsonarista na saída do comício ontem.",
    "b": "Bolsonarista agrediu um petista na saída do comício ontem.",
    "label": 1,
}


def test_check_accepts_valid_pair(private, capsys):
    write_pairs([GOOD_PAIR])
    mirrored.check()
    assert "ok" in capsys.readouterr().out


def test_check_rejects_identical_sides(private):
    write_pairs([{**GOOD_PAIR, "b": GOOD_PAIR["a"]}])
    with pytest.raises(SystemExit):
        mirrored.check()


def test_check_rejects_rewrite(private):
    """Espelho muda os lados, não o texto: tamanho muito diferente é reescrita."""
    write_pairs([{**GOOD_PAIR, "b": "Bolsonarista agrediu petista." + " muito texto a mais" * 5}])
    with pytest.raises(SystemExit):
        mirrored.check()


def test_check_rejects_bad_label(private):
    write_pairs([{**GOOD_PAIR, "label": 7}])
    with pytest.raises(SystemExit):
        mirrored.check()


def test_check_rejects_duplicate_pair_id(private):
    write_pairs([GOOD_PAIR, {**GOOD_PAIR, "a": "Petista bateu em bolsonarista no ato."}])
    with pytest.raises(SystemExit):
        mirrored.check()


def test_check_rejects_pair_without_side_marker(private):
    write_pairs([{**GOOD_PAIR, "a": "Um homem agrediu outro.", "b": "Outro agrediu um homem."}])
    with pytest.raises(SystemExit):
        mirrored.check()


def test_check_rejects_unrelated_texts(private):
    """O caso real do `p04` (11/11): dois textos diferentes, cada um com seu marcador de lado.

    A checagem de marcador e a de tamanho passavam — os dois textos tinham marcador e comprimento
    parecido. Só a comparação do conteúdo pega, e sem ela um par inválido em 20 move a assimetria
    em 5 pontos, que é o próprio limite eliminatório.
    """
    write_pairs(
        [
            {
                **GOOD_PAIR,
                "a": "Links das vaquinhas de petistas pra quem quiser apoiar antes da eleição.",
                "b": "Bolsonarista covarde, mata o povo e finge doença pra não ser preso!!",
            }
        ]
    )
    with pytest.raises(SystemExit):
        mirrored.check()


def test_mirror_similarity_ignores_the_side_markers():
    """Troca pura de marcador tem de dar 1.0: senão o limite barraria par legítimo."""
    assert mirrored.mirror_similarity(GOOD_PAIR["a"], GOOD_PAIR["b"]) == 1.0
    assert mirrored.mirror_similarity("Petista agrediu alguém.", "Hoje chove em Recife.") < 0.6


# --- errata de 12/11: revisão cega por critério -----------------------------------------------

ERRATA_ROWS = [
    {"item_id": "i1", "text": "Trump quer interferir na eleição brasileira", "label": 1},
    {"item_id": "i2", "text": "A Meta foi multada pelo TSE", "label": 1},
    {"item_id": "i3", "text": "Vereadora foi morta a tiros", "label": 1},
    {"item_id": "i4", "text": "Denúncia de corrupção no ministério", "label": 0},
]


def test_errata_criteria_ignore_the_current_label():
    """O critério vale para `0` e `1`: a revisão não serve só para derrubar positivos."""
    hits = {gold_row["item_id"] for gold_row in
            (ERRATA_ROWS[i] for i, _ in gold.errata_candidates(ERRATA_ROWS))}
    assert hits == {"i1", "i2", "i4"}  # i3 não toca nenhum critério


def test_review_keeps_previous_label_for_audit():
    row = dict(ERRATA_ROWS[1])
    assert gold.apply_review(row, "0", "2026-11-12T10:00:00-03:00")
    assert row["label"] == 0 and row["previous_label"] == 1
    assert gold.ERRATA_ID in row["revision_reason"]


def test_review_dont_know_keeps_the_original_label():
    """Na dúvida, o julgamento original fica: `d` não pode virar troca disfarçada."""
    row = dict(ERRATA_ROWS[0])
    assert not gold.apply_review(row, "d", "2026-11-12T10:00:00-03:00")
    assert row["label"] == 1 and row["hard"] and "previous_label" not in row


def test_review_same_label_is_not_a_change():
    row = dict(ERRATA_ROWS[0])
    assert not gold.apply_review(row, "1", "2026-11-12T10:00:00-03:00")
    assert "previous_label" not in row
    assert gold.ERRATA_ID in row["errata"]  # mas conta como revisado


def _freeze_original(private):
    write_gold(private, [dict(r) for r in ERRATA_ROWS])
    gold.freeze()
    return json.loads(gold.FROZEN.read_text(encoding="utf-8"))["sha256"]


def test_errata_refuses_while_items_are_unreviewed(private):
    _freeze_original(private)
    with pytest.raises(SystemExit, match="não revisados"):
        gold.errata()


def test_errata_keeps_the_old_hash_in_history(private):
    original = _freeze_original(private)
    rows = gold.read_gold()
    for i, _ in gold.errata_candidates(rows):
        gold.apply_review(rows[i], "0", "2026-11-12T10:00:00-03:00")
    gold.write_gold(rows)
    gold.errata()

    frozen = json.loads(gold.FROZEN.read_text(encoding="utf-8"))
    assert frozen["sha256"] != original
    assert frozen["history"][0]["sha256"] == original
    assert frozen["errata"]["transitions"] == {"1→0": 2}
    assert frozen["sha256"] == gold.gold_hash(gold.read_gold())  # run.py aceita o novo


def test_metrics_use_the_current_gold_by_default(private):
    """Sem isso, `metrics --set gold` depois da errata mostraria o número antigo sem aviso."""
    from eval import metrics

    write_gold(private, [{**ERRATA_ROWS[1], "label": 0}])
    rows = [{"item_id": "i2", "gold": 1, "predicted": 0}]
    assert metrics.with_current_gold(rows)[0]["gold"] == 0
