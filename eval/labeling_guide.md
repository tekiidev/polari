# Guia de rotulagem

**is_political_violence = true** somente se o texto trata de violência/ameaça/intimidação com
motivação política ou eleitoral claramente indicada no próprio texto.

- Ironia, hipérbole e metáfora ("vou matar esse adversário no debate") → `false`, natureza
  `opiniao_ou_ironia`.
- Notícia compartilhada sobre um fato → `true`, natureza `noticia_compartilhada`.
- "Disseram que fulano foi espancado" sem fonte → `true`, natureza `boato_nao_verificado`.
- Quem relata ter vivido o fato → `relato_primeira_mao`.
- Incentivo a violência futura → `incitacao`.
- Na dúvida entre dois valores, use `indeterminado` e confiança baixa.
- Cidade/UF só se citadas explicitamente. Não deduza pelo contexto.
