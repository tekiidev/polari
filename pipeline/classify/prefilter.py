"""Pré-filtro barato antes do classificador: decide o que vale a pena classificar.

Prioridade é recall: o que o pré-filtro barra nunca é classificado. A precisão fica com o
classificador. O recall é medido contra itens rotulados à mão, inclusive barrados
(`python -m pipeline.classify.recall`, docs/prefilter.md).

O texto é normalizado antes (minúsculas, sem acento, pontuação vira espaço), então os padrões
não têm acento. Todo termo tem fronteira de palavra: `tiro` não casa com "retirou", nem `soco`
com "socorro".

Regras (escopo em eval/labeling_guide.md); o texto passa se alguma regra casar:
  - consulta:  o item veio de uma consulta de violência (famílias cargo e evento), que já exige
               violência + contexto. Medido em 07/11/2026: o regex barrava casos centrais dessas
               famílias ("o matador de Marielle Franco explica a execução", sem "vereadora"); são
               ~130 itens em 5 meses, custo desprezível. A família `espectro` foi retirada em
               11/11/2026 por medição (ver `EXCLUDED_FAMILIES`);
  - frase:     a própria expressão já é o tema ("violência política", "motivação política");
  - politica:  violência + contexto político (eleição, cargo, partido, espectro político);
  - evento:    ato/manifestação/protesto + violência ou repressão policial;
  - interferencia: interferência estrangeira + contexto político (regra do guia de 07/11/2026).
               Custo medido: +4.961 itens a classificar em 5 meses (de ~13,2 mil para ~18 mil).
"""
from __future__ import annotations

import re

from pipeline.geocode.ibge import normalize
from pipeline.ingest.queries import FAMILIES

# Famílias cujas consultas, por si, bastam para o item ser classificado (regra `consulta`).
#
# `contexto` está fora porque é o denominador: não exige violência, traz 216 mil itens.
#
# `espectro` saiu em 11/11/2026, por medição. Ela cruza termo de espectro político com termo de
# violência, e o cruzamento casa demais: "Mata" de Mata Atlântica, "se mata" como expressão,
# "existe vida fora do bluesky". Dos 347 itens rotulados (dev + gabarito), 21 entravam **somente**
# por ela e **todos os 21 eram código 0**; nos 111 itens exclusivos dela em 5 meses, a leitura de
# uma amostra não achou positivo claro. Precisão medida na Fase 2: 4 de 15. Reverter é tirar
# `"espectro"` deste conjunto.
EXCLUDED_FAMILIES = frozenset({"contexto", "espectro"})
VIOLENCE_QUERIES = frozenset(
    q for fam, qs in FAMILIES.items() if fam not in EXCLUDED_FAMILIES for q in qs
)


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
INTERFERENCE = _words(r"interfer\w*", r"ingerenc\w*", r"intromiss\w*", r"soberania")
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
    if INTERFERENCE.search(t) and POLITICAL.search(t):
        rules.add("interferencia")
    return rules


def matches_prefilter(text: str, queries: list[str] | None = None) -> bool:
    return bool(prefilter_rules(text, queries))
