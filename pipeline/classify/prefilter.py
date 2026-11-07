"""Pré-filtro barato antes do classificador: decide o que vale a pena classificar.

Prioridade é recall: o que o pré-filtro barra nunca é classificado. A precisão fica com o
classificador. O recall é medido contra itens rotulados à mão, inclusive barrados
(`python -m pipeline.classify.recall`, docs/prefilter.md).

O texto é normalizado antes (minúsculas, sem acento, pontuação vira espaço), então os padrões
não têm acento. Todo termo tem fronteira de palavra: `tiro` não casa com "retirou", nem `soco`
com "socorro".

Regras (escopo em eval/labeling_guide.md); o texto passa se alguma regra casar:
  - consulta:  o item veio de uma consulta de violência (famílias cargo, evento, espectro), que já
               exige violência + contexto. Medido em 07/11/2026: o regex barrava casos centrais
               dessas famílias ("o matador de Marielle Franco explica a execução", sem "vereadora");
               são ~130 itens em 5 meses, custo desprezível;
  - frase:     a própria expressão já é o tema ("violência política", "motivação política");
  - politica:  violência + contexto político (eleição, cargo, partido, espectro político);
  - evento:    ato/manifestação/protesto + violência ou repressão policial.
"""
from __future__ import annotations

import re

from pipeline.geocode.ibge import normalize
from pipeline.ingest.queries import FAMILIES

VIOLENCE_QUERIES = frozenset(q for fam, qs in FAMILIES.items() if fam != "contexto" for q in qs)


def _words(*patterns: str) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(patterns) + r")\b")


VIOLENCE = _words(
    # ameaça, intimidação, ofensa
    r"amea\w*", r"intimid\w*", r"persegu\w*", r"coag\w*", r"ofens\w*", r"xingad\w*", r"hostiliz\w*",
    # agressão física, inclusive linguagem coloquial
    r"agred\w*", r"agress\w*", r"agrid\w*", r"espanc\w*", r"socos?", r"socad\w*", r"murros?", r"chutes?",
    r"chutad\w*", r"pontap\w*", r"tapas?", r"pancad\w*", r"pancadaria", r"porrad\w*", r"surra\w*",
    r"voadoras?", r"cadeiradas?", r"garrafadas?", r"pedradas?", r"pauladas?", r"empurr\w*",
    r"partiu pra cima", r"partiram pra cima", r"linch\w*", r"brigas?", r"confrontos?", r"feridos?", r"feridas?",
    r"atacad\w*", r"atacou", r"atacaram", r"ataques?", r"atentados?",
    # arma, tiro, morte
    r"tiros?", r"tiroteio", r"balead\w*", r"baleou", r"disparos?", r"atir\w*", r"arma de fogo",
    r"facadas?", r"esfaque\w*", r"faca", r"assassin\w*", r"homicid\w*", r"executad[oa]s?", r"executou", r"executaram",
    r"execucao", r"matador\w*", r"pistoleir\w*", r"mandantes?", r"jagunc\w*", r"milician\w*",
    r"mort[oa]s?", r"morte", r"morreu", r"mat(?:a|ou|aram|am|ar|ando|ado|ada)",
    # depredação
    r"depred\w*", r"vandaliz\w*", r"incendi\w*", r"quebra quebra",
    r"violen\w*",
)
POLICE = _words(
    r"bala de borracha", r"balas de borracha", r"spray de pimenta", r"gas lacrimogeneo",
    r"bombas? de gas", r"bombas? de efeito moral", r"reprim\w*", r"repress\w*", r"cassetet\w*",
    r"tropa de choque",
)
POLITICAL = _words(
    r"elei\w*", r"eleitor\w*", r"eleitora\w*", r"votos?", r"vot(?:ar|ou|aram|ando)", r"urnas?",
    r"candidat\w*", r"campanha eleitoral", r"campanha politica", r"cabos? eleitora(?:l|is)",
    r"comicios?", r"carreatas?", r"panfletag\w*", r"comites?", r"santinhos?",
    # cargos
    r"vereador\w*", r"prefeit[oa]s?", r"vice prefeit[oa]s?", r"deputad[oa]s?", r"senador\w*",
    r"governador\w*", r"parlamentar\w*", r"presidente da republica", r"ministr[oa]s?",
    # partidos e espectro (só para achar o tema; nenhum campo registra o lado de alguém)
    r"partidos?", r"partidari\w*", r"politic\w*", r"militantes?", r"militancia",
    r"apoiador\w*", r"apoiadora\w*", r"petistas?", r"do pt", r"bolsonar\w*", r"lulistas?", r"lula",
    r"esquerdistas?", r"direitistas?", r"de esquerda", r"de direita", r"extrema direita",
    r"extrema esquerda", r"comunistas?", r"fascistas?", r"golpist\w*",
)
EVENT = _words(r"atos?", r"manifesta\w*", r"protest\w*", r"passeatas?", r"carreatas?", r"comicios?",
               r"marchas?", r"mobilizac\w*")
PHRASE = _words(
    r"violencia politica", r"violencia eleitoral", r"violencia partidaria", r"motivac\w* politica",
    r"crime politico", r"atentado politico", r"assassinato politico", r"discussao politica",
    r"briga politica", r"por causa de politica", r"por motivo politico",
)


def prefilter_rules(text: str, queries: list[str] | None = None) -> set[str]:
    """Nomes das regras que o item satisfaz (vazio = barrado). `queries`: consultas que o trouxeram."""
    t = normalize(text)
    rules = {"consulta"} if VIOLENCE_QUERIES.intersection(queries or []) else set()
    if PHRASE.search(t):
        rules.add("frase")
    violent = bool(VIOLENCE.search(t))
    if violent and POLITICAL.search(t):
        rules.add("politica")
    if EVENT.search(t) and (violent or POLICE.search(t)):
        rules.add("evento")
    return rules


def matches_prefilter(text: str, queries: list[str] | None = None) -> bool:
    return bool(prefilter_rules(text, queries))
