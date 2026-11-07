# Guia de rotulagem

**is_political_violence = true** somente se o texto trata de violência/ameaça/intimidação com
motivação política ou eleitoral claramente indicada no próprio texto.

## Como decidir

Duas perguntas, nesta ordem; `true` só se as duas forem "sim":

1. **Há violência concreta?** Ato ou ameaça feito, tentado, planejado ou relatado: agressão, tiro,
   morte, ameaça, intimidação, coação, depredação, repressão policial.
2. **O contexto político está no próprio texto?** A vítima tem papel político, o fato ocorreu em
   ato político ou o texto dá motivo político.

Rótulo na amostra do pré-filtro (`eval/labeled_private/prefilter_sample.csv`):

| valor | significado |
|---|---|
| `1` | violência política no Brasil (ou envolvendo brasileiros, mesmo fora do país) |
| `2` | violência política pelos mesmos critérios, mas em outro país (qualquer tipo, inclusive verbal) |
| `3` | violência verbal política no Brasil: xingamento sem ameaça (ver "Violência verbal") |
| `0` | não é violência política |

Se o texto tiver xingamento **e** ameaça ou agressão, vale o mais grave: `1`.

`2` é um `1` com etiqueta de país, não um "não conta": a régua é a mesma em qualquer lugar. A série
padrão ("no Brasil") usa só `1`; a leitura "discurso sobre violência política no Bluesky
brasileiro" usa `1` e `2`. Sem país identificável no texto, considere Brasil.

## Regras gerais

- **Só o texto do item.** Post + linha `[link]` (título e descrição do cartão). Não abra o artigo
  nem leia comentários: o classificador só vê esse texto. Título vago ("Entenda o caso") sem
  violência visível → `0`. Comentários são outros posts e contam por si.
- **Julgue pelo texto, não pelo que você sabe do caso.** A régua precisa ser reproduzível por
  outra pessoa e pelo modelo.
- **Vínculo eleitoral não é exigido.** O critério é contexto político, não eleitoral: a relação
  com a eleição se mede comparando períodos (base × campanha × D±14), com a mesma régua. Exigir
  vínculo eleitoral zeraria a linha de base por definição.
- **Suspeita conta.** O Polari mede o discurso, não a ocorrência comprovada: "polícia investiga se
  a morte do vereador teve motivação política", "suspeito de mandar matar a prefeita", "PF suspeita
  de plano para atacar candidato" → `1`. Só vira `0` se o texto descartar o motivo político ou se o
  suspeito não for violência (fraude, corrupção).
- **Teste da simetria.** Troque os lados políticos do texto: o rótulo tem de ser o mesmo.

## O que entra

- **Violência contra quem tem papel político:** candidatos, eleitos, cabos eleitorais, militantes,
  jornalistas cobrindo política. Ex.: "Vereadora foi morta a tiros", mesmo sem a palavra "eleição".
- **Agressão em ato político:** briga, pancadaria ou ataque em manifestação, protesto, passeata,
  carreata ou comício. Ex.: "Pancadaria no protesto, vários feridos".
- **Repressão policial a ato político:** bala de borracha, gás, spray de pimenta ou agressão da
  polícia contra manifestação política. Ex.: "PM reprime ato no centro".
- **Casos isolados com motivação política:** agressão ou morte por causa de posição política,
  fora de evento. Ex.: "Bolsonarista mata petista em festa", "espancado por usar camisa do PT",
  "morto após discussão política em bar".
- **Linguagem indireta para um fato real:** "partiu pra cima do deputado", "teve cadeirada no
  debate", "tomou uma voadora no ato" → `true`.
- **Incitação, inclusive indireta:** o texto chama, aprova ou ameaça violência contra um **alvo
  identificável** (pessoa ou grupo), mesmo sem verbo explícito: "alguém devia resolver esse
  problema de vez", "CPF cancelado", 🔫 ao lado do nome, expor endereço com "vocês sabem o que
  fazer", "bem feito, foi pouco" sobre uma agressão, "tomara que morra". Teste: alvo **e** alusão a
  dano físico ou coação. O critério é o conteúdo do texto, não o efeito possível no leitor ("pode
  incitar" vale para quase todo post exaltado).
- **Ameaça de força contra instituições:** "vamos invadir o STF", "se perder, vai ter sangue"
  (`intimidacao_institucional`).
- **Protesto com pauta dirigida ao poder público,** inclusive greve de servidores em ato público.
- **Lideranças sociais e ativistas** (indígena, quilombola, sem-terra, sindical, defensor de direitos
  humanos): `1` quando o texto menciona o cargo ou a atuação política da vítima ("liderança que
  denunciava garimpo é assassinada"). Conflito de terra sem essa menção → `0`.
- **Interferência estrangeira na política ou nas eleições brasileiras** (decisão do autor, 07/11/2026):
  governo ou Estado de outro país interferindo, pressionando ou coagindo a política brasileira →
  `1` (o alvo é o Brasil, então não é `2`). Vale para qualquer país e contra qualquer lado: "o
  governo Trump interfere nas eleições" e "a China financia a esquerda" recebem o mesmo rótulo
  (teste da simetria). Exige a interferência descrita no texto; opinião sobre política externa sem
  interferência no Brasil → `0`. Empresas (plataformas) e órgãos brasileiros não entram nesta regra.
  Consequência: a série deixa de medir só violência contra pessoas; a metodologia (Fase 5) precisa
  dizer isso, e o pré-filtro não foi desenhado para este vocabulário.
- **Impedir alguém de votar** por ameaça, coação ou obstrução (bloqueio, intimidação na seção,
  "vote em X ou perde o emprego"). Não votar por problema técnico (urna, fila, título) → `0`.

## Violência verbal (código `3`, tipo `ofensa`)

Xingamento sem ameaça conta como violência verbal política quando é dirigido:

- a **quem tem papel político**: prefeito, vereador, deputado, senador, governador, presidente,
  candidato, militante, liderança. Ex.: "esse vereador é um vagabundo";
- a alguém **por causa da posição política explícita no texto**. Ex.: "petista imundo",
  "bolsonarista lixo".

A regra se lê no próprio texto: não é preciso saber o lado de quem escreveu, o que exigiria inferir
orientação política de pessoas. Crítica sem xingamento ("o prefeito é incompetente") → `0`.

Por que código próprio: xingamento a político é o conteúdo mais comum do Bluesky político e, somado
aos outros, dominaria a série. A visão padrão mostra violência física, ameaça e intimidação; a
ofensa verbal aparece como camada separada. O pré-filtro não tem léxico de insultos, então a maior
parte desses casos cai no contexto barrado: o relatório de recall mostra esse custo.

## O que não entra

- **Operação policial comum** (ex.: operação em favela, abordagem), salvo se o texto der motivação
  política. Sem esse limite, o Polari vira monitor de violência policial em geral.
- **Metáfora e hipérbole:** "vou matar esse adversário no debate", "massacrou no debate" → `false`,
  natureza `opiniao_ou_ironia`. É a fronteira mais difícil com o item anterior: pergunte se o texto
  descreve um ato físico ou ameaça concreta.
- **Discussão do tema sem caso:** "a violência política cresce no país" é `true` só se citar caso
  ou ameaça concreta; análise genérica → `false`.
- **Violência sem motivação política:** briga de torcida, trânsito, crime comum contra alguém que
  por acaso é político, quando o próprio texto diz que o motivo não é político. Conflito
  trabalhista contra empresa privada também fica fora.
- **Ataque à democracia sem violência e sem interferência estrangeira:** "as urnas são fraudadas", "a
  eleição foi roubada", pedido de intervenção sem ameaça de força. É desinformação ou discurso
  antidemocrático, outro fenômeno. Crítica à cobertura da imprensa também fica fora.
- **Crítica dura ou chamado para protesto sem força:** "fora fulano", "impeachment já", "todo mundo
  pra rua domingo".
- **Desumanização + chamado de luta sem ato concreto:** "é guerra contra essa corja até o fim" →
  `0`, anotado como caso difícil. "Vermes", "corja" são sinal de risco, mas o Polari mede violência
  política, não discurso de ódio; a régua é o conteúdo, não o efeito possível.

## Natureza do relato

- Notícia compartilhada sobre um fato → `true`, natureza `noticia_compartilhada`.
- "Disseram que fulano foi espancado" sem fonte → `true`, natureza `boato_nao_verificado`.
- Quem relata ter vivido o fato → `relato_primeira_mao`.
- Incentivo a violência futura → `incitacao`.
- Na dúvida entre dois valores, use `indeterminado` e confiança baixa.

## O que nunca registrar

- **Lado político de uma pessoa** (esquerda/direita, partido de vítima ou agressor). Termos de
  espectro só servem para achar o post. Orientação política é dado sensível (LGPD) e, ligada a um
  caso, identifica a pessoa. Também não sustenta comparação séria ("um lado agride mais").
- Cidade/UF só se citadas explicitamente. Não deduza pelo contexto.

## Em aberto (decisão do autor)

Nenhuma no momento.

## Pendente para a Fase 3

- O schema não tem quem cometeu a violência. Sem isso, "apoiador agrediu adversário" e "polícia
  reprimiu ato" caem na mesma contagem. Proposta: `perpetrator_type` = apoiador / agente do Estado /
  indeterminado (sem lado político). `TargetType` também não tem "manifestante".
- `vinculo_eleitoral` (sim/não: o texto cita eleição, campanha, candidatura ou voto), para medir que
  parte do discurso sobre violência política é explicitamente eleitoral em cada período.
- Campo de país, se a amostra do pré-filtro tiver muitos `2`.
- Pares espelhados (mesmo texto com os lados trocados) no gabarito, para testar viés do LLM.
