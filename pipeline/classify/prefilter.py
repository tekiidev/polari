"""Pré-filtro barato antes do LLM (economiza cota do free tier).

Trade-off: termos demais = muito ruído e gasto de cota; termos de menos = perde casos (recall).
Meça o recall do pré-filtro contra seu gabarito rotulado em eval/ e ajuste a lista.
"""
from __future__ import annotations

import re

# Lista INICIAL. Expanda com base nos casos que o filtro deixou passar.
VIOLENCE_TERMS = [
    r"amea[çc]a\w*", r"agred\w+", r"agress\w+", r"espanc\w+", r"soco\w*", r"tiro\w*",
    r"atentado\w*", r"assassin\w+", r"morto\w*", r"mataram", r"matar\b", r"facada\w*",
    r"intimida\w+", r"perseguiç\w+", r"ataque\w*", r"violên\w+", r"violenc\w+",
]
CONTEXT_TERMS = [
    r"elei[çc]\w+", r"voto\w*", r"candidat\w+", r"urna\w*", r"bolsonar\w+", r"lula",
    r"eleitor\w*", r"comício\w*", r"bandeira\w*", r"camiseta\w*",
]

_violence = re.compile("|".join(VIOLENCE_TERMS), re.IGNORECASE)
_context = re.compile("|".join(CONTEXT_TERMS), re.IGNORECASE)


def matches_prefilter(text: str) -> bool:
    """True se o texto tem termo de violência E contexto político/eleitoral."""
    return bool(_violence.search(text)) and bool(_context.search(text))
