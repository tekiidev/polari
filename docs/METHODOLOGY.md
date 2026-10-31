# Metodologia e limitações

## O que o Polari mede
Volume de **menções** a violência política em fontes abertas, por município citado e por dia.
Não é contagem de ocorrências: um mesmo fato pode gerar muitas menções.

## Pergunta
Como o discurso sobre violência política muda antes e depois dos dois turnos de 2026
(04/10 e 25/10), em comparação com um período sem eleição?

## Períodos e janelas
Definidos em `pipeline/study/windows.py` (única fonte das datas).

| Período | Intervalo | Observação |
|---|---|---|
| baseline | a definir (padrão: 01/06 a 15/08) | **Decisão do autor:** justificar. Convenções partidárias podem elevar o discurso. |
| campanha_1t | 16/08 a 04/10 | Inclui o dia do 1º turno. |
| entre_turnos | 05/10 a 25/10 | Inclui o dia do 2º turno. |
| pos_eleicao | a partir de 26/10 | Em aberto: a coleta continua. |

- **Janelas por evento:** D-14 a D+14 em torno de cada turno (D0 = dia da votação).
- **Fuso:** todo agrupamento por dia usa America/Sao_Paulo, nunca UTC.

## Medida
- **Taxa, não contagem.** `taxa(dia) = itens de violência política ÷ itens do contexto eleitoral`,
  com o denominador vindo de uma consulta neutra (termos eleitorais, sem termos de violência).
  Isso controla o aumento geral de posts em dias de votação.
- **Unidade de análise:** o incidente deduplicado, não a menção.
- **Confiança mínima:** só entram itens com `confidence` acima de um limiar documentado.

## Comparações
- **Antes × depois** de cada turno, com a diferença das taxas e um intervalo de incerteza
  (por exemplo, bootstrap por dia). Sem conclusões causais.
- **Picos:** detectar dias anômalos com método robusto (mediana móvel e MAD) e conferir contra
  eventos conhecidos. Em série diária curta, métodos simples são mais transparentes que modelos pesados.
- **Mapa por período:** onde o discurso se concentrava em cada janela.

## Taxonomia
Alinhada às categorias de observatórios brasileiros (ameaça, ofensa, agressão física, atentado,
homicídio, violência de gênero). Confira o livro de códigos do OVPE/UNIRIO e ajuste.

## Natureza do relato
`relato_primeira_mao`, `relato_terceiros`, `noticia_compartilhada`, `opiniao_ou_ironia`,
`boato_nao_verificado`, `incitacao`, `indeterminado`. Boato não é descartado: é rotulado.

## Comportamento das ferramentas no tempo
- **Versões fixas:** cada classificação grava `model_id`, `prompt_version` e `classified_at`.
- **Sem misturar versões:** ao trocar modelo ou prompt, reclassifica-se tudo antes de comparar períodos.
- **Teste de deriva (canário):** o gabarito de 200 itens roda periodicamente e o F1 é acompanhado
  (`eval/`). Queda sinaliza mudança no classificador, não no mundo.
- **Saúde do pipeline:** por execução, itens coletados, % no pré-filtro, % classificado,
  % geolocalizado, erros e uso da cota do LLM (`pipeline/monitor/health.py`).

## Validação
- 200+ itens rotulados à mão (`eval/`), com guia de rotulagem.
- Métricas: precisão, recall e F1 por campo, e concordância entre dois rotuladores.
- **Validação externa:** comparar a série com casos registrados por observatórios. Exemplo: o
  levantamento de Terra de Direitos e Justiça Global contou 134 casos de 16/08 a 04/10/2026
  (121 no mesmo recorte de 2022). Curvas que andam juntas dão credibilidade; curvas que divergem
  são um achado a explicar, não a esconder.

## Ameaças à validade
- **Cobertura da fonte:** Bluesky, Telegram e notícias têm públicos distintos e não representam a população.
- **Tamanho de amostra por janela** pode ser pequeno; mostrar sempre o `n`.
- **Fatores de confusão:** ciclos de notícia, eventos pontuais, mudanças na base de usuários da plataforma.
- **Backfill incompleto:** se uma fonte não alcança o pré-eleição, a comparação perde força; declarar isso.
- **Correlação não é causa.**

## Limitações (publicar na página de metodologia)
- Só uma fração dos itens cita cidade; o % geolocalizado vai para o `summary.json`.
- Ironia e hipérbole geram ruído; por isso a validação humana.
- Deduplicação por incidente é aproximada.
