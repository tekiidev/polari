# Polari

## Objetivo
Monitor de discurso sobre violência política no Brasil, com pipeline de IA (coleta → classificação → geocodificação → agregação) e site público.
Duas finalidades: portfólio técnico de engenharia de IA/ML (LLMs, modelo treinado, avaliação, produção) e consulta pública.

O Polari mede onde e quando se **fala** de violência política, não onde ela **ocorreu**.

## Decisões tomadas (com justificativa)
- **Retrospectiva das eleições de 2026 primeiro, monitor contínuo depois.** A eleição terminou em 25/10/2026; o pipeline diário só vale depois que a retrospectiva funcionar. Muda se a Fase 1 mostrar que as fontes não alcançam o pré-eleição: aí o escopo vira "pós-eleição em diante". **Confirmada na Fase 1:** o Bluesky cobre de 01/06 em diante sem perda (`docs/feasibility.md`).
- **LLM escolhido por medição, não por preferência.** O Gemini entrou só por ter plano gratuito. A Fase 3 compara 3 opções (Gemini Flash, modelo aberto local, um pago barato) no mesmo gabarito, por F1, privacidade, custo, latência, JSON inválido e versão fixável. Critérios definidos antes de rodar; o Gemini pode perder.
- **Modelo próprio (BERTimbau) ao lado do LLM.** O LLM ajuda a rotular; o modelo treinado roda todo dia sem cota de API. Em produção, o BERT classifica tudo e só os casos de baixa confiança vão ao LLM. Muda se o BERT ficar muito abaixo do LLM no gabarito.
- **Gabarito humano de 200 itens é a régua de tudo.** Inclui itens barrados pelo pré-filtro, para medir o recall dele. Nunca ajustar o gabarito para melhorar um resultado.
- **Texto bruto fora do repositório e fora do GitHub Actions.** O runner é efêmero; sem guardar o bruto, não há reclassificação nem estado incremental. O repositório público contém só agregados.
- **IDs com hash.** O URI do Bluesky contém o DID do autor. O ID de cada item é um HMAC com chave secreta (`POLARI_SECRET_KEY`, `pipeline/privacy.py`). O URI original só existe criptografado, no armazenamento privado do bruto, para respeitar posts apagados; nunca vai para o git, logs ou agregados. Nunca guardar handle ou perfil.
- **Bruto em Parquet por fonte e dia local** (`pipeline/storage.py`): sincronização incremental e remoção de posts apagados reescrevendo um arquivo pequeno. Remoto: dataset privado `tekiidev/polari-raw` no Hugging Face (token fine-grained só nesse repositório), com squash do histórico após remoções; B2 como alternativa (`docs/decisions/armazenamento-bruto.md`).
- **Agregação por UF antes de município.** Contagem por município reflete população e imprensa, e poucos textos citam cidade. Mostrar sempre taxa **e** volume, o `n` de cada janela, e boatos fora da visão padrão. O mínimo k vale também para cada tipo, não só para o total.
- **Dia local (America/Sao_Paulo), versões fixas de modelo e prompt, tabela IBGE local.** Já implementados ou previstos em `pipeline/study/windows.py`, `pipeline/models.py` e `pipeline/geocode/`.
- **Licença AGPL-3.0.** Copyleft: qualquer um pode usar e modificar, mas quem distribuir ou oferecer como serviço online compartilha o código sob a mesma licença.
- **Sem orientação política de pessoas.** Dado sensível (LGPD) e inferência frágil. Termos de espectro ("petista", "bolsonarista") só servem para achar posts; nenhum campo registra o lado de alguém.
- **Escopo do que conta (Fase 2, `eval/labeling_guide.md`):** violência concreta + contexto político no próprio texto. Inclui repressão policial a ato político, casos isolados com motivação política, lideranças sociais (quando o texto cita a atuação), suspeita e boato, incitação indireta com alvo identificável, impedir alguém de votar por coação e **interferência estrangeira na política brasileira** (decisão do autor em 07/11, contra a recomendação: mistura um fenômeno sem violência física na série; vale para qualquer país e lado). Não entram: metáfora, ataque à democracia sem violência, crítica à mídia, desumanização sozinha, operação policial comum. Vínculo eleitoral não é exigido: a relação com a eleição se mede comparando períodos.
- **Códigos de rótulo:** `1` Brasil, `2` outro país (mesma régua), `3` violência verbal (xingamento a quem tem papel político ou por posição política explícita no texto), `0` não é. A série padrão usa só `1`; ofensa verbal e casos de fora são camadas separadas, para não dominar a série.
- **Coleta do Bluesky por 4 famílias de consulta** (`pipeline/ingest/queries.py`): contexto (denominador, fatia diária) e cargo/evento/espectro + violência (fatia semanal). A consulta é um filtro: o recall que importa é consulta + pré-filtro. A busca não faz stemming (feminino e masculino listados à parte) e o `hitsTotal` trava em 10.000.
- **Remoção no HF = squash + apagar LFS órfãos** (`pipeline/remote.py`). Só o squash não basta: medido em 05/11, o arquivo removido continuava baixável pelo SHA antigo. `push` nunca espelha apagando o que falta no remoto.
- **O site é um globo 3D interativo, não um mapa plano.** Girar o globo mostra a repercussão por continente e país; clicar no Brasil aproxima até os estados (UF), com as estatísticas de cada um. Projeções: o globo 3D não usa projeção (vista ortográfica da esfera); o mapa-múndi plano (celular e alternativa) usa **Equal Earth**; o Brasil por UF usa **Albers de áreas iguais**, porque em mapa colorido por valor o olho lê área como quantidade. Implementação candidata: MapLibre GL (globo → plano ao aproximar) com Natural Earth (países) e malha do IBGE (UF). O globo navega e impressiona; a comparação fica numa lista ordenada com n e numa tabela ao lado. Arcos só com significado (país → Brasil, espessura = nº de matérias). Versão plana no celular, navegação por teclado e "reduzir movimento".
- **Repercussão internacional ("dump global") via GDELT:** cobertura e tom da imprensa estrangeira sobre a eleição brasileira, por país e dia, em D±14 de cada turno, com foco na violência política. Mede **cobertura e tom da imprensa**, não a opinião das pessoas de cada país; o nome na tela é "Repercussão internacional". O tom do GDELT é por dicionário e rudimentar: serve para comparar antes/depois, não como veredito. Países com poucas matérias ficam como "dados insuficientes" (cobertura do GDELT é desigual entre regiões).
- **Notícias públicas aparecem, posts não.** Ao clicar num país ou UF: título, veículo, data e link (sem copiar o texto da matéria). Posts nunca, nem anonimizados, porque o texto pode ser buscado e leva ao autor. Seleção por critério objetivo (assuntos publicados por mais veículos diferentes), mostrando países e veículos de origem, para o Polari não virar curadoria editorial.
- **Identidade visual:** tema escuro com neon contido, Orbitron em várias espessuras (títulos, números grandes, rótulos, menu) e Space Grotesk como auxiliar (texto corrido, filtros, eixos, legendas); acabamento de macOS numa página rolável: barra de menu de vidro no topo (com busca ⌘K/Ctrl+K estilo Spotlight; ⌘+Espaço é reservado pelo sistema), seções como janelas translúcidas com semáforo, papel de parede escuro com brilho azul, dock flutuante embaixo com aumento no hover (desktop) e barra de abas no celular; acento azul elétrico #4F82FF (o lavanda #7373FF foi rejeitado por parecer roxo), escala de dados azul de um matiz (#1C3FA8 → #C8DAFF) validada no modo escuro, logo do usuário (`polari-logo`). Arquivo: https://www.figma.com/design/tmufTFDCxxcN2wHgzw2j9z/polari. Nunca gráfico com dois eixos; sem cores partidárias nem da bandeira.
- **Compartilhar (estilo Spotify Wrapped):** card por estado, país ou período, em 1080×1920 (Stories) e 1200×630 (prévia de link). Site não posta direto no Instagram: no celular, Web Share API com arquivo (folha nativa → Instagram Stories/Feed, WhatsApp etc.); no desktop, baixar imagem + copiar link. Links de intenção para X, Threads, Bluesky e WhatsApp, com Open Graph por página. Cards gerados no servidor (candidato: `@vercel/og`) a partir de modelos do Figma. **Regras do card:** sempre "mede o discurso, não a ocorrência", n, período, fonte e link da metodologia; taxa e volume juntos; título neutro; nada de ranking "mais violento"; sem card para dados insuficientes ou ilustrativos. Motivo: o tema é sensível e um card fora de contexto vira peça partidária.
- **Divulgação, em ordem de impacto:** README com GIF do globo + post técnico no LinkedIn (peso para o iFood); artigo técnico e modelo no Hugging Face; comunidade de jornalismo de dados (Escola de Dados, Coda.Br, Abraji) e observatórios; post no Bluesky; cards de compartilhar. Gancho: "retrospectiva das eleições 2026" enquanto o tema está recente.

## Problemas conhecidos (corrigir nas fases indicadas)
- `Classification` aceita `is_political_violence = false` com `violence_type` diferente de `nenhum`. Fase 3.
- Exemplo do prompt trata cabo eleitoral como `agente_publico`; o prompt não lista os valores de `violence_type`. Fase 3.
- Metodologia contradiz a si mesma: mede menções, mas define "incidente deduplicado" como unidade. O "período sem eleição" é pré-campanha de ano eleitoral. As janelas D±14 dos dois turnos se sobrepõem de 11 a 18/10. Fase 5.
- `build.py` cita `timeline.json`, o `ARCHITECTURE.md` cita `series.json`. Fase 5.
- `requirements.txt` sem versões fixadas; docstrings em tom de tutorial ("você precisa implementar"). Fase 6.
- Volume do Bluesky: ~10–40 itens candidatos por dia no país inteiro, antes da classificação. Um recorte UF × tipo × dia com k=3 fica quase vazio; o viável é uma série nacional semanal, com UF só no total de cada período. Fase 5.
- A taxa depende do denominador: "eleição" cresce 10× do baseline ao pós-eleição e a violência cresce 3,4×, então a taxa cai enquanto o volume sobe. Definir e justificar o denominador. Fase 5.
- Notícias não medidas: a DOC API do GDELT bloqueia este IP (429). Os arquivos brutos seguem disponíveis, então não há risco de perda. Medir por outra rede ou pelo BigQuery. Fase 2b (depois da Fase 4), junto da repercussão internacional e do cruzamento com casos noticiados para medir o recall das consultas.
- Recall do pré-filtro só preliminar (`docs/prefilter.md`): 23% na 1ª medição; 62% (18–100%) após a correção, medido na mesma amostra (otimista). Medir sem viés com os itens barrados do gabarito; triagem por LLM de 2–3 mil itens do contexto barrado (216 mil itens, 50 rótulos). Um rótulo (`aeef71ef…`, plataforma) diverge do guia: revisar. Fase 3.
- Schema sem `perpetrator_type` (apoiador / agente do Estado / indeterminado, sem lado), `vinculo_eleitoral` e país; `TargetType` sem "manifestante"; interferência estrangeira sem `violence_type` próprio. Fase 3.
- Gabarito precisa de pares espelhados (mesmo texto, lados trocados) para testar viés do LLM e de kappa com segunda pessoa, sobretudo em incitação indireta. Fase 3.
- Pré-filtro não normaliza grafias que driblam moderação ("facist4", "m0rte"); família espectro com precisão baixa (4/15), candidata a poda se a cota apertar. Fase 3.
- Detecção periódica de posts apagados no Bluesky (o mecanismo de remoção existe; falta checar quais sumiram). Fase 5.
- Crédito embutido no que se compartilha: cards e site com "Polari" + link; campos `fonte` e `licenca` (CC BY 4.0) nos JSON públicos. Fases 5 e 6.
- `web/README.md` descreve Leaflet e mapa por município; reescrever com o stack decidido (MapLibre, globo, UF). README geral: diagrama de arquitetura com "Leaflet" e "município × tipo × dia". Fase 6.
- Estatísticas do painel ao clicar ainda não levantadas. Proposta a validar com os dados: **país** (nº de matérias e n de veículos, tom médio com intervalo, variação D-14 × D+14 em cada turno, principais temas, notícias mais cobertas); **UF** (volume e taxa por período com n, tipos de violência, natureza do relato e alvos com mínimo k, comparação com a média nacional, notícias que citam a UF). Fase 5.
- Telas no Figma (dados ilustrativos): fundamentos, componentes, Tela 1 (linha do tempo, desktop, visual macOS + estado com busca ⌘K), Tela 2 (globo com repercussão internacional, zoom e dica por país) e Tela 2b (Brasil por UF em Albers, painel do estado com estatísticas e notícias). Globo e mapa gerados de dados reais (Natural Earth 110m, malha do IBGE) com d3-geo. Faltam mobile, comparação, metodologia, como funciona e estados de carregando/vazio/erro. Fase 6.

## Estado atual
- Fase concluída: 2a — Coleta de dados (07/11/2026), na branch `fase-2-coleta`. 77 testes passando.
  - Bluesky: 228.204 posts únicos de 01/06 a 04/11 (77 MB), no `tekiidev/polari-raw` e em `data/raw/`; 99% do `hitsTotal` estimado na Fase 1. Retomar a coleta: `python -m pipeline.run --backfill-from … --backfill-to …` (checkpoint pula fatias feitas).
  - Pré-filtro com regras nomeadas aprova 18.145 itens (8%); recall preliminar em `docs/prefilter.md`. Amostra de 147 itens rotulada (`eval/labeled_private/`).
  - Guia de rotulagem com escopo, códigos 0–3 e casos de fronteira; licença com termo de atribuição (AGPL 7b, `NOTICE`), CC BY 4.0 para dados e textos, `CITATION.cff`.
  - Fase 2b (notícias, GDELT, repercussão internacional) adiada para depois da Fase 4, por causa do prazo.
- Fase anterior: 1 — Fundação e viabilidade (05/11/2026), mergeada na `main` (PR #1). 30 testes.
  - Cron do workflow desligado (só `workflow_dispatch`); README com licença AGPL e roadmap das fases; LICENSE conferido contra o texto oficial.
  - `pipeline/privacy.py` (IDs com HMAC, link criptografado), `pipeline/storage.py` (RawStore local), `pipeline/feasibility.py` e `docs/feasibility.md`.
  - Armazenamento remoto decidido: dataset privado no HF, criado e com acesso conferido.
  - Conta Google Cloud criada (para a Fase 2b) (crédito de teste vence ~90 dias após nov/2026); se usar BigQuery, configurar `maximum_bytes_billed` e alerta de orçamento antes da primeira consulta.
- Próxima fase: 3 — Classificador e avaliação. Entrada: os 18.145 itens aprovados pelo pré-filtro; o gabarito de 200 precisa incluir itens barrados (refaz o recall sem viés) e os casos difíceis anotados na Fase 2.
- Prazo externo: o Polari é portfólio para o estágio GenAI do iFood (trilha AI Engineer). O processo seletivo vai até 09/12/2026; a meta é se candidatar o quanto antes com uma versão mínima que mostre o lado de IA (coleta + gabarito + avaliação do LLM + BERTimbau no Hugging Face + README com resultados), alvo ~22/11. Repercussão internacional, globo e site ficam para depois da candidatura (até 09/12).

## Fases
Uma fase por conversa. Se a conversa ficar longa, atualize "Estado atual" e continue numa nova com o mesmo título + "parte 2".

1. **Fundação e viabilidade:** organização do repositório, contagem de dados por dia nas fontes, armazenamento do bruto fora do Actions, IDs com hash.
2. **Coleta de dados:** coletor de notícias com backfill e checkpoint, coletor do Bluesky, pré-filtro com recall medido, extração da repercussão internacional no GDELT ("dump global", provavelmente pelo BigQuery).
3. **Classificador e avaliação:** classificador LLM com validação, gabarito humano de 200 itens, avaliação e escolha do LLM.
4. **Modelo próprio:** rotulagem em volume, baseline TF-IDF, fine-tuning do BERTimbau, comparação final, publicação no Hugging Face.
5. **Produção:** agregação e métricas do estudo (incluindo agregados por país e por UF e a seleção de notícias para o globo), pipeline diário com roteamento BERT → LLM, cron religado.
6. **Vitrine:** site com globo interativo (países → Brasil → UF) e linha do tempo, cards de compartilhar (Stories, X, WhatsApp, Bluesky), deploy, README com resultados e GIF, artigo técnico, divulgação.
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
