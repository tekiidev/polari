"""Pré-filtro: casos centrais que precisam passar e falsos positivos conhecidos que precisam sair.

Não mede recall (isso é contra itens rotulados, pipeline/classify/recall.py): só trava regressões.
"""
import pytest

from pipeline.classify.prefilter import matches_prefilter, prefilter_rules
from pipeline.ingest.queries import FAMILIES

MUST_PASS = [
    # casos centrais que a versão da Fase 1 perdia
    "Vereadora foi morta a tiros em frente de casa",
    "Prefeito é baleado durante evento no interior",
    "Candidata recebe ameaças de morte após debate",
    # manifestação e repressão policial
    "PM usa bala de borracha contra manifestantes em ato no centro",
    "Pancadaria no protesto de ontem, vários feridos",
    "Tropa de choque reprime passeata em Belém",
    # espectro político e casos isolados
    "Bolsonarista mata petista em festa de aniversário",
    "Foi espancado por usar camisa do PT",
    "Homem é morto após discussão política em bar",
    # linguagem coloquial
    "O cara partiu pra cima do deputado no aeroporto",
    "Teve cadeirada no debate dos candidatos",
    # o próprio tema
    "Relatório aponta aumento da violência política no país",
    # notícia compartilhada: o texto do cartão de link entra no texto
    "Absurdo.\n\n[link] Vereador é esfaqueado durante comício — Crime em MG",
    # palavras de autoria do crime (caso real barrado na medição de 07/11)
    "O matador do vereador explica friamente a execução",
    # interferência estrangeira (regra do guia de 07/11)
    "Governo Trump está interferindo nas eleições brasileiras",
]

MUST_FAIL = [
    # sem fronteira de palavra, a Fase 1 aceitava estes
    "Ele retirou a candidatura do vereador da pauta",
    "Chamaram o socorro para o candidato que passou mal",
    # violência sem contexto político
    "Houve uma agressão no trânsito ontem",
    "Briga de torcida termina com feridos no estádio",
    # contexto político sem violência
    "Hoje o tempo está agradável para votar",
    "Prefeito inaugura escola no bairro",
    # termos que pareciam violência
    "O poder executivo enviou o projeto ao Congresso",
]


@pytest.mark.parametrize("text", MUST_PASS)
def test_central_cases_pass(text):
    assert matches_prefilter(text), text


@pytest.mark.parametrize("text", MUST_FAIL)
def test_known_false_positives_are_blocked(text):
    assert not matches_prefilter(text), (text, prefilter_rules(text))


def test_rules_are_named():
    assert prefilter_rules("PM usa spray de pimenta em ato") == {"evento"}
    assert prefilter_rules("Debate sobre violência eleitoral") == {"frase", "politica"}


def test_items_from_violence_queries_always_pass():
    text = "Ronnie Lessa, o pistoleiro, explica os detalhes do caso Marielle"  # sem cargo no texto
    assert prefilter_rules(text, ["vereadora assassinada"]) >= {"consulta"}
    assert not matches_prefilter("Hoje o tempo está agradável", ["eleição"])  # contexto não basta


def test_only_the_intended_families_grant_the_consulta_rule():
    """Quais famílias bastam por si é decisão medida, não detalhe: precisa quebrar se mudar.

    `contexto` é o denominador (216 mil itens, sem exigir violência) e `espectro` foi podada em
    11/11/2026 por medição — 21 de 21 itens que entravam só por ela eram código 0. Remover uma
    família inteira não quebrava nenhum teste antes deste.
    """
    from pipeline.classify.prefilter import EXCLUDED_FAMILIES, VIOLENCE_QUERIES
    from pipeline.ingest.queries import FAMILIES

    assert EXCLUDED_FAMILIES == {"contexto", "espectro"}
    for family in ("cargo", "evento"):
        assert FAMILIES[family], f"família {family} vazia: o teste não provaria nada"
        assert set(FAMILIES[family]) <= VIOLENCE_QUERIES
    for family in EXCLUDED_FAMILIES:
        assert not set(FAMILIES[family]) & VIOLENCE_QUERIES


def test_spectrum_query_alone_no_longer_passes():
    """O caso real que motivou a poda: termo de espectro + palavra que parece violência.

    "Mata" de Mata Atlântica e "se mata" como expressão entravam pela família espectro.
    """
    text = "araras-vermelhas retornaram à Mata Atlântica depois de 200 anos"
    spectrum_query = next(iter(FAMILIES["espectro"]))
    assert not matches_prefilter(text, [spectrum_query])
