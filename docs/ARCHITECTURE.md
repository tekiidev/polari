# Arquitetura

## Fluxo de dados

0. **Backfill** (`pipeline/ingest/backfill.py`): coleta o passado em fatias diárias, com checkpoint.
   Vem primeiro porque as fontes expiram e o estudo precisa do pré-eleição.
1. **Ingest** (`pipeline/ingest/`): cada fonte implementa `Source.fetch(since, until, limit)` e
   devolve `RawItem`. Adicionar o X depois = um novo arquivo, sem mexer no resto.
2. **Pré-filtro** (`pipeline/classify/prefilter.py`): regex barata que descarta o que claramente
   não é sobre violência. Prioriza *recall*; o LLM decide a precisão.
3. **Classificação** (`pipeline/classify/classifier.py`): LLM com saída estruturada. O contrato é
   `schemas/classification.schema.json`, espelhado em `pipeline/models.py`. Cada resultado grava
   `model_id`, `prompt_version` e `classified_at`.
4. **Geocodificação** (`pipeline/geocode/`): `cidade + UF` → tabela IBGE local. Nominatim só como
   fallback, com cache, 1 req/s e User-Agent identificável.
5. **Agregação** (`pipeline/aggregate/build.py`): dia local → período (`pipeline/study/windows.py`),
   taxas com denominador de contexto, JSON estático para o front.
6. **Monitor** (`pipeline/monitor/health.py`): uma linha de métricas por execução em
   `data/processed/runs.jsonl`, resumida em `health.json`.
7. **Front** (`web/`): lê os JSON de `web/public/data/`.

## Contrato de saída (web/public/data/)

- `summary.json`: totais, período coberto, % geolocalizado, data de atualização, versões do modelo e do prompt.
- `municipios.json`: `[{ibge, nome, uf, lat, lon, periodo, total, por_tipo:{...}}]` (somente células com total ≥ k).
- `series.json`: `[{data, periodo, dia_relativo:{primeiro_turno, segundo_turno}, violencia, contexto, taxa, por_tipo:{...}}]`.
- `windows.json`: períodos e eventos usados (espelho de `windows.py`, para o front desenhar os marcadores).
- `health.json`: evolução das métricas de execução e do F1 do teste de deriva.
- `briefing.md`: texto do agente de briefing (gerado só de agregados; todo número citado deve existir nos dados).

## Decisões (e por quê)

- **Janelas como dados:** as datas vivem em `windows.py`; nada de datas espalhadas pelo código.
- **Dia local, não UTC:** evita contar na eleição o que aconteceu na noite anterior.
- **Taxa com denominador:** o volume geral de posts muda; a taxa torna os períodos comparáveis.
- **Versão fixa do classificador por série:** trocar modelo ou prompt exige reclassificar tudo.
- **LLM em vez de BERTimbau:** sem dataset rotulado e com foco em "IA como alavanca"; avaliação
  contra gabarito humano comprova a qualidade.
- **IBGE local em vez de Nominatim:** determinístico, sem limite de taxa, sem política a violar.
- **Agregados no repositório, texto bruto fora:** privacidade e termos das fontes.
- **Sem campo de orientação política da vítima/autor:** dado sensível e inferência frágil.
- **Estático + cron:** zero custo de servidor, deploy simples.
