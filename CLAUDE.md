# Polari

## Objetivo
Monitor de discurso sobre violência política no Brasil, com pipeline de IA (coleta → classificação → geocodificação → agregação) e site público.
Duas finalidades: portfólio técnico de engenharia de IA/ML (LLMs, modelo treinado, avaliação, produção) e consulta pública.

O Polari mede onde e quando se **fala** de violência política, não onde ela **ocorreu**.

## Decisões tomadas (com justificativa)
- **Retrospectiva das eleições de 2026 primeiro, monitor contínuo depois.** A eleição terminou em 25/10/2026; o pipeline diário só vale depois que a retrospectiva funcionar. Muda se a Fase 1 mostrar que as fontes não alcançam o pré-eleição: aí o escopo vira "pós-eleição em diante".
- **LLM escolhido por medição, não por preferência.** O Gemini entrou só por ter plano gratuito. A Fase 3 compara 3 opções (Gemini Flash, modelo aberto local, um pago barato) no mesmo gabarito, por F1, privacidade, custo, latência, JSON inválido e versão fixável. Critérios definidos antes de rodar; o Gemini pode perder.
- **Modelo próprio (BERTimbau) ao lado do LLM.** O LLM ajuda a rotular; o modelo treinado roda todo dia sem cota de API. Em produção, o BERT classifica tudo e só os casos de baixa confiança vão ao LLM. Muda se o BERT ficar muito abaixo do LLM no gabarito.
- **Gabarito humano de 200 itens é a régua de tudo.** Inclui itens barrados pelo pré-filtro, para medir o recall dele. Nunca ajustar o gabarito para melhorar um resultado.
- **Texto bruto fora do repositório e fora do GitHub Actions.** O runner é efêmero; sem guardar o bruto, não há reclassificação nem estado incremental. O repositório público contém só agregados.
- **IDs com hash.** O URI do Bluesky contém o DID do autor; nunca guardar DID, handle ou perfil.
- **Agregação por UF antes de município.** Contagem por município reflete população e imprensa, e poucos textos citam cidade. Mostrar sempre taxa **e** volume, o `n` de cada janela, e boatos fora da visão padrão. O mínimo k vale também para cada tipo, não só para o total.
- **Dia local (America/Sao_Paulo), versões fixas de modelo e prompt, tabela IBGE local.** Já implementados ou previstos em `pipeline/study/windows.py`, `pipeline/models.py` e `pipeline/geocode/`.
- **Licença AGPL-3.0.** Copyleft: qualquer um pode usar e modificar, mas quem distribuir ou oferecer como serviço online compartilha o código sob a mesma licença.
- **Sem orientação política de pessoas.** Dado sensível (LGPD) e inferência frágil.

## Problemas conhecidos (corrigir nas fases indicadas)
- Pré-filtro perde casos centrais ("Vereadora foi morta a tiros", "Prefeito é baleado") e aceita falsos positivos por falta de fronteira de palavra (`tiro` em "retirou", `soco` em "socorro"). Fase 2.
- `Classification` aceita `is_political_violence = false` com `violence_type` diferente de `nenhum`. Fase 3.
- Exemplo do prompt trata cabo eleitoral como `agente_publico`; o prompt não lista os valores de `violence_type`. Fase 3.
- Metodologia contradiz a si mesma: mede menções, mas define "incidente deduplicado" como unidade. O "período sem eleição" é pré-campanha de ano eleitoral. As janelas D±14 dos dois turnos se sobrepõem de 11 a 18/10. Fase 5.
- `build.py` cita `timeline.json`, o `ARCHITECTURE.md` cita `series.json`. Fase 5.
- `requirements.txt` sem versões fixadas; docstrings em tom de tutorial ("você precisa implementar"). Fase 6.

## Estado atual
- Fase concluída: nenhuma (estrutura inicial, 20 testes passando, pipeline com `NotImplementedError`).
- Próxima fase: 1 — Fundação e viabilidade.
- Pendências de organização: confirmar `LICENSE` AGPL-3.0, aviso "em construção" no README (que ainda diz "Licença: a definir") e workflow `daily-pipeline` desativado.

## Fases
Uma fase por conversa. Se a conversa ficar longa, atualize "Estado atual" e continue numa nova com o mesmo título + "parte 2".

1. **Fundação e viabilidade:** organização do repositório, contagem de dados por dia nas fontes, armazenamento do bruto fora do Actions, IDs com hash.
2. **Coleta de dados:** coletor de notícias com backfill e checkpoint, coletor do Bluesky, pré-filtro com recall medido.
3. **Classificador e avaliação:** classificador LLM com validação, gabarito humano de 200 itens, avaliação e escolha do LLM.
4. **Modelo próprio:** rotulagem em volume, baseline TF-IDF, fine-tuning do BERTimbau, comparação final, publicação no Hugging Face.
5. **Produção:** agregação e métricas do estudo, pipeline diário com roteamento BERT → LLM, cron religado.
6. **Vitrine:** site com linha do tempo e mapa por UF, deploy, README com resultados, artigo técnico.
7. **Revisão final:** revisão crítica como avaliador técnico e simulação de entrevista.

As fases 1 e 3 decidem o rumo: termine cada uma antes da seguinte. Se faltar tempo, corte primeiro o site e o deploy; gabarito, avaliação e Hugging Face não saem.

## Regras de trabalho
- Responda em português do Brasil.
- Uma fase por conversa; não avance para outra sem eu pedir.
- Antes de codar, explique o plano em poucas linhas e espere meu ok.
- Toda escolha técnica precisa de justificativa e, se possível, de medição.
- Seja crítico: aponte erros e riscos, mesmo nas minhas ideias.
- Não faça commit nem push sem eu pedir.
- Repositório público: nada de segredos, texto bruto de posts ou dados pessoais no git.
- Ao terminar uma fase: resuma o que mudou, rode os testes (`pytest`) e atualize "Estado atual" e "Problemas conhecidos".
