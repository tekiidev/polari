# Polari

> **Status:** em construção. Coleta do Bluesky pronta (228 mil posts de 01/06 a 04/11/2026, só no
> armazenamento privado); classificador, modelo próprio e site ainda não.

**Monitor de discurso sobre violência política no Brasil**, com pipeline automatizado
(coleta → classificação com LLM → geocodificação → agregação) e mapa interativo.

Contexto: eleições de 2026 (1º turno em 04/10, 2º turno em 25/10, Lula x Flávio Bolsonaro).

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
 fontes (Bluesky | RSS/GDELT | Telegram*)        * futuro; X = conector opcional
          │  pipeline/ingest  (backfill do passado + coleta incremental)
          ▼
   pré-filtro por palavras-chave  (pipeline/classify/prefilter.py)
          ▼
   classificador LLM → JSON validado (schemas/ + prompts/), com model_id e prompt_version
          ▼
   resolvedor de cidade (tabela IBGE local → Nominatim só como fallback)
          ▼
   agregação por período/janela (município × tipo × dia local; mínimo k=3) → web/public/data/*.json
          ▼
   Next.js + Leaflet (mapa, linha do tempo com marcadores, comparação de janelas) → Vercel
          ▲
   GitHub Actions (cron diário) roda o pipeline, registra a saúde da execução e faz commit dos agregados
```

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
├── eval/            # gabarito humano, métricas e teste de deriva
├── tests/           # contrato, janelas, saúde e utilitários
├── docs/            # ARCHITECTURE.md e METHODOLOGY.md
├── web/             # front-end Next.js + Leaflet
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

## Roadmap

- [x] 1. Fundação e viabilidade: contagem de dados por dia nas fontes, armazenamento do bruto fora do Actions, IDs com hash
- [x] **2a. Coleta de dados:** Bluesky com backfill e checkpoint, sincronização com o HF, pré-filtro com recall medido (preliminar)
- [ ] 2b. Notícias (GDELT) e repercussão internacional, depois da Fase 4
- [ ] 3. Classificador e avaliação: classificador LLM, gabarito humano de 200 itens, escolha do LLM por medição
- [ ] 4. Modelo próprio: baseline TF-IDF, fine-tuning do BERTimbau, publicação no Hugging Face
- [ ] 5. Produção: agregação e métricas do estudo, pipeline diário (BERT → LLM)
- [ ] 6. Vitrine: site com linha do tempo e mapa por UF, deploy, artigo técnico
- [ ] 7. Revisão final

## Métricas de impacto (preencher com números reais)

| Métrica | Valor |
|---|---|
| Tempo para rotular 200 itens à mão | _ min |
| Tempo do pipeline para os mesmos 200 itens | _ min |
| F1 do LLM vs. gabarito humano | _ |
| F1 no teste de deriva (última execução) | _ |
| % de itens geolocalizados | _ |
| Itens por janela (antes/depois de cada turno) | _ |
| Custo total | R$ 0 |
| Dias de construção | _ |

## Ética e dados

- O repositório público contém **apenas agregados**. O texto bruto fica em armazenamento privado,
  fora do git (localmente em `data/raw/`, ignorado).
- Itens são identificados por um hash com chave secreta. O link original fica só no armazenamento
  privado, criptografado, para respeitar posts apagados pelos autores.
- Não armazenamos handle nem perfil de autores. Células com menos de 3 itens são ocultadas.
- Não classificamos a orientação política de pessoas (dado sensível, LGPD).
- Respeitamos os termos de cada fonte; não coletamos do X sem a API oficial.

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
