# Avaliação dos LLMs classificadores

**O que este documento é:** o resultado da comparação prevista em
`docs/decisions/escolha-llm.md`, com os critérios fixados **antes** de qualquer modelo rodar. Os
critérios não foram alterados depois de ver resultado; onde algo mudou, a mudança está datada e
justificada aqui.

**O que ele não é:** uma recomendação geral de qual LLM é melhor. Mede-se uma tarefa estreita
(classificar discurso sobre violência política em português, com uma régua escrita) num corpus
específico, com um prompt que foi ajustado ao longo da própria avaliação. Os números valem para
esta tarefa.

## Resumo

- **Vencedor: `gpt-6-luna`**, F1 0,638 no código 1 (IC 95%: 0,537–0,726), contra 0,516 do
  `gpt-5.4-mini`. Diferença pareada +0,122 (IC +0,025 a +0,225), sem empate. Também é o mais
  barato por item, mas reprova no limite de custo (abaixo).
- **Os dois modelos locais (Qwen3 8B, Gemma 3 12B) saíram por tempo**: 103 h e 175 h para 25 mil
  itens, contra o limite de 48 h. Isso torna o BERTimbau da Fase 4 uma necessidade medida.
- **Simetria partidária: 0 de 20 pares divergentes** nos três modelos medidos. Com 20 pares, isso
  quer dizer "nenhuma assimetria detectável", não "simétrico": o limite superior de 95% é 13,9%.
- **Perfil comum: precisão ~0,88, recall ~0,50.** O número da série é um piso.
- **O gabarito passou por uma errata cega** (9 de 78 rótulos), que desmentiu a hipótese de quem a
  propôs e revelou uma regra que faltava no guia: interferência de plataforma.
- **Três defeitos de instrumento foram achados e corrigidos durante a avaliação**: falha de cota
  contada como erro do modelo, versão do prompt em dois lugares, e um par espelhado inválido que
  movia a assimetria exatamente até o limite eliminatório.
- **Os dois modelos pagos reprovam no custo** pelo preço padrão (US$ 18–21 e 22–28 para 25 mil
  itens, limite US$ 10). Resolver na Fase 4, antes da rotulagem em volume.

## O que foi medido contra o quê

| conjunto | n | para que serve | quantas vezes se roda |
|---|---|---|---|
| **dev** | 147 | ajustar o prompt | quantas vezes for preciso |
| **gold** (congelado) | 200 | decidir | uma vez por modelo |
| **mirrored** | 20 pares (40 textos) | eliminatório de simetria | uma vez por modelo |

A separação é o que dá validade ao resultado: o prompt foi corrigido olhando os erros do **dev**, e
a decisão sai do **gold**, que ninguém olhou antes de congelar. O gabarito tem SHA-256
`7423fb24…9f6a` registrado em `eval/gold.frozen.json`, e `eval/run.py` **recusa rodar** se o hash
não bater — rótulo corrigido depois do congelamento exige errata declarada, não silêncio.

### Por que o dev não serve para ranquear

Os 147 rótulos do dev são de 07/11 e a régua mudou duas vezes depois:

- **10/11, "afirmação basta":** textos que afirmam violência sem descrever o ato passaram de `0`
  para `1`. Os rótulos do dev não foram refeitos.
- **11/11, "o papel de quem comete também basta":** violência cometida por quem tem cargo político
  passou a contar.

Medido na revisão dos erros do `gpt-6-luna` (11/11): de 4 erros aparentes em 35 itens, **3 eram
defeito do conjunto ou do prompt** e 1 era erro do modelo. O F1 do dev subestima todos os
candidatos, e subestima cada um de forma diferente. Por isso o dev aparece aqui só como história do
ajuste.

## Candidatos

| candidato | o que é | versão fixada | privacidade |
|---|---|---|---|
| **gpt-5.4-mini** | API paga, OpenAI | ID exato no `.env` | texto sai da máquina; API comercial não treina por padrão |
| **gpt-6-luna** | API paga, OpenAI | ID exato no `.env` | idem |
| **Gemini 3.5 Flash** | API, plano gratuito | ID exato | idem |
| **Qwen3 8B** | pesos abertos, local (Ollama) | pesos locais | **o texto nunca sai da máquina** |
| **Gemma 3 12B** | pesos abertos, local (Ollama) | pesos locais | **idem** |

O Claude Haiku ficou implementado e testado (`pipeline/classify/backends.py`) mas fora da disputa:
exigia cartão na época da escolha. Entra depois da candidatura, quando acrescentar candidato custa
só a execução.

Os dois modelos locais eram candidatos de verdade, não figurantes: o projeto trata **dado sensível**
pela LGPD (`docs/decisions/lgpd.md`), e um classificador que roda sem o texto sair da máquina é o
argumento mais forte que o Polari poderia ter. Por isso a eliminação deles é registrada com o
número que a causou, não como nota de rodapé.

## Eliminados por tempo: os dois modelos locais

Limite fixado antes de medir: **≤ 48 h de relógio para 25 mil itens**, o que exige ~7 s por item.

| candidato | F1 (dev) | recall | latência mediana | p95 | projeção 25 mil itens | prompt |
|---|---|---|---|---|---|---|
| Qwen3 8B | 0,658 (0,52–0,77) | 0,889 | 14,8 s | 17,0 s | **103 h** | v2 |
| Gemma 3 12B | 0,638 (0,49–0,76) | 0,815 | 25,1 s | 43,9 s | **175 h** | v3 |

Ambos reprovam por 2× a 4× o limite. Dois achados que valem mais que a eliminação:

**Mais parâmetros não compraram acurácia nesta tarefa.** O Gemma tem 50% mais parâmetros, rodou com
um prompt melhor (v3 contra v2) e ficou com F1 estatisticamente igual ao do Qwen — intervalos
sobrepostos — gastando 70% mais tempo por item.

**A comparação entre os dois é inválida, e a causa era um defeito meu.** A versão do prompt estava
escrita em dois lugares (o arquivo e uma constante Python) e eles divergiram sem nada avisar.
Corrigido em 11/11: `prompt_version()` passou a ler a versão do título do próprio arquivo, com
teste que falha alto se ela faltar. O defeito não invalida a eliminação (que foi por tempo), mas
invalida o "Qwen melhor que Gemma". Era o bug mais perigoso do período: não dá erro, só grava a
série inteira com a procedência errada.

**O que isso decide para a Fase 4.** Nenhum LLM local escala para o volume do projeto. Isso
transforma o BERTimbau de preferência em necessidade medida: um modelo de ~110 M de parâmetros
classifica 25 mil itens em minutos, local, sem cota. A eliminação dos locais é um resultado melhor
do que se eles tivessem passado.

## Cotas: o que de fato limitou a avaliação

O eliminatório de custo (≤ US$ 10) não discriminou ninguém — todos os candidatos eram gratuitos ou
custavam centavos. **O que limitou foi a cota de requisições**, que nenhum critério previa:

| provedor | limite encontrado | efeito na avaliação |
|---|---|---|
| Gemini (plano gratuito) | 20 req/dia por modelo | inviabilizou o candidato: 126 de 147 itens falharam |
| OpenAI (Free tier) | 50 req/dia por modelo | bloqueou o dev no meio; execução parcial |
| OpenAI (tier Build, após US$ 5) | 5.000 req/min | destravou a avaliação completa (12/11) |
| Ollama (local) | nenhum | único sem limite, e o mais lento |

Isso reforça por um caminho inesperado a decisão original do modelo próprio: **cota é um risco
operacional que não aparece em nenhum benchmark de acurácia.**

### O erro de interpretação que quase entrou no relatório

Em 10/11 eu registrei para o Gemini **F1 0,194 e recall 0,111** e quase escrevi "o Gemini tem
recall ruim". Nos 21 itens que de fato rodaram, os números eram **F1 0,857 e recall 1,000, sem um
único falso negativo**. Os outros 126 falharam por cota (HTTP 429) e entraram na conta como erro
do modelo.

Correção implementada, não só anotada: `coverage_warning()` em `eval/metrics.py` avisa quando mais
de 5% dos itens falham por erro de API, e a flag `--only-completed` separa as duas coisas. Três
testes garantem que **JSON inválido continua pesando no F1** — esse é erro do modelo — enquanto
falha de infraestrutura não.

## O prompt mudou durante a avaliação: v1 → v4

Declarado porque afeta a comparabilidade: candidatos rodados em versões diferentes não são
comparáveis entre si, e a decisão final usa **só o v4**, no gabarito.

| versão | o que mudou | por quê |
|---|---|---|
| v1 → v2 | lista os valores de `violence_type`; corrige cabo eleitoral de `agente_publico` para `apoiador`; acrescenta `perpetrator_type`, `vinculo_eleitoral`, `country`; regra de simetria | problemas conhecidos da Fase 2 |
| v2 → v3 | contexto político passa a ter três formas explícitas, e **basta uma**; "afirmação basta" | o `gpt-5.4-mini` classificou "Vereadora foi morta a tiros em Caruaru" como **não** violência política, 3× de forma estável, justificando "não explicita motivação política" — e estava seguindo minha regra à risca |
| v3 → v4 | quarta forma de contexto político: **o papel de quem comete**; novo valor `perpetrator_type = "agente_politico"` | o `gpt-6-luna` recusou "senador teria agredido mulher em hospital" porque a regra definia contexto político só pela vítima |

As duas últimas são o mesmo padrão, e vale registrar: **em nenhum dos dois casos o modelo estava
errado.** Ele seguia uma regra incompleta minha. Se eu tivesse tratado o desacordo como erro do
modelo, teria escolhido o candidato pela capacidade de adivinhar o que eu quis dizer.

## Simetria partidária (eliminatório)

Limite: o rótulo muda em **≤ 5% dos pares** e a direção da divergência não é sistemática. Endurecido
de 10% para 5% em 09/11, quando o mapa público passou a ser a finalidade principal declarada.

### Um par inválido inflava a medida em 5 pontos

A primeira execução (Qwen, 11/11) deu **1 de 20 pares divergentes = 5,0%** — exatamente no limite.
Investigando o par, a divergência era **correta**: os dois textos não eram espelhos. O campo `a` do
par `p04` continha o texto de outro item do corpus (uma lista de vaquinhas eleitorais, rótulo `0`)
emparelhado com um xingamento a ex-presidente (rótulo `3`). A nota do par provava o erro: descrevia
uma troca ("Petista→Bolsonarista, Lula→Bolsonaro, 13→22") que não correspondia ao texto gravado.

O validador deixou passar porque exigia marcador de lado em cada texto e tamanhos parecidos — e o
par satisfazia os dois. Faltava checar o que define um par espelhado: **que os dois sejam o mesmo
texto**. Corrigido com `mirror_similarity()` (compara o conteúdo fora dos marcadores de lado, corte
em 0,6, calibrado nos dados: o pior par legítimo deu 0,81, o inválido 0,02).

Com o par corrigido, **Qwen: 0 de 20 pares divergentes (0,0%)**.

Por que isso importava além do Qwen: um par inválido em 20 move a assimetria em 5 pontos, que é o
próprio limite eliminatório, e ia inflar a medida de **todo** candidato rodado depois. Em 40 pares
seria 2,5 pontos — menos visível e igualmente errado. Rodar primeiro o modelo local e grátis foi o
que permitiu achar isso sem gastar cota paga medindo o próprio defeito.

### Limitação declarada: 20 pares, não 40 — e o eliminatório fica mais fraco do que parece

A meta eram ~40 pares (80 textos); há 20 (16 sintéticos, 4 do corpus). Duas consequências, e a
segunda é pior do que "intervalo largo":

**O limite de 5% equivale a um único par.** Com 20 pares, zero divergências passa e uma divergência
reprova (5,0% fica no limite, duas já são 10%). Não há granularidade entre "aprovado" e "reprovado".

**Zero de 20 não prova simetria.** O limite superior de 95% para 0 sucessos em 20 tentativas é
**13,9%**. Ou seja: um modelo cuja assimetria real seja de 10% — o limite que vigorava antes do
endurecimento de 09/11 — tem boa chance de passar neste teste sem nenhuma divergência aparecer. O
critério ficou mais rigoroso no papel do que a amostra consegue verificar.

Para reprovar uma assimetria de 5% com alguma confiança seriam necessários da ordem de 60 pares, e
para 10%, cerca de 30. Declarado em vez de compensado: o número publicado é "nenhuma assimetria
detectável em 20 pares", nunca "o modelo é simétrico". Ampliar os pares é a primeira coisa a fazer
se a simetria vier a decidir entre dois candidatos.

### Resultados

| candidato | pares divergentes | taxa | direção | eliminatório |
|---|---|---|---|---|
| **gpt-5.4-mini** | **0 de 20** | **0,0%** | — | **passa** |
| **gpt-6-luna** | **0 de 20** | **0,0%** | — | **passa** |
| **Qwen3 8B** | **0 de 20** | **0,0%** | — | **passa** (eliminado por tempo) |

Nenhum dos candidatos medidos até aqui trocou o rótulo ao trocar os lados políticos do texto, nem
uma vez em 20 pares. Com a ressalva do tamanho da amostra acima: 0 de 20 é compatível com uma taxa
real de até ~14% (limite superior de 95%), então o resultado afirma "nenhuma assimetria detectável
nesta amostra", não "simétrico".

O que o resultado **não** cobre: a decisão prevê medir assimetria **por UF** também, porque um
modelo que erra mais onde um lado predomina pinta estados com régua diferente. Com 20 pares não há
como abrir por UF. Fica para a Fase 5, quando houver volume classificado.

## Resultado no gabarito congelado

### Antes da errata (gabarito `7423fb24…`, 12/11)

Prompt v4, 200 itens, uma execução por modelo, zero falhas nos dois.

| candidato | F1 código 1 | IC 95% | precisão | recall | TP | FP | FN | TN | s/item | projeção 25 mil |
|---|---|---|---|---|---|---|---|---|---|---|
| **gpt-6-luna** | **0,662** | 0,560–0,750 | 0,880 | 0,530 | 44 | 6 | 39 | 111 | 3,7 | 25,7 h |
| gpt-5.4-mini | 0,538 | 0,420–0,641 | 0,889 | 0,386 | 32 | 4 | 51 | 113 | 1,4 | 9,6 h |

**Diferença pareada luna − mini: +0,124 (IC 95%: +0,025 a +0,229).** O intervalo não cruza zero:
pelo gabarito original, o luna vence sem empate. Reproduzível com
`python -m eval.metrics --set gold --compare luna openai --original-gold`.

Os dois têm o mesmo perfil: precisão alta (~0,88) e recall baixo. Quando dizem que é violência
política, quase sempre é; o problema está no que deixam de marcar.

### Por que houve errata

Lidos os 51 falsos negativos do `gpt-5.4-mini`, metade (25) caía em dois temas, e nos dois o
modelo aplicava o guia escrito **melhor do que eu** tinha aplicado ao rotular:

- **13 de interferência**, em que o texto fala de interferência como opinião ou especulação, ou
  atribui "interferir nas eleições" a um ator brasileiro ("vai arrastar o caso para interferir nas
  eleições", dito de um ministro). O guia só conta interferência de **Estado estrangeiro**,
  afirmada no texto.
- **12 de plataforma**: CPI das big techs, multa à Meta por descumprir ordem do TSE. O guia diz
  com todas as letras que **empresas e plataformas não entram** na regra de interferência.

Entre os outros 26 havia mais erros meus sem defesa: "fraude de voto por correio toda eleição"
(desinformação, excluída pelo guia), emendas suspeitas de senador (corrupção, excluída), uma idosa
que caiu da escada na escola onde votou (acidente).

A hipótese, antes da revisão, era que a régua "afirmação basta" (10/11) tinha sido aplicada larga
demais, como "o texto fala de política com palavra forte". **A revisão cega desmentiu essa
hipótese** (abaixo): o gabarito estava mais consistente do que ela supunha, e a divergência real
era outra.

### Como a errata foi feita (e o viés que ela ainda tem)

Corrigir só os itens que o modelo errou transformaria o gabarito em espelho do modelo. Por isso:

1. **Critério antes de rótulo.** Três critérios, cada um tirado de uma exclusão **escrita** do guia
   (`ERRATA_RULES` em `eval/gold.py`): `plataforma`, `interferencia`, `fora_do_escopo`.
2. **Todos os 200 itens, qualquer rótulo.** Os critérios alcançam 78 itens, sendo 25 hoje `0`, que
   podem virar `1`. A revisão não é só para derrubar positivos.
3. **Às cegas.** Quem rerrotula vê só o texto: nem o rótulo atual, nem o de modelo algum.
   "Não sei" mantém o rótulo original.
4. **Sem critério para caso isolado.** A idosa que caiu da escada não ganhou regra própria: regra
   feita para um erro visto é o mesmo que corrigir o erro à mão. Esses ficam como estão.
5. **Hash antigo preservado** em `eval/gold.frozen.json` (`history`), cada rótulo trocado com o
   valor anterior, e o número de antes reproduzível.

**Viés que sobra, declarado:** os critérios foram formulados *depois* de ler os erros de um modelo.
Aplicá-los a todos os itens e rotular às cegas reduz esse viés, mas não o elimina — os temas
escolhidos são justamente aqueles em que o mini errou. O número de depois deve ser lido como "o
gabarito corrigido nos pontos em que se descobriu que ele contrariava o guia", não como um
gabarito independente novo.

### O que a revisão cega mostrou

78 itens revisados às cegas, nenhum marcado como "não sei". **9 mudaram**, e o saldo foi para
**mais** positivos, não menos:

| troca | itens |
|---|---|
| `0→1` | 5 |
| `0→3` | 1 |
| `2→1` | 1 |
| `1→0` | 1 |
| `3→0` | 1 |

Hash novo `f1b74e5d…`; o anterior (`7423fb24…`) está em `history`, em `eval/gold.frozen.json`.

Dois achados, e nenhum era o esperado:

**1. A divergência era de regra, não de rótulo.** Com o resumo do guia na tela dizendo "plataformas
não entram", o autor manteve como `1`, de forma consistente, os textos de interferência de
plataforma ("as plataformas têm interferido no fluxo de informações durante as eleições",
"Zuckerberg resolveu interferir na eleição brasileira"). Era a regra que ele de fato aplicava, e ela
não estava no guia nem no prompt — por isso o modelo, que segue o texto, marcava `0`. Os dois lados
eram coerentes com regras diferentes. Decidido em 12/11: **plataforma conta, como tipo próprio e
camada separada no mapa** (`eval/labeling_guide.md`; prompt v5, abaixo).

**2. Itens duplicados no gabarito.** O mesmo texto de campanha ("Acabei de pressionar deputados
pela CPI das Big Techs", em duas variações) ocupa **5 dos 200 itens**. Um único julgamento pesa 5
vezes no F1. O gabarito não foi deduplicado depois de congelado (seria outra mudança pós-resultado);
fica declarado. Para a série, o achado é maior: campanhas de copiar e colar inflam a contagem, e a
agregação (Fase 5) precisa deduplicar textos quase iguais.

### Depois da errata (gabarito `f1b74e5d…`)

| candidato | F1 código 1 | IC 95% | precisão | recall |
|---|---|---|---|---|
| **gpt-6-luna** | **0,638** | 0,537–0,726 | 0,880 | 0,500 |
| gpt-5.4-mini | 0,516 | 0,400–0,617 | 0,889 | 0,364 |

**Diferença pareada luna − mini: +0,122 (IC 95%: +0,025 a +0,225).** O F1 dos dois caiu um pouco
(mais positivos no gabarito, que os dois não marcaram), e a diferença entre eles ficou praticamente
igual. A ordem não depende da errata.

## Decisão (12/11/2026)

**O `gpt-6-luna` classifica o Polari.** Pela regra fixada antes de rodar: entre os aprovados nos
eliminatórios, vence o maior F1, e a diferença para o segundo não é empate.

| eliminatório | limite | gpt-6-luna | gpt-5.4-mini |
|---|---|---|---|
| JSON inválido | ≤ 2% | 0,0% | 0,0% |
| versão fixável | ID exato | `gpt-6-luna` | `gpt-5.4-mini` |
| tempo para 25 mil itens | ≤ 48 h | 25,7 h | 9,6 h |
| simetria | ≤ 5% | 0 de 20 | 0 de 20 |
| custo para 25 mil itens | ≤ US$ 10 | **US$ 18–21 (reprova)** | **US$ 22–28 (reprova)** |
| **F1 código 1** (principal) | — | **0,638** | 0,516 |

Diferença pareada +0,122 (IC 95%: +0,025 a +0,225): não cruza zero, então não há empate e os
critérios de desempate não entram.

**Os dois reprovam no custo, e a regra não prevê esse caso.** Medido no painel de uso da OpenAI
(12/11, gasto por item de cobrança) e dividido pelas chamadas cobradas registradas em
`eval/results/`:

| | gpt-6-luna | gpt-5.4-mini |
|---|---|---|
| gasto na semana | US$ 0,34–0,40 | US$ 0,24–0,30 |
| chamadas cobradas | ~480 | ~270 |
| custo por item | US$ 0,0007–0,0008 | US$ 0,0009–0,0011 |
| 18 mil itens (só aprovados) | US$ 13–15 | US$ 16–20 |
| 25 mil itens (volume do critério) | US$ 18–21 | US$ 22–28 |

A faixa vem de itens de cobrança pequenos agrupados pelo painel ("7 other", US$ 0,06) que não se
separam por modelo. O mini sai **mais caro** por item que o luna, então trocar de modelo não resolve:
o luna é o melhor em qualidade e em preço.

O maior custo do luna é **gravação de cache** (US$ 0,257, ~2/3 do gasto dele). O prompt tem ~4.200
tokens fixos; o cache deveria ser gravado poucas vezes e depois lido, que é mais barato. Pelo valor,
está sendo regravado quase a cada chamada. **A escolha do modelo fica feita pela qualidade, e o custo
é a primeira tarefa da Fase 4**, antes da rotulagem em volume: (1) entender e evitar a regravação do
cache; (2) confirmar na documentação se a Batch API vale para o luna e com que desconto — com metade
do preço, ~US$ 9–10 para 25 mil itens; (3) se nada bastar, o autor decide se o limite sobe, e a
mudança fica registrada como alteração de critério depois do resultado.

**O que a decisão não diz.** F1 0,638 é baixo em termos absolutos, e o perfil dos dois modelos é o
mesmo: precisão alta (~0,88), recall baixo (~0,50). Quando o luna marca violência política, quase
sempre é; ele deixa de marcar metade. Combinado com o pré-filtro, que já perde 64% dos positivos, o
pipeline vê uma fração pequena do fenômeno. Isso não impede a série (o que importa para comparar
períodos e UFs é o recall ser **estável**, não alto), mas obriga a metodologia a dizer que o número
é um piso, e o recall por período e por tipo vira a primeira coisa a medir na Fase 5.

### Prompt v5, depois da decisão

A regra de plataforma (12/11) entrou no prompt como v5, **depois** de o gabarito ter sido visto. O
número do v5 no gabarito não é uma medida independente e não substitui o do v4: serve só para
verificar que a regra nova não estragou os outros itens, antes de o v5 rotular o volume da Fase 4.

| prompt | F1 código 1 | IC 95% | precisão | recall | TP | FP | FN |
|---|---|---|---|---|---|---|---|
| v4 (decisão) | 0,638 | 0,537–0,726 | 0,880 | 0,500 | 44 | 6 | 44 |
| v5 (pós-hoc) | 0,755 | 0,672–0,828 | 0,905 | 0,648 | 57 | 6 | 31 |

**O 0,755 não é o resultado do projeto.** A regra que o produziu foi escrita depois de ver o
gabarito, então parte da subida é esperada por construção. O número que vale para a decisão continua
sendo 0,638, e o próximo número independente sai de um conjunto que o v5 não viu.

De onde veio a diferença — 19 itens trocaram de lado entre as duas execuções:

| itens | troca | origem | v5 |
|---|---|---|---|
| 11 | `0→1` | plataforma | acertou |
| 1 | `0→1` | plataforma | errou (falso positivo) |
| 4 | `0→1` | outros | acertou |
| 1 | `1→0` | outros | acertou |
| 2 | `1→0` | outros | errou |

A regra nova fez o que devia: 12 itens marcados como `interferencia_plataforma`, 11 certos. Fora
dela, 7 itens mudaram, com saldo de +3 acertos e nenhum sinal de regressão. Sem uma segunda
execução do v4, não dá para separar o efeito do prompt da variação natural entre execuções nesses
7; a concordância entre execuções, prevista como métrica relatada, fica para a Fase 4.

## Limitações desta avaliação

1. **Um único rotulador.** Os 200 rótulos do gabarito são de uma pessoa. Sem segundo rotulador não
   há kappa, e portanto não há como afirmar que a régua é reproduzível por outra pessoa. É a
   limitação mais séria do trabalho: toda a avaliação mede concordância com **um** julgamento.
2. **O prompt foi ajustado durante a avaliação** (v1→v4). O gabarito nunca foi usado para isso,
   mas o prompt foi corrigido a partir de erros vistos no dev — que é o procedimento correto e,
   ainda assim, significa que o v4 é adaptado a este corpus.
3. **20 pares espelhados**, não 40 (acima).
4. **O recall do pipeline é limitado antes do classificador.** O pré-filtro deixa passar 35,8% dos
   positivos (`docs/prefilter.md`), então o melhor classificador possível ainda vê pouco mais de um
   terço do fenômeno. O F1 aqui mede o classificador, não o sistema.
5. **Dois modelos locais eliminados por tempo em hardware específico** (máquina pessoal, Ollama).
   Em GPU dedicada a conclusão poderia mudar; o que não muda é que a Fase 4 roda neste hardware.
6. **Bootstrap pareado entre dois candidatos, não três** como previsto: os locais saíram nos
   eliminatórios antes de chegar ao gabarito.
7. **Errata pós-resultado.** Os critérios da revisão foram formulados depois de ler os erros de um
   modelo. A revisão cega e a aplicação a todos os itens reduzem o viés, mas não o eliminam. O
   número de antes da errata continua publicado e reproduzível (`--original-gold`).
8. **5 dos 200 itens são o mesmo texto de campanha**, e o gabarito não foi deduplicado.
9. **Custo medido pelo painel, não por tabela de preços**: dividido por chamadas estimadas, com
   US$ 0,06 que não se separam por modelo (acima).
