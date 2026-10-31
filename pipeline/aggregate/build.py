"""Agrega itens classificados e escreve os JSON do front (veja docs/ARCHITECTURE.md).

Regras:
  - Só entram itens com is_political_violence == True e confidence >= limiar (defina e documente).
  - Deduplique antes de contar (a unidade é o incidente, não a menção): comece simples
    (mesmo texto normalizado/URL) e evolua (similaridade por embeddings) se sobrar tempo.
  - Privacidade: oculte células com total < settings.min_cell_size.
  - Escreva summary.json, municipios.json, timeline.json em settings.out_dir.
"""
from __future__ import annotations

from collections.abc import Iterable

from pipeline.models import ProcessedItem


def build_outputs(items: Iterable[ProcessedItem]) -> None:
    # TODO(D3)
    raise NotImplementedError
