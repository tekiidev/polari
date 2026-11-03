# Polari

## Objetivo
Monitor de discurso sobre violência política no Brasil, com pipeline de IA (coleta → classificação → geocodificação → agregação) e site público.
Duas finalidades: portfólio técnico de engenharia de IA/ML (LLMs, modelo treinado, avaliação, produção) e consulta pública.

O Polari mede onde e quando se **fala** de violência política, não onde ela **ocorreu**.

## Decisões tomadas (com justificativa)
- **Retrospectiva das eleições de 2026 primeiro, monitor contínuo depois.** A eleição terminou em 25/10/2026; o pipeline diário só vale depois que a retrospectiva funcionar. Muda se a Etapa 01 mostrar que as fontes não alcançam o pré-eleição: aí o escopo vira "pós-eleição em diante".
- **LLM escolhido por medição, não por preferência.** O Gemini entrou só por ter plano gratuito. A Etapa 08 compara 3 opções (Gemini Flash, modelo aberto local, um pago barato) no mesmo gabarito, por F1, privacidade, custo, latência, JSON inválido e versão fixável. Critérios definidos antes de rodar; o Gemini pode perder.
- **Modelo próprio (BERTimbau) ao lado do LLM.** O LLM ajuda a rotular; o modelo treinado roda todo dia sem cota de API. Em produção, o BERT classifica tudo e só os casos de baixa confiança vão ao LLM. Muda se o BERT ficar muito abaixo do LLM no gabarito.
- **Gabarito humano de 200 itens é a régua de tudo.** Inclui itens barrados pelo pré-filtro, para medir o recall dele. Nunca ajustar o gabarito para melhorar um resultado.
- **Texto bruto fora do repositório e fora do GitHub Actions.** O runner é efêmero; sem guardar o bruto, não há reclassificação nem estado incremental. O repositório público contém só agregados.
- **IDs com hash.** O URI do Bluesky contém o DID do autor; nunca guardar DID, handle ou perfil.
- **Agregação por UF antes de município.** Contagem por município reflete população e imprensa, e poucos textos citam cidade. Mostrar sempre taxa **e** volume, o `n` de cada janela, e boatos fora da visão padrão. O mínimo k vale também para cada tipo, não só para o total.
- **Dia local (America/Sao_Paulo), versões fixas de modelo e prompt, tabela IBGE local.** Já implementados ou previstos em `pipeline/study/windows.py`, `pipeline/models.py` e `pipeline/geocode/`.
- **Licença AGPL-3.0.** Copyleft: qualquer um pode usar e modificar, mas quem distribuir ou oferecer como serviço online compartilha o código sob a mesma licença.
- **Sem orientação política de pessoas.** Dado sensível (LGPD) e inferência frágil.

## Problemas conhecidos (corrigir nas etapas indicadas)
- Pré-filtro perde casos centrais ("Vereadora foi morta a tiros", "Prefeito é baleado") e aceita falsos positivos por falta de fronteira de palavra (`tiro` em "retirou", `soco` em "socorro"). Etapa 05.
- `Classification` aceita `is_political_violence = false` com `violence_type` diferente de `nenhum`. Etapa 06.
- Exemplo do prompt trata cabo eleitoral como `agente_publico`; o prompt não lista os valores de `violence_type`. Etapa 06.
- Metodologia contradiz a si mesma: mede menções, mas define "incidente deduplicado" como unidade. O "período sem eleição" é pré-campanha de ano eleitoral. As janelas D±14 dos dois turnos se sobrepõem de 11 a 18/10. Etapa 14.
- `build.py` cita `timeline.json`, o `ARCHITECTURE.md` cita `series.json`. Etapa 14.
- `requirements.txt` sem versões fixadas; docstrings em tom de tutorial ("você precisa implementar"). Etapa 18.

## Estado atual
- Etapa concluída: nenhuma (estrutura inicial, 20 testes passando, pipeline com `NotImplementedError`).
- Etapa em andamento: 00 — Contexto e organização.
- Pendências da Etapa 00: confirmar `LICENSE` AGPL-3.0, aviso "em construção" no README (que ainda diz "Licença: a definir") e workflow `daily-pipeline` desativado.
- Próxima etapa: 01 — Viabilidade das fontes.

## Etapas
00 Contexto e organização · 01 Viabilidade das fontes · 02 Armazenamento e privacidade · 03 Coletor de notícias e backfill · 04 Coletor do Bluesky · 05 Pré-filtro com recall medido · 06 Classificador LLM · 07 Gabarito humano · 08 Avaliação e escolha do LLM · 09 Rotulagem em volume · 10 Baseline clássico · 11 Fine-tuning do BERTimbau · 12 Análise de erros e comparação final · 13 Publicação no Hugging Face · 14 Agregação e métricas do estudo · 15 Pipeline diário em produção · 16 Site · 17 Deploy · 18 README e limpeza · 19 Artigo técnico · 20 Revisão crítica e entrevista.

As etapas 01, 08 e 12 decidem o rumo: termine cada uma antes da seguinte. Se faltar tempo, corte primeiro 16 e 17; gabarito, avaliação e Hugging Face não saem.

## Regras de trabalho
- Responda em português do Brasil.
- Uma etapa por conversa; não avance para outra sem eu pedir.
- Antes de codar, explique o plano em poucas linhas e espere meu ok.
- Toda escolha técnica precisa de justificativa e, se possível, de medição.
- Seja crítico: aponte erros e riscos, mesmo nas minhas ideias.
- Não faça commit nem push sem eu pedir.
- Repositório público: nada de segredos, texto bruto de posts ou dados pessoais no git.
- Ao terminar uma etapa: resuma o que mudou, rode os testes (`pytest`) e atualize "Estado atual" e "Problemas conhecidos".
