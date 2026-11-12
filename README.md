# Polari

**Monitor de discurso sobre violência política no Brasil.** Pipeline de IA (coleta → classificação
por LLM → geocodificação → agregação) e, como destino, um mapa interativo de consulta pública:
globo 3D que gira para mostrar a repercussão por país e aproxima no Brasil até cada estado.

Contexto: eleições de 2026 (1º turno em 04/10, 2º turno em 25/10, Lula x Flávio Bolsonaro).

## Por que existe

No Brasil, violência política é medida por **ocorrência registrada** — e isso tem dois furos.
Ocorrência depende de denúncia, e quem é ameaçado numa cidade pequena muitas vezes não denuncia. E
o dado consolidado chega meses depois, quando a eleição já passou.

Falta a outra metade: **o quanto se fala** de violência política, onde e quando. Isso aparece em
tempo quase real nas redes e não é medido de forma sistemática em português. Um jornalista que
queira saber se o discurso sobre violência eleitoral cresceu em Pernambuco entre os dois turnos
não tem hoje onde olhar.

O Polari mede isso, e é explícito sobre o que **não** mede.

> **O que o Polari mede:** onde e quando se *fala* de violência política, não onde ela *ocorreu*.
> Cada item é rotulado por natureza do relato (primeira mão, notícia compartilhada, opinião/ironia,
> boato). O nome faz referência à polaridade política, mas o projeto **não afirma** que a
> polarização causa a violência: ele observa o discurso e expõe seus limites.
> Veja [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Estado (12/11/2026)

| etapa | estado |
|---|---|
| Coleta do Bluesky | **pronta** — 228.204 posts de 01/06 a 04/11, com backfill e checkpoint |
| Pré-filtro com recall medido | **pronto** — aprova 7,9% dos itens, deixa passar 37% dos positivos ([`docs/prefilter.md`](docs/prefilter.md)) |
| Gabarito humano | **pronto** — 200 itens rotulados à mão, congelados com hash, com uma errata cega registrada |
| Pares espelhados (teste de viés) | **pronto** — 20 pares |
| Classificadores | **prontos** — OpenAI, Gemini, Claude e modelos locais (Ollama), mesma interface |
| Avaliação e escolha do LLM | **pronta** — `gpt-6-luna` escolhido por medição ([`docs/eval-llm.md`](docs/eval-llm.md)) |
| Modelo próprio (BERTimbau) | a fazer |
| Agregação e pipeline diário | a fazer |
| **Mapa interativo** | a fazer — é o destino do projeto, e depende dos agregados reais |

A ordem é imposta pelos dados: o mapa só mostra o que a classificação produzir, e um globo com
dados ilustrativos não é consulta pública.

## O que o projeto resolve de engenharia

- **Classificação com régua auditável.** LLM com saída estruturada por JSON schema, validada com
  Pydantic — inclusive regras de coerência entre campos. Em JSON inválido, uma nova tentativa;
  persistindo, o item é marcado como erro e **nunca** recebe rótulo inventado.
- **Escolha de modelo por medição, não por preferência.** Três candidatos, mesmo gabarito,
  critérios escritos **antes** de rodar ([`docs/decisions/escolha-llm.md`](docs/decisions/escolha-llm.md)).
- **Gabarito congelado com hash** antes da primeira execução, e conjunto de desenvolvimento
  separado do de teste — ajustar o prompt onde se mede o F1 produz número otimista.
- **Viés partidário medido, não suposto.** Pares espelhados: o mesmo texto com os lados políticos
  trocados tem de receber o mesmo rótulo. Modelo que falha nisso não classifica dado público,
  mesmo com o melhor F1. Um mapa colorido por estado é exatamente o que faria uma assimetria
  parecer legítima.
- **Destilação para produção.** O LLM rotula em volume; o BERTimbau aprende e roda todo dia sem
  cota de API. Em produção, o BERT classifica tudo e só a baixa confiança volta ao LLM.
- **Privacidade no desenho.** IDs por HMAC com chave secreta, URI original só criptografado, texto
  bruto fora do repositório público, remoção real testada contra o histórico do Hugging Face, base
  legal da LGPD escrita com as fragilidades declaradas ([`docs/decisions/lgpd.md`](docs/decisions/lgpd.md)).

> **O que o Polari mede:** onde e quando se *fala* de violência política, não onde ela *ocorreu*.
> Cada item é rotulado como relato de primeira mão, notícia compartilhada, opinião/ironia ou boato.
> O nome faz referência à polaridade política, mas o projeto **não afirma** que a polarização
> causa a violência: ele observa o discurso e expõe seus limites. Veja `docs/METHODOLOGY.md`.

## Pergunta e desenho do estudo

**Pergunta:** como o discurso sobre violência política muda antes e depois dos dois turnos,
em comparação com um período sem eleição?

- **Períodos:** linha de base (pré-campanha), campanha do 1º turno (16/08–04/10), entre os
  turnos (05–25/10) e pós-eleição (a partir de 26/10, em aberto).
- **Janelas por evento:** D-14 a D+14 em torno de 04/10 e de 25/10.
- **Medida:** *taxa* (itens de violência política ÷ total de posts sobre o contexto eleitoral no
  mesmo dia), nunca contagem bruta. Dia = dia local (America/Sao_Paulo).
- **Validação externa:** a série é comparada com casos registrados por observatórios (por exemplo,
  Terra de Direitos e Justiça Global).
- **Comportamento das ferramentas no tempo:** modelo e prompt versionados, teste de deriva com o
  gabarito humano e painel de saúde do pipeline.

## Arquitetura

```
 fontes: Bluesky (pronto) | GDELT para repercussão internacional (Fase 2b)
          │  pipeline/ingest — backfill retomável por fatias + coleta incremental
          ▼
   armazenamento do bruto: Parquet por fonte e dia local (fora do git)
          │  IDs por HMAC · URI criptografado · dataset privado no Hugging Face
          ▼
   pré-filtro por regras nomeadas, recall medido  (pipeline/classify/prefilter.py)
          │  aprova ~8%: o que ele barra nunca é classificado, então o recall dele limita tudo
          ▼
   classificação                        ┌─ avaliação (eval/)
     produção: BERTimbau todo dia       │   gabarito humano de 200, congelado com hash
     baixa confiança → LLM              │   F1 com intervalo · pares espelhados · teste de deriva
     (schemas/ + prompts/, com          │   escolha do LLM por critérios escritos antes
      model_id e prompt_version)        └─
          ▼
   resolvedor de UF e cidade (tabela IBGE local → Nominatim só como fallback)
          ▼
   agregação por período e janela (UF × tipo × dia local; mínimo k) → web/public/data/*.json
          ▼
   mapa: globo 3D (MapLibre GL) → países → Brasil por UF em Albers de áreas iguais
          │  + linha do tempo · lista ordenada com n · cards de compartilhar
          ▲
   GitHub Actions (cron diário): roda o pipeline, registra a saúde e faz commit dos agregados
```

**Projeções escolhidas por motivo:** o globo não usa projeção (vista ortográfica da esfera); o
mapa-múndi plano usa Equal Earth; o Brasil por UF usa Albers de áreas iguais, porque em mapa
colorido por valor o olho lê área como quantidade.

## Estrutura do repositório

```
polari/
├── pipeline/
│   ├── ingest/      # fontes + backfill por fatias
│   ├── classify/    # pré-filtro e classificador LLM
│   ├── geocode/     # tabela IBGE e resolvedor de cidade
│   ├── aggregate/   # séries, taxas e JSON para o front
│   ├── study/       # janelas do estudo (períodos e eventos)
│   └── monitor/     # métricas de saúde por execução
├── schemas/         # contrato JSON da classificação
├── prompts/         # prompt versionado do classificador
├── eval/            # gabarito (gold.py), pares espelhados (mirrored.py), métricas
├── tests/           # 123 testes: contrato, backends, gabarito, coleta, privacidade
├── docs/            # arquitetura, metodologia e decisions/ (uma decisão por arquivo)
├── web/             # front-end Next.js + MapLibre GL (globo → UF)
├── data/            # dados locais (raw/ fica fora do git)
└── .github/workflows/daily.yml
```

## Como rodar (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # preencha as chaves
pytest
python -m pipeline.run --dry-run
```

Coleta (precisa de `BLUESKY_*`, `POLARI_SECRET_KEY` e, para sincronizar, `HF_TOKEN` e `HF_RAW_REPO`):

```bash
python -m pipeline.ingest.queries --end 2026-11-04       # volume de cada consulta (1 requisição cada)
python -m pipeline.run --backfill-from 2026-06-01 --backfill-to 2026-11-04   # retomável; --no-sync para não usar o HF
python -m pipeline.remote pull                           # traz o bruto do dataset privado
```

Recall do pré-filtro (rótulos em `eval/labeled_private/`, fora do git; resultado em `docs/prefilter.md`):

```bash
python -m pipeline.classify.recall sample --start 2026-06-01 --end 2026-11-04
python -m pipeline.classify.recall report
```

Gabarito humano e teste de viés (rótulos fora do git; só o hash é versionado):

```bash
python -m eval.gold sample      # sorteia 200 itens, estratificados e cegos
python -m eval.gold label       # rotula no terminal (retomável, salva a cada item)
python -m eval.gold status      # progresso por código e por estrato
python -m eval.gold freeze      # congela e imprime o SHA-256

python -m eval.mirrored candidates   # acha posts espelháveis no corpus
python -m eval.mirrored write        # escreve os pares no terminal
python -m eval.mirrored check        # valida (recusa reescrita e par sem marcador de lado)
```

## Roadmap

- [x] 1. Fundação e viabilidade: contagem de dados por dia nas fontes, armazenamento do bruto fora do Actions, IDs com hash
- [x] **2a. Coleta de dados:** Bluesky com backfill e checkpoint, sincronização com o HF, pré-filtro com recall medido (preliminar)
- [ ] 2b. Notícias (GDELT) e repercussão internacional, depois da Fase 4
- [ ] **3. Classificador e avaliação** (em andamento): gabarito de 200 congelado ✅, pares espelhados ✅, três backends ✅, falta a avaliação e a escolha do LLM
- [ ] 4. Modelo próprio: baseline TF-IDF, fine-tuning do BERTimbau, publicação no Hugging Face
- [ ] 5. Produção: agregação e métricas do estudo, pipeline diário (BERT → LLM)
- [ ] 6. Vitrine: globo interativo (países → Brasil → UF), linha do tempo, cards de compartilhar, deploy, artigo técnico
- [ ] 7. Revisão final

## Números

Medidos. O que ainda não foi medido está marcado como tal, não estimado.

| Métrica | Valor |
|---|---|
| Posts coletados (Bluesky, 01/06–04/11) | 228.204 |
| Aprovados pelo pré-filtro | 18.034 (7,9%) |
| Gabarito humano | 200 itens · 88 positivos no Brasil · 5 difíceis |
| SHA-256 do gabarito | `f1b74e5d…5860` (errata cega de 12/11; original `7423fb24…9f6a`, congelado em 10/11 antes de rodar qualquer modelo) |
| Precisão do pré-filtro no gabarito | 59% (83 positivos em 140 aprovados) |
| Pares espelhados (teste de viés) | 20 pares · 40 textos |
| Recall do pré-filtro (sem viés, 60 itens barrados do gabarito) | 37,0% (21,3% a 48,5%) |
| F1 do classificador escolhido (`gpt-6-luna`, código 1) | 0,638 (IC 95%: 0,537–0,726) · precisão 0,88 · recall 0,50 |
| Diferença para o segundo (`gpt-5.4-mini`) | +0,122 (IC pareado: +0,025 a +0,225) |
| Simetria partidária (pares espelhados divergentes) | 0 de 20 nos três modelos medidos |
| Modelos locais (Qwen3 8B, Gemma 3 12B) | eliminados por tempo: 103 h e 175 h para 25 mil itens (limite 48 h) |
| Testes automatizados | 167 |
| Custo de API da avaliação | US$ 0,64 (≈ 750 classificações) · projeção para 25 mil itens: US$ 18–21 com o `gpt-6-luna`, acima do limite de US$ 10 — redução de custo é a 1ª tarefa da Fase 4 |

## Ética e dados

- O repositório público contém **apenas agregados**. O texto bruto fica em armazenamento privado,
  fora do git (localmente em `data/raw/`, ignorado).
- Itens são identificados por um hash com chave secreta. O link original fica só no armazenamento
  privado, criptografado, para respeitar posts apagados pelos autores.
- Não armazenamos handle nem perfil de autores. Células com menos de 3 itens são ocultadas.
- Não classificamos a orientação política de pessoas (dado sensível, LGPD).
- Respeitamos os termos de cada fonte; não coletamos do X sem a API oficial.
- **Base legal e riscos:** o tratamento se apoia na finalidade de pesquisa (art. 7º, IV e art. 11,
  II, "c"). O raciocínio completo, inclusive as fragilidades — o art. 7º, IV fala em "órgão de
  pesquisa" e este é um projeto individual; a chave do HMAC é ponto único de falha; o bruto não tem
  prazo de retenção definido — está em [`docs/decisions/lgpd.md`](docs/decisions/lgpd.md).
- **Remoção:** quem quiser os próprios posts removidos pode pedir pelo e-mail do perfil, informando
  o handle ou o link. Apagar o post no Bluesky também basta: a varredura periódica (Fase 5) remove
  da cópia privada o que sumiu da origem.
- **Posts nunca aparecem no site**, nem anonimizados — o texto é buscável e levaria ao autor. Ao
  clicar num país ou estado, aparecem notícias públicas com título, veículo, data e link.

## Licença

[AGPL-3.0](LICENSE). Quem distribuir uma versão modificada, ou oferecê-la como serviço online,
precisa publicar o código sob a mesma licença.

Termo adicional (seção 7b da AGPL): versões derivadas e serviços baseados no Polari devem manter a
atribuição "Baseado no Polari, de Felipe Oliveira", com link para este repositório. Veja [NOTICE](NOTICE).

Dados agregados, gráficos, metodologia e textos: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.pt-br).
Podem ser republicados, inclusive em reportagens, desde que citem "Polari, de Felipe Oliveira" com link.

## Como citar

> Oliveira, Felipe. *Polari: monitor do discurso sobre violência política no Brasil*. 2026.
> https://github.com/tekiidev/polari

No GitHub, use o botão "Cite this repository" (gerado a partir do [CITATION.cff](CITATION.cff)).
