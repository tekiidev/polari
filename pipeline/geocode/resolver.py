"""Resolve (cidade, UF) -> município IBGE.

Cascata sugerida:
  1. Se há UF: busca exata em (normalize(cidade), UF).
  2. Sem UF: aceite só se o nome for único no país; se ambíguo (ex.: 'Santa Luzia'), devolva None.
  3. Fallback opcional: Nominatim, com cache em disco, 1 req/s e User-Agent identificável
     (settings.nominatim_user_agent). Nunca em lote grande: a política do serviço proíbe.
  4. Sem resolução -> None. Não chute: o % geolocalizado vai para o summary.json.
"""
from __future__ import annotations


def resolve_city(city: str | None, uf: str | None) -> str | None:
    """Devolve o código IBGE do município ou None."""
    # TODO(D3)
    raise NotImplementedError
