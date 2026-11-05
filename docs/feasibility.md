# Viabilidade (Fase 1)

**Pergunta:** as fontes alcançam o período pré-eleição com volume suficiente para comparar antes
e depois dos turnos?

**Resposta curta:** o Bluesky alcança, sem perda de histórico. O volume sustenta comparações
**nacionais, por período ou por semana**. Não sustenta comparações por UF e por dia. As
notícias (GDELT) não foram medidas: a API bloqueou as requisições (ver "Pendências").

Dados: [`feasibility/bluesky_daily.csv`](feasibility/bluesky_daily.csv) (dia local × termo × total)
e [`feasibility/bluesky_verify.csv`](feasibility/bluesky_verify.csv). Só contagens, nenhum texto.
Para reproduzir: `python -m pipeline.feasibility bluesky --start 2026-06-01 --end 2026-11-02 --verify`
e depois `python -m pipeline.feasibility summary`. Coleta feita em 03/11/2026.

## Método

- `app.bsky.feed.searchPosts` com login, `lang=pt`, um intervalo [00:00, 24:00) por dia local
  (America/Sao_Paulo), de 01/06 a 02/11/2026 (155 dias).
- Lemos o campo `hitsTotal` da primeira página: é uma requisição por termo e por dia, em vez de
  paginar tudo.
- **Conferência do `hitsTotal`:** em 11 dias (a cada 15), paginamos "eleição" por completo. O
  `hitsTotal` superestima em média 2,6% (mínimo 0%, máximo 8,3%), provavelmente por posts
  removidos ou moderados que entram na contagem mas não são devolvidos. Isso basta para estimar
  ordem de grandeza; a coleta da Fase 2 conta os itens um a um.
- Termos (a busca do Bluesky faz AND entre as palavras):
  - **contexto** (denominador): eleição, eleições, candidato, voto;
  - **violência** (numerador aproximado): 13 combinações curtas de violência + contexto (lista em
    `pipeline/feasibility.py`).

## Resultados

Soma dos 13 termos de violência. Ela superestima o total porque um post pode casar com mais de um
termo, e ainda **não foi classificada**: inclui opinião, notícia e falsos positivos.

| período | dias | média/dia | total | dia mais fraco | "eleição"/dia | violência ÷ "eleição" |
|---|---|---|---|---|---|---|
| baseline (01/06–15/08) | 76 | 11,4 | 867 | 2 | 104 | 11,0% |
| campanha 1º turno (16/08–04/10) | 50 | 18,7 | 935 | 3 | 388 | 4,8% |
| entre turnos (05–25/10) | 21 | 29,7 | 624 | 12 | 972 | 3,1% |
| pós-eleição (26/10–02/11) | 8 | 38,8 | 310 | 15 | 1.000 | 3,9% |

- Por semana: 23 semanas, de 15 a 295 itens (mediana 91). O pico foi a semana encerrada em
  01/11, depois do 2º turno.
- Nas janelas D±14: 773 itens em torno do 1º turno (29 dias). Em torno do 2º turno, 698 itens,
  mas só com 21 dos 29 dias, porque a janela vai até 08/11.
- "violência política" responde por cerca de metade do volume e tende a ser discussão do tema,
  não relato de caso. Termos de casos centrais ("candidato baleado", "vereadora assassinada")
  ficam perto de zero por dia.

Tabela completa por termo: `python -m pipeline.feasibility summary`.

## O que isso significa

1. **A retrospectiva é viável.** O índice do Bluesky cobre todo o período, inclusive a linha de
   base, e não expira. O motivo previsto para trocar o escopo por "pós-eleição em diante" não
   se confirmou.
2. **A granularidade precisa ser revista.** Com ~10–40 candidatos por dia **no país inteiro**,
   antes da classificação, um recorte por UF × tipo × dia com mínimo k=3 fica quase todo vazio.
   O que os números sustentam é uma série **nacional semanal**, com UF só no total de cada
   período. Decisão da Fase 5; aqui fica registrado o limite.
3. **A taxa depende muito do denominador.** O total sobre "eleição" cresce 10× do baseline ao
   pós-eleição; a violência cresce 3,4×. Por isso a taxa *cai* durante a campanha enquanto o
   volume *sobe*. As duas leituras precisam aparecer juntas, como já prevê a decisão "taxa **e**
   volume". A escolha do denominador vai para a metodologia (Fase 5).
4. **Viés da fonte:** o Bluesky brasileiro não é uma amostra da população, nem do eleitorado, nem
   das redes em geral. As conclusões valem para o discurso *nesta plataforma*.

## Pendências

- **Notícias (GDELT) não medidas.** A DOC API do GDELT respondeu 429 a todas as requisições deste
  IP, mesmo com uma requisição isolada após mais de 15 minutos. Os arquivos brutos do GDELT 2.0
  continuam disponíveis (testado com 01/03/2026), então **não há urgência de perda**. Opções:
  repetir a DOC API de outra rede, ou contar pelo BigQuery (`gdelt-bq.gdeltv2`, cota gratuita,
  exige conta Google Cloud).
- Google News RSS não tem histórico (só itens recentes): serve para o monitor contínuo, não para
  a retrospectiva.
