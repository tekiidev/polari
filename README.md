# Polari

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
pytest                      # contrato, janelas, saúde e utilitários
python -m pipeline.run --dry-run
```

## Roadmap

- [ ] **D0 Viabilidade e backfill (urgente):** contar itens por dia desde 16/08 e coletar o pré-eleição antes que as fontes expirem
- [ ] D1 Repositório, tabela IBGE, coletor Bluesky/RSS (incremental)
- [ ] D2 Prompt + classificador + 200 itens rotulados à mão + teste de deriva (`eval/`)
- [ ] D3 Resolvedor de cidade + agregação por período e taxas
- [ ] D4 Mapa Leaflet (bolhas, filtros) + linha do tempo com marcadores de 04/10 e 25/10 + seletor de janela
- [ ] D5 Agente de briefing + PDF + automação diária + painel de saúde
- [ ] D6 Deploy, README final, GIF/vídeo de 2 min
- [ ] D7 Página de metodologia, limitações e validação externa

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

- O repositório público contém **apenas agregados** e IDs; o texto bruto fica em `data/raw/` (ignorado pelo git).
- Não armazenamos handle nem perfil de autores. Células com menos de 3 itens são ocultadas.
- Não classificamos a orientação política de pessoas (dado sensível, LGPD).
- Respeitamos os termos de cada fonte; não coletamos do X sem a API oficial.

## Licença

A definir (sugestão: MIT para o código).
