# Decisão: qual LLM classifica os posts

**Status:** proposta (Fase 3, 07/11/2026). Critérios escritos **antes** de rodar qualquer modelo no
gabarito; depois da primeira execução no gabarito, este arquivo só recebe resultados, não muda de
regra. Mudança de regra depois disso precisa ser registrada aqui com data e motivo.

## Problema

O classificador decide o que entra na série. O mesmo modelo ainda rotula em volume o treino do
BERTimbau (Fase 4) e atende os casos de baixa confiança em produção (Fase 5). O Gemini entrou no
projeto por ter plano gratuito, não por medição.

## Candidatos (revistos em 10/11: três opções sem custo)

A versão anterior tinha "um pago barato" (Claude Haiku 5.5). Trocado por um segundo modelo local,
por dois motivos: o projeto tem custo de API de R$ 0 e isso é parte do que ele demonstra; e um
candidato que exige cartão de crédito empurraria a Fase 4 (18 mil itens) para US$ 2–5 e um cadastro
que não é necessário. O Haiku fica registrado como candidato para depois da candidatura.

| | A: Gemini Flash | B: Qwen3 8B | C: Gemma 3 12B |
|---|---|---|---|
| Onde roda | API do Google | Ollama local (Apple M5, 16 GB) | Ollama local |
| Versão | ID estável, nunca alias `-latest` | pesos com digest fixo, Ollama 0.40.16 | idem |
| Custo | plano gratuito | zero | zero |
| Saída estruturada | `response_json_schema` do SDK | `format` com JSON schema | idem |
| Uso dos dados | **o Google pode usar entradas e saídas, e revisores humanos podem lê-las** | nada sai da máquina | nada sai da máquina |
| Origem do treino | EUA (Google) | China (Alibaba) | EUA (Google) |

**Por que dois modelos abertos de origens diferentes:** o teste de simetria fica mais informativo.
Qwen (China) e Gemma (EUA) foram treinados com dados e políticas distintas; se os dois tratarem os
lados da política brasileira de forma igual, é um resultado melhor do que medir um só.

Limite de hardware: 16 GB rodam um modelo por vez, não os dois juntos. Se o Gemma 12B ficar lento
demais no conjunto de desenvolvimento, ele cai e sobram dois candidatos — declarado, não escondido.

**Efeito nos eliminatórios:** o de custo (≤ US$ 10) deixa de discriminar, já que todos são
gratuitos. O de **tempo** (≤ 48 h para 25 mil itens, ou ~7 s por item) passa a ser o que elimina de
verdade, e é o risco real dos modelos locais.

## Protocolo

1. **Desenvolvimento e teste separados.** O prompt é ajustado só nos 147 itens rotulados na Fase 2
   (`eval/labeled_private/prefilter_sample.csv`). O gabarito de 200 não é visto por nenhum modelo
   antes do congelamento, e não compartilha itens com o conjunto de desenvolvimento.
2. **Gabarito congelado.** O SHA-256 de `gold.jsonl` é registrado abaixo antes da primeira
   execução. Rótulo errado descoberto depois vira nota de errata, com o F1 antes e depois. Nunca
   se troca o rótulo em silêncio.
3. **Mesmo prompt para os três** (`prompts/classifier.md`, v2). Só o envelope muda (onde vai o
   schema e a instrução de sistema). Os parâmetros de geração de cada provedor ficam fixos e
   registrados no resultado.
4. **Duas execuções completas por modelo.** A concordância entre elas mede a estabilidade; as
   métricas usam a primeira.
5. **O código 0–3 sai dos campos do schema** por uma regra única em código
   (`is_political_violence`, país, `violence_type = ofensa`). O modelo não escolhe o código
   diretamente.
6. **Sem nova tentativa por "resposta ruim".** Só se repete a chamada quando o JSON é inválido
   (uma vez) ou há erro de rede. Persistindo, o item conta como erro: entra nas métricas como
   negativo previsto e na taxa de JSON inválido.

## Critérios

### Eliminatórios (reprovou, sai)

| critério | limite | motivo |
|---|---|---|
| JSON inválido após 1 nova tentativa | ≤ 2% dos itens | acima disso a série ganha buracos que não são aleatórios |
| Versão fixável | ID imutável ou pesos locais | sem isso, a série mistura modelos sem aviso (ver teste de deriva em `eval/README.md`) |
| Custo de rotular 25 mil itens | ≤ US$ 10 | 18.145 aprovados + triagem de 2–3 mil barrados + folga |
| Tempo de rotular 25 mil itens | ≤ 48 h de relógio | a Fase 4 começa logo depois; local exige ≤ ~7 s por item |
| **Simetria partidária** | rótulo muda em **≤ 5%** dos pares espelhados, e o intervalo de 95% da assimetria contém zero | ver abaixo |

**Simetria é o eliminatório mais duro, e foi endurecido de 10% para 5% em 09/11**, quando o mapa
público passou a ser a finalidade principal declarada do projeto. Um par espelhado é o mesmo texto
com os lados políticos trocados ("bolsonarista agrediu petista" ↔ "petista agrediu bolsonarista");
pelo guia de rotulagem, os dois recebem o mesmo rótulo, porque a violência é a mesma. Se o modelo
discorda de si mesmo, a série é medida com régua diferente conforme quem aparece como agressor — e
o F1 agregado não revela isso, porque um modelo pode acertar 85% dos itens errando justamente de
forma assimétrica.

Três decisões que vêm disso:

- **A assimetria se mede também por UF**, não só no total. Um modelo que erra mais onde um lado
  predomina pinta estados com régua diferente, e o mapa é exatamente o que faz essa comparação
  parecer legítima.
- **A direção importa mais que a taxa.** 5% de divergência distribuída ao acaso é ruído de
  temperatura; 5% sempre no mesmo sentido é viés. Por isso o critério tem as duas partes.
- **Os pares são construídos à mão**, a partir de posts reais do corpus, nunca por substituição
  automática: "petista" e "bolsonarista" têm frequências muito diferentes nos dados de treino e a
  troca costuma quebrar a frase. Cerca de 40 duplas (80 textos), revisadas item por item.

Textos espelhados são sintéticos: entram **só** na medida de simetria, nunca no F1, que é medido
apenas em texto que alguém escreveu de verdade.

### Principal

**F1 do código `1`** (violência política no Brasil contra todo o resto) no gabarito, com intervalo
de 95% por bootstrap pareado (os três modelos nos mesmos itens reamostrados).

### Regra de decisão

1. Entre os aprovados nos eliminatórios, vence o maior F1.
2. **Empate:** a diferença para o segundo tem intervalo pareado que cruza zero. Com ~200 itens é
   o resultado mais provável, e o empate é decidido, em ordem, por:
   1. **simetria:** menor assimetria nos pares espelhados, mesmo entre dois modelos que passaram no
      eliminatório. O produto final é um mapa público sobre violência política; entre dois
      classificadores igualmente precisos, vale mais o que trata os lados de forma igual;
   2. privacidade: local > API sem treino > API que usa os dados;
   3. recall do código `1` (o pré-filtro já perde casos antes do classificador; perder mais é pior
      que ganhar falso positivo, que o BERT e a revisão ainda filtram);
   4. custo por item;
   5. latência.

### Relatados, sem peso na decisão

- precisão e recall do código `1`; F1 de `1` + `2`; código `3` à parte;
- acurácia de `violence_type`, `report_nature` e `target_type` nos verdadeiros positivos;
- calibração de `confidence` (decide o limiar do roteamento BERT → LLM na Fase 5);
- concordância entre as duas execuções;
- tokens, custo e latência por item (mediana e p95).

## Configuração medida antes de avaliar (10/11)

Teste de fumaça com 3 a 5 itens do desenvolvimento, antes de qualquer execução longa. Duas
descobertas mudaram a configuração dos candidatos, e as duas são sobre **latência**, que é o
eliminatório que discrimina agora que todos são gratuitos.

**1. `gemini-2.5-flash` foi descontinuado para contas novas** (404 com indicação do substituto). A
chave foi criada em 10/11, então o modelo do `.env` desde a Fase 1 nunca teria funcionado.

**2. O Flash mais novo é inutilizável no plano gratuito.** Medido no mesmo item e no mesmo prompt:

| modelo | com raciocínio | sem raciocínio |
|---|---|---|
| `gemini-3.8-flash` | 206 s/item | **194 s/item** |
| `gemini-3.6-flash` | 5,1 s | — |
| `gemini-3.5-flash` | 7,2 s (≈1.000 tokens de pensamento) | **3,3 s** |
| `gemini-3.1-flash-lite` | 1,7 s (não raciocina) | — |

Como desligar o raciocínio no 3.8 não mudou nada (206 → 194 s), a lentidão **não é geração**: é
fila do modelo mais novo no plano gratuito. Os três modelos acertaram a mesma resposta no item de
teste. **Escolhido `gemini-3.5-flash` com `thinking_budget: 0`**, que chegou a 1,7 s por item na
medição com 5 itens. O `-lite` fica como alternativa se a cota apertar.

**3. Os dois modelos locais raciocinam por padrão, e isso os reprovaria.** Qwen3 gastava 450–630
tokens de saída para um JSON de ~80, a 29 s por item. Com `think: false`, caiu para **6,4 s**, sem
nenhum erro de JSON.

**4. A cota do plano gratuito é 20 requisições por dia, por modelo** (`quotaId:
GenerateRequestsPerDayPerProjectPerModel-FreeTier`, medido em 10/11 com a chave do projeto). Não
1.500, como as fontes públicas diziam — por isso o documento mandava conferir no AI Studio em vez
de presumir. O `retryDelay` devolvido foi de 26.613 s, ou seja, 7 horas.

Consequência: **o Gemini no plano gratuito não serve para este projeto.**

| uso | com 20 req/dia |
|---|---|
| gabarito de 200 itens | 10 dias por modelo |
| rotulagem da Fase 4 (18 mil itens) | ~2,5 anos |

Na execução dos 147 itens de desenvolvimento, 21 passaram e **126 falharam com 429**. A cota é por
modelo, então ela se contorna espalhando as chamadas por vários modelos (3.1-lite, 3.5, 3.6…) — mas
aí não é um candidato, são vários, e a comparação perde sentido. Caminhos: só modelos locais;
Gemini pela Vertex AI com o crédito do Google Cloud da Fase 1, se ainda válido; ou plano pago.

**5. Falha de infraestrutura quase virou conclusão errada sobre o modelo.** O relatório mostrou
F1 de 0,194 e recall de 0,111 para o Gemini, com 24 "falsos negativos" — todos itens bloqueados
pela cota, que o modelo nunca viu. Nos 21 que ele de fato classificou: **F1 0,857, recall 1,000,
zero falsos negativos**.

A regra de contar falha como negativo previsto está certa para falha **do modelo** (JSON inválido,
recusa), porque descartá-la inflaria o F1. Está errada para falha **de infraestrutura**. Desde
então `eval/metrics.py` avisa quando erros de API passam de 5% dos itens e diz que o F1 não mede o
classificador naquele caso; `--only-completed` separa diagnóstico de resultado oficial. Três testes
cobrem a distinção.

### Situação dos candidatos após o teste de fumaça

| candidato | modelo | s/item | JSON inválido | projeção 25 mil itens | eliminatório de tempo |
|---|---|---|---|---|---|
| A | `gemini-3.5-flash` | 1,7 | 0/5 | ~12 h | **passa** |
| B | `qwen3:8b` (think off) | 6,4 | 0/3 | ~44 h | **passa, no limite** |
| C | `gemma3:12b` (think off) | 19,1 | 0/3 | ~133 h | **reprova** (limite 48 h) |

O Gemma 3 12B reprova no tempo e tende a sair, como previsto no risco de hardware (16 GB rodam um
modelo por vez). A decisão final espera a execução no conjunto de desenvolvimento, porque a
latência de 3 itens pode não representar a de 147 — mas a margem é grande demais para esperar
reversão. Nenhum dos três errou JSON até aqui, o que é um bom sinal para o schema e o prompt v2.

## Escopo da Fase 3 (revisto em 09/11)

A finalidade principal do projeto passou a ser declarada como o mapa público (`CLAUDE.md`,
"Objetivo"). Isso muda a pergunta da fase: não é "qual LLM tem o F1 mais alto", é "a régua é
confiável o bastante para um número ir ao ar com o nome Polari". Consequências:

**Sobe de prioridade**
- Pares espelhados: de opcional no fim para eliminatório, medidos junto do gabarito (passo 5).
- Assimetria por UF, que não estava prevista.

**Desce ou sai da fase**
- **Modelo aberto local: último da fila**, e o primeiro a cair se o prazo apertar (instalar Ollama,
  escolher entre Qwen3 8B e Gemma 3 12B e acertar JSON em modelo pequeno são horas que podem virar
  um dia). Se cair, vira pendência em "Problemas conhecidos", não resultado omitido. Vale notar que
  ele não resolveria o pipeline diário de qualquer forma: o runner do Actions é efêmero e sem GPU,
  e quem roda todo dia é o BERTimbau.
- **Triagem por LLM dos 2–3 mil itens barrados:** vai para a Fase 4, junto da rotulagem em volume.
  O recall sem viés continua na Fase 3, medido pelos itens barrados do gabarito.
- **Kappa com segunda pessoa:** mantido como desejável; sai se não houver rotulador disponível.

Gabarito, avaliação dos dois modelos de API e teste de simetria não saem em nenhuma hipótese.

## Decidido em 10/11: Gemini no plano gratuito

Opção (a) das que estavam em aberto. O gabarito são 200 posts públicos, sem handle nem URI, então
o risco concreto de enviá-los a um plano que pode usá-los é pequeno. Em troca:

- **a privacidade pesa contra o Gemini no desempate** (critério 2), e ele só vence se o F1 ficar
  acima do segundo colocado **fora** do empate estatístico;
- **se o Gemini vencer, a rotulagem em volume da Fase 4 vai para o plano pago**, onde o Google não
  usa os dados. Não se manda 18 mil posts para o plano gratuito;
- a cota real do plano gratuito é conferida no AI Studio antes da execução, não presumida: as
  fontes públicas divergem entre ~20 e ~1.500 chamadas por dia.

Candidato de outra empresa (OpenAI e afins): fora desta fase. Um terceiro modelo de API não
acrescenta ponto novo na curva de privacidade, custo e reprodutibilidade — o modelo local
acrescenta —, e cada backend custa meio dia. Fica como pendência para depois da candidatura, quando
a infraestrutura de avaliação já aceita um backend novo em poucas horas.

## Registro

- **SHA-256 de `gold.jsonl`: `7423fb24f4208960726d35e5a648903dd2b2b6a80a3346d91aed580006ea9f6a`**
  (congelado em 10/11/2026, antes de qualquer execução de modelo; contagens em
  `eval/gold.frozen.json`).
- **Composição:** 200 itens — 109 código `0`, 83 `1`, 5 `2`, 3 `3`; 5 marcados como difíceis.
  140 aprovados pelo pré-filtro (78 positivos, precisão de 56%) e 60 barrados (5 positivos).
  Positivos por período: 20 baseline, 26 campanha 1T, 19 entre turnos, 18 pós-eleição.
- **Régua:** `eval/labeling_guide.md` na versão de 10/11/2026, que inclui a regra "afirmação
  basta". 14 itens foram revisados de `0` para `1` por causa dessa mudança, com data e motivo
  gravados em cada linha; o congelamento é posterior à revisão.
- **Limites declarados do gabarito:** com 3 itens de código `3` e 5 de código `2`, ele **não mede**
  a camada de ofensa verbal nem a de casos fora do Brasil. O `3` é raro porque o pré-filtro não tem
  léxico de insultos (`docs/prefilter.md`); medir essas duas camadas exige amostra própria, fora
  desta fase.
- Resultados: `docs/eval-llm.md` (a criar)

## Fontes

- [Gemini API — Additional Terms of Service (prévia)](https://ai.google.dev/gemini-api/terms_preview): uso de dados em serviços não pagos e revisão humana. Conferir a versão vigente.
- [Anthropic — Commercial Terms](https://www.anthropic.com/legal/commercial-terms) e [suporte: dados enviados pela API](https://support.anthropic.com/en/articles/7996875-can-you-delete-data-that-i-sent-via-api): sem treino com dados da API por padrão; prazo de retenção a conferir.
- Preço e ID do Haiku 5.5: documentação da API da Anthropic (tabela de modelos, outubro de 2026).
