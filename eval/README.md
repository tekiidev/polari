# Avaliação (gabarito humano e teste de deriva)

## Gabarito
1. Separe ~200 itens variados (inclua ironia, notícias compartilhadas e itens sem relação),
   distribuídos entre os períodos do estudo (baseline, campanha, entre turnos, pós-eleição).
2. Rotule à mão seguindo `labeling_guide.md` e salve em `eval/labeled_private/gold.jsonl`
   (pasta ignorada pelo git, pois contém texto bruto). Cronometre o tempo total.
3. Rode o classificador nos mesmos itens e compare campo a campo:
   precisão, recall e F1 de `is_political_violence`; acurácia de `violence_type` e `report_nature`.
4. Se possível, peça a uma segunda pessoa para rotular 50 itens e calcule a concordância (kappa).
5. Publique só as métricas e a matriz de confusão, nunca o texto.

## Teste de deriva (canário)
- Reexecute o classificador no mesmo gabarito de tempos em tempos (por exemplo, semanalmente) e
  registre o F1 junto de `model_id` e `prompt_version`.
- Queda de F1 sem mudança de versão = o serviço do modelo mudou. Pare, investigue e só compare
  períodos depois de reclassificar tudo com a mesma versão.
- O resultado alimenta `health.json` e o painel de saúde do front.
