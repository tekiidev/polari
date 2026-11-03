---
description: Inicia uma fase do projeto a partir do CLAUDE.md
argument-hint: "[número da fase, opcional]"
---

Vamos iniciar uma fase do projeto. Fase pedida: $ARGUMENTS

1. Leia o CLAUDE.md: objetivo, decisões, "Estado atual", "Fases" e "Problemas conhecidos".
2. Se eu não indiquei a fase acima, use a "Próxima fase" do "Estado atual". Se a fase anterior tiver pendências, me avise antes de começar.
3. Responda primeiro com:
   - **Título da conversa:** `Fase <N> — <nome>` (vou usar como nome desta conversa).
   - **Objetivo:** uma frase.
   - **Entregáveis:** lista, a partir da descrição da fase e dos problemas conhecidos ligados a ela.
   - **Pronto quando:** critério verificável.
   - **Fora do escopo:** o que pertence a outras fases.
   - **Skills:** as instaladas que ajudam nesta fase, e por quê.
   - **Plano:** passos numerados, cada um pequeno o suficiente para revisar.
   - **Riscos:** o que pode dar errado e como saberemos cedo.
4. Pare e espere meu ok antes de mexer em qualquer arquivo.

Durante a fase, siga as "Regras de trabalho" do CLAUDE.md. Ao terminar, resuma o que mudou, rode os testes e atualize "Estado atual" e "Problemas conhecidos".
