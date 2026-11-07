# Pré-filtro: recall medido (Fase 2)

**Pergunta:** quantos itens de violência política o pré-filtro barra antes do classificador?
O que ele barra nunca é classificado, então o recall dele limita o de todo o pipeline.

**Resposta curta:** a primeira medição deu **23%** (intervalo de 90%: 8% a 54%). O pré-filtro foi
corrigido a partir dos erros encontrados. A estimativa com o pré-filtro final é **62%** (18% a
100%), mas é **preliminar e otimista**: foi calculada na mesma amostra usada para corrigi-lo. A
medida sem esse viés sai dos itens barrados do gabarito da Fase 3.

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

Aprova **18.145 de 228.204 itens (8,0%)**. Por regra (um item pode casar com várias):

| regra | itens |
|---|---|
| `politica` (violência + contexto político) | 12.813 |
| `interferencia` | 5.446 |
| `consulta` (famílias cargo, evento, espectro) | 1.394 |
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

## Limites

1. **Viés de ajuste:** as regras foram corrigidas olhando os erros desta amostra. Medir nela de
   novo infla o recall. A medida válida é a dos itens barrados do gabarito (Fase 3), sorteados
   depois do ajuste.
2. **Intervalo largo no barrado do contexto:** são 216 mil itens e 50 rótulos. "0 de 50" ainda é
   compatível com milhares de positivos perdidos. Proposta para a Fase 3: o LLM faz a triagem de
   2 a 3 mil itens desse estrato, e o humano confere os positivos.
3. **Recall das consultas não medido:** o número vale para o pré-filtro *sobre o que as consultas
   trouxeram*. O que nenhuma consulta trouxe não aparece aqui. A checagem possível é cruzar com
   casos noticiados (Fase 2b).
4. **Um rotulador:** sem concordância medida (kappa), que fica para a Fase 3.
5. **Grafias que driblam a moderação** ("facist4", "m0rte") não são normalizadas pelo regex.
   Medir o quanto aparecem antes de tratar.

## Precisão (aprovados rotulados)

Itens com `1` ou `2` entre os 15 aprovados de cada família: cargo 8, contexto 6, espectro 4,
evento 11. A precisão baixa é esperada (o pré-filtro prioriza recall), mas a família **espectro**
(4 de 15) é a candidata a ser podada se a cota do classificador apertar.
