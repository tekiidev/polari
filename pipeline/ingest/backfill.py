"""Backfill: coleta o PASSADO em fatias, antes que as fontes expirem.

Por que isso vem primeiro: o estudo compara antes/depois das eleições. RSS não guarda
histórico e algumas APIs só cobrem uma janela recente (confira a cobertura real de cada fonte).

O que implementar:
  1. Percorrer [start, end] em fatias de `chunk_days` dias (comece com 1 dia).
  2. Para cada fatia, chamar `source.fetch(since=..., until=..., limit=...)`.
  3. Idempotência: gravar em data/raw/ com chave (source, item_id); reexecutar não duplica.
  4. Checkpoint: registrar as fatias concluídas (ex.: data/raw/_checkpoint.json) para retomar
     depois de uma queda ou de estouro de cota sem refazer o que já foi coletado.
  5. Respeitar limites de taxa (backoff) e logar quantos itens cada fatia trouxe.
  6. Fatias que voltarem vazias merecem atenção: pode ser dia sem posts ou limite da fonte.

Teste de viabilidade (D0), antes de construir o resto: some a contagem de itens por dia entre
16/08 e hoje para a consulta de contexto eleitoral. Se o volume por janela for pequeno demais,
a comparação antes/depois não sustenta conclusão: documente isso em vez de forçar.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from pipeline.ingest.base import Source
from pipeline.models import RawItem


def backfill(source: Source, start: date, end: date, chunk_days: int = 1) -> Iterable[RawItem]:
    # TODO(D0)
    raise NotImplementedError("Implemente o backfill por fatias (veja o docstring).")
