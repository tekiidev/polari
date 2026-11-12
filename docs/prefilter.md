# Pré-filtro: recall medido (Fase 2)

**Pergunta:** quantos itens de violência política o pré-filtro barra antes do classificador?
O que ele barra nunca é classificado, então o recall dele limita o de todo o pipeline.

**Resposta curta: o pré-filtro aprova 7,9% dos itens e deixa passar 37,0% dos positivos**
(intervalo de 90%: 21,3% a 48,5%), medido em 11/11/2026 nos 60 itens barrados do gabarito
congelado — sorteados depois de o filtro estar pronto e rotulados às cegas.

O caminho até esse número, porque ele muda a leitura: a primeira medição deu **23%** (8% a 54%); o
pré-filtro foi corrigido a partir dos erros encontrados e a reavaliação deu **62%** (18% a 100%),
mas na **mesma amostra** usada para corrigi-lo — media o ajuste, não o filtro. A medição sem viés
derrubou o número para 36% e apertou o intervalo. Os 62% não devem ser citados.

Código: `pipeline/classify/prefilter.py` (regras) e `pipeline/classify/recall.py` (amostra e
estimativa). Régua: `eval/labeling_guide.md`. Os rótulos ficam em `eval/labeled_private/`, fora do git.

## Método

- **População:** 228.204 posts do Bluesky (`lang=pt`), de 01/06 a 04/11/2026, trazidos por 216
  consultas em 4 famílias (`pipeline/ingest/queries.py`).
- **Estratos:** família da consulta × aprovado/barrado. Um item trazido por várias consultas fica
  na família de violência, que tem prioridade sobre o contexto.
- **Amostra:** 147 itens sorteados com semente fixa. São 15 por estrato aprovado e 20 por estrato
  barrado (50 no barrado do contexto, o maior), ou o estrato inteiro quando ele é menor.
- **Rotulagem cega:** o arquivo rotulado tinha só ID e texto; o estrato ficava num arquivo à parte.
  Um rotulador (o autor), códigos `0`/`1`/`2`/`3` do guia. Tempo de rotulagem não cronometrado.
- **Estimativa:** positivos de cada estrato = tamanho × proporção rotulada; recall = positivos
  aprovados ÷ positivos totais. O intervalo vem de Monte Carlo com Beta de Jeffreys por estrato,
  na primeira medição, e de bootstrap estratificado, na reavaliação.

## Primeira medição

| família | status | população | rotulados | `1` Brasil | `2` outro país |
|---|---|---|---|---|---|
| cargo | aprovado | 516 | 15 | 8 | 0 |
| cargo | barrado | 12 | 12 | 1 | 0 |
| contexto | aprovado | 10.302 | 15 | 3 | 3 |
| contexto | barrado | 216.508 | 50 | 2 | 0 |
| espectro | aprovado | 399 | 15 | 4 | 0 |
| espectro | barrado | 111 | 20 | 0 | 0 |
| evento | aprovado | 351 | 15 | 8 | 3 |
| evento | barrado | 5 | 5 | 1 | 0 |

Nenhum item recebeu `3` (violência verbal).

- **Recall (Brasil):** 23,3% (8,5% a 54,2%).
- **Recall (qualquer país):** 35,5% (15,4% a 66,3%).

O número é dominado pelo **barrado do contexto**: cada um dos 2 positivos ali representa
~4.300 itens da população.

## Diagnóstico dos 4 positivos barrados

| caso (resumo) | por que foi barrado | o que mudou |
|---|---|---|
| matador de uma vereadora explica a execução, sem a palavra "vereadora" | "matador", "pistoleiro" e "execução" fora do léxico; nome da vítima sem cargo | itens de consultas de violência passam direto (regra `consulta`); léxico ampliado |
| governo estrangeiro interferindo nas eleições | sem vocabulário de interferência | nova regra `interferencia`, decorrente da decisão de 07/11 no guia |
| coligação aciona órgãos contra uma plataforma por atuação nas eleições | sem violência nem interferência de Estado | nada: pelo guia é `0` (plataforma não entra na regra de interferência) |
| crítica a um veículo por omitir denúncias | sem violência | passa agora pela regra `consulta`; pelo guia é `0` |

Três dos quatro estão na fronteira do escopo (interferência, plataforma, crítica à mídia), e não
são casos centrais de violência. A fronteira pesa mais no número do que o regex.

## Pré-filtro final

Aprova **18.034 de 228.204 itens (7,9%)**, já com a família espectro podada (ver abaixo).
Por regra (um item pode casar com várias):

| regra | itens |
|---|---|
| `politica` (violência + contexto político) | 12.813 |
| `interferencia` | 5.446 |
| `consulta` (famílias cargo e evento) | 884 |
| `evento` (ato + violência ou repressão) | 873 |
| `frase` ("violência política" etc.) | 236 |

A regra de interferência custa +38% de itens a classificar (de ~13,2 mil para ~18 mil).

**Recall preliminar com o pré-filtro final** (mesma amostra, estimador de Horvitz-Thompson com os
pesos do sorteio original):

- Brasil: **61,7%** (bootstrap 90%: 18,5% a 100%);
- qualquer país: **67,7%** (31,8% a 100%).

O único positivo ainda barrado é o caso da plataforma, rotulado `1`. Pelo guia atual ele é `0`;
nessa leitura, o recall pontual sobe para 100%. As duas leituras estão aqui porque o rótulo não foi
revisto.

## Medição sem viés (Fase 3, 11/11/2026)

`python -m eval.prefilter_recall report`, com os 60 itens barrados do gabarito congelado. Estes
foram sorteados **depois** de o pré-filtro estar pronto e rotulados às cegas (quem rotulou não
sabia o status do item), então não têm o viés de ajuste do número acima. Estatística idêntica à da
primeira medição, de propósito: dois estimadores diferentes para o mesmo número dariam uma
diferença impossível de atribuir.

| período | status | população | rotulados | `1` | `2` | `3` |
|---|---|---|---|---|---|---|
| baseline | aprovado | 3.540 | 30 | 21 | 1 | 0 |
| baseline | barrado | 30.128 | 15 | 1 | 0 | 0 |
| campanha_1t | aprovado | 6.373 | 40 | 23 | 0 | 0 |
| campanha_1t | barrado | 70.281 | 15 | 3 | 0 | 0 |
| entre_turnos | aprovado | 5.671 | 40 | 20 | 1 | 3 |
| entre_turnos | barrado | 82.316 | 15 | 0 | 0 | 0 |
| pos_eleicao | aprovado | 2.450 | 30 | 19 | 1 | 0 |
| pos_eleicao | barrado | 27.445 | 15 | 1 | 1 | 0 |

- **Recall (Brasil, sem ofensa verbal): 37,0%** (21,3% a 48,5%)
- Recall (Brasil, com ofensa verbal): 38,0% (21,8% a 49,3%)
- Recall (qualquer país, com ofensa verbal): 36,4% (21,5% a 47,2%)

Números com o gabarito da errata de 12/11 (`f1b74e5d…`). Com o gabarito original eram 35,8% (20,3% a
47,5%): a errata acrescentou positivos entre os aprovados e não mexeu nos barrados.

**O recall real é 37,0%, não 62%.** O intervalo nem alcança os 62%, e o documento já previa isso: a
estimativa anterior media o ajuste, não o filtro. O ganho maior não é o número, é o intervalo —
de 18%–100% ("não sei") para 20%–48%, porque o gabarito tem 60 barrados bem distribuídos. Dá para
afirmar com firmeza que **o pré-filtro perde quase dois terços dos positivos.**

### A falha não é uniforme no tempo

| período | barrados rotulados | positivos `1` | população barrada |
|---|---|---|---|
| baseline | 15 | 1 | 30.128 |
| campanha_1t | 15 | **3** | 70.281 |
| entre_turnos | 15 | **0** | 82.316 |
| pos_eleicao | 15 | 1 | 27.445 |

O filtro parece falhar **mais na campanha do 1º turno** e **menos entre os turnos**. Isso é pior do
que um recall baixo uniforme: recall uniforme rebaixa a escala da série e preserva a forma da
curva; recall que varia por período **distorce a forma**, que é o que o mapa e a linha do tempo
mostram. Se o filtro perde mais na campanha, a série subestima justamente o período de interesse.

Ressalva: 3 contra 0 em amostras de 15 pode ser ruído, e não se afirma tendência com isso. Fica
como risco declarado e como o primeiro alvo da triagem por LLM do estrato barrado (limite 2).

## Limites

1. **Viés de ajuste:** as regras foram corrigidas olhando os erros desta amostra. Medir nela de
   novo infla o recall. ~~A medida válida é a dos itens barrados do gabarito (Fase 3)~~ — **feita
   em 11/11/2026, acima: 37,0% (21,3% a 48,5%), após a errata de 12/11.**
2. **Intervalo largo no barrado do contexto:** são 216 mil itens e 50 rótulos. "0 de 50" ainda é
   compatível com milhares de positivos perdidos. Proposta para a Fase 3: o LLM faz a triagem de
   2 a 3 mil itens desse estrato, e o humano confere os positivos.
3. **Recall das consultas não medido:** o número vale para o pré-filtro *sobre o que as consultas
   trouxeram*. O que nenhuma consulta trouxe não aparece aqui. A checagem possível é cruzar com
   casos noticiados (Fase 2b).
4. **Um rotulador:** sem concordância medida (kappa), que fica para a Fase 3.
5. ~~**Grafias que driblam a moderação** ("facist4", "m0rte") não são normalizadas pelo regex.~~
   **Medido em 11/11/2026 e descartado.** Varredura dos 228.204 itens com dígito ou símbolo no
   lugar de letra nas raízes do escopo (`m[o0]rt`, `[a4]me[a4]c`, `[a4]ss[a4]ss[i1]n`, `t[i1]r`,
   `f[a4]sc[i1]st`, `g[o0]lp[i1]st`, entre outras): **23 itens, 0,010% do corpus**, dos quais 16
   barrados. Lidos um a um, **nenhum é positivo claro** pela régua: são hipótese retórica ("mesmo
   que apareça imagens do candidato matand8 crianças"), metáfora eleitoral ("o voto da sentença da
   sua própria M0RTE", "projeto de ódi0 e m0rt3"), desabafo sem alvo e ofensa a grupo (`3`). Um
   único caso seria `1` ("o plano dos golpistas era o ASS4SS1NAT0 DE LULA") — 1 item em 228 mil
   não move o recall.

   Por que a intuição falhou: ofuscação existe para escapar de moderação por palavra-chave, e o
   Bluesky não a aplica como as redes onde o hábito nasceu. Quem escreve assim ali está imitando
   um costume, não driblando um filtro — e o uso predominante é metafórico, que o escopo exclui.
   Normalizar custaria regex, testes e risco de falso positivo novo para ganho não mensurável.

## Precisão (aprovados rotulados)

Itens com `1` ou `2` entre os 15 aprovados de cada família: cargo 8, contexto 6, espectro 4,
evento 11. A precisão baixa é esperada (o pré-filtro prioriza recall).

## Poda da família espectro (11/11/2026)

A família **espectro** (termo de espectro político + termo de violência) deixou de bastar por si
para o item ser classificado (`EXCLUDED_FAMILIES` em `pipeline/classify/prefilter.py`). Decidido
por medição, não por preferência:

| evidência | número |
|---|---|
| precisão da família (Fase 2) | 4 de 15 |
| itens que entravam **só** por ela, em 5 meses | 111 |
| desses, positivos entre os 347 itens rotulados (dev + gabarito) | **0 de 21** |
| itens do gabarito que mudaram de estrato | 1, de rótulo `0` — o texto `"023"` |
| recall antes / depois | 36,0% / 35,8% |

O cruzamento casa demais: "**Mata** Atlântica" (araras voltando ao bioma), "o pessoal de lá **se
mata** antes de parar de dar dinheiro pra megacorporação", "existe vida fora do bluesky", adesivos
de cristal, Neymar fora de treino. O risco levantado antes de medir — de a família ser a única a
pegar incitação indireta — não se confirmou: nenhum positivo rotulado depende dela.

A queda de 0,2 ponto no recall não é positivo perdido; é o denominador dos estratos mudando (49
itens saíram de aprovado em todo o corpus). Reverter é tirar `"espectro"` de `EXCLUDED_FAMILIES`,
e dois testes em `tests/test_prefilter.py` quebram se isso for feito sem refazer a medição.
