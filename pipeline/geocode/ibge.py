"""Tabela local de municípios (IBGE) para resolver cidade+UF -> código IBGE + coordenadas.

TODO(D1): baixe uma tabela com ibge_code, nome, uf, latitude, longitude dos 5.570 municípios
(IBGE malhas/localidades ou uma base aberta mantida pela comunidade; confira a licença) e salve
em data/municipios.csv. Carregue com pandas/duckdb.
"""
from __future__ import annotations

import re
import unicodedata


def normalize(name: str) -> str:
    """minúsculas, sem acentos, espaços/pontuação colapsados. 'São Luís ' -> 'sao luis'."""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", ascii_only.lower()).strip()


def load_municipalities():
    # TODO(D1): ler data/municipios.csv e criar índice por (normalize(nome), uf)
    raise NotImplementedError
