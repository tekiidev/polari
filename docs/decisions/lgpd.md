# Decisão: base legal e proteção de dados (LGPD)

**Status:** proposta (Fase 3, 09/11/2026). Escrito depois das medidas técnicas, o que é a ordem
errada: as salvaguardas de `pipeline/privacy.py` existem desde a Fase 1, mas nada registrava **por
que** o Polari pode tratar esses dados. Este documento fecha essa lacuna.

Não é parecer jurídico. É o registro da decisão do autor, com os artigos em que ela se apoia, para
que a escolha possa ser auditada e contestada.

## O dado tratado

228.204 posts públicos do Bluesky (`lang=pt`, 01/06 a 04/11/2026), coletados pela API de busca da
plataforma. De cada post guardamos: texto, data de criação, idioma, consultas que o trouxeram, um
ID derivado por HMAC e o URI original **criptografado**. Nunca guardamos handle, nome de perfil,
avatar, seguidores nem qualquer outro campo do autor.

**Isso é dado pessoal.** Post público não deixa de ser dado pessoal (a LGPD não tem exceção para
"dado público"; o art. 7º, §4º apenas dispensa novo consentimento quando o próprio titular tornou
o dado público, e ainda assim exige finalidade e boa-fé). E o texto de um post político
frequentemente revela **opinião política do autor**, que é dado sensível pelo art. 11.

Consequência prática: o Polari trata dado sensível, mesmo não registrando o lado político de
ninguém. Não registrar é uma medida de minimização, não um motivo para o art. 11 deixar de valer.

## Base legal

**Finalidade de pesquisa, art. 7º, IV, combinado com o art. 11, II, "c".**

O art. 7º, IV autoriza o tratamento "para a realização de estudos por órgão de pesquisa,
garantida, sempre que possível, a anonimização". O art. 11, II, "c" repete a autorização para
dado sensível, com a mesma ressalva de anonimização.

**Por que não consentimento:** seria preciso obter de 228 mil pessoas. Pedir implicaria contatar
cada autor, o que exigiria guardar o handle de todos — mais dado pessoal do que o projeto trata
hoje, para proteger menos.

**Por que não legítimo interesse (art. 7º, IX):** é a base que eu usaria por reflexo, e ela **não
vale para dado sensível**. O art. 11 tem lista própria e fechada, e legítimo interesse não está
nela. Usar o art. 7º, IX aqui seria um erro.

**O ponto fraco desta escolha, declarado:** o art. 7º, IV fala em "órgão de pesquisa", que o art.
5º, XVIII define como entidade da administração pública ou pessoa jurídica de direito privado sem
fins lucrativos com missão de pesquisa. **O Polari é um projeto individual, não um órgão de
pesquisa.** Então a base legal é, com honestidade, imperfeita.

O que sustenta a decisão de seguir, mesmo assim:

1. a finalidade é genuinamente de pesquisa, sem uso comercial, publicitário ou de perfilamento;
2. o resultado publicado é **agregado e anônimo** — a anonimização que os dois artigos pedem
   "sempre que possível" é feita, não prometida;
3. o tratamento é jornalístico-acadêmico no sentido do art. 4º, II, "a" e "b" (fins exclusivamente
   jornalísticos, artísticos ou acadêmicos), hipótese em que a LGPD não se aplica integralmente;
4. nenhuma decisão sobre pessoa alguma é tomada a partir desses dados.

**Se o projeto mudar de finalidade** — uso comercial, venda de acesso, qualquer análise individual
— esta base legal deixa de valer e o tratamento precisa parar até ser refeito.

## Finalidade, e o que ela proíbe

**Finalidade declarada:** medir a frequência e a distribuição do **discurso** sobre violência
política no Brasil, por período e por unidade federativa, de forma agregada.

O princípio da finalidade (art. 6º, I) e o da necessidade (art. 6º, III) tornam proibido, mesmo
sendo tecnicamente possível com os dados em mãos:

- perfilar autores, contar posts por pessoa, medir quem fala mais;
- inferir orientação política, localização, gênero ou qualquer atributo de autor;
- publicar texto de post, ainda que anonimizado (texto é buscável e leva ao autor);
- cruzar os dados com outra base para reidentificar;
- treinar modelo que reproduza texto de autor identificável — o BERTimbau da Fase 4 é
  classificador, não gerador.

## Medidas técnicas, e o que cada uma protege

Verificado no código em 09/11/2026:

| medida | onde | contra o quê |
|---|---|---|
| `item_id` = HMAC-SHA256 com chave secreta, 128 bits | `privacy.py` | o URI do Bluesky contém o DID do autor; sem a chave não se testa URI candidato para achar quem é |
| URI original só criptografado (Fernet, subchave própria) | `privacy.py`, `storage.py` | permite checar post apagado sem guardar o link em claro |
| Subchaves separadas por rótulo para ID e para link | `privacy.py` | comprometer um uso não compromete o outro |
| Handle, perfil e avatar nunca gravados | `models.RawItem` | minimização (art. 6º, III) |
| `source_ref` fora de `model_dump()` | `models.RawItem` | o link não escapa por serialização acidental |
| Texto bruto fora do git | `.gitignore` (`data/raw/`, `eval/labeled_private/`) | repositório é público |
| Bruto em dataset privado no HF, token restrito a ele | `remote.py` | limita o alcance de um token vazado |
| Remoção real: squash + apagar LFS órfãos | `remote.py`, medido em 05/11 | post apagado pelo autor desaparece também do histórico |
| `push` nunca apaga por espelhamento | `remote.py` | remoção acidental em massa |
| Nenhum log imprime texto de post | verificado por busca em `pipeline/` | texto em log de CI é texto público |
| Orientação política fora do schema | `models.py`, guia | art. 11 |
| Mínimo k na agregação, por tipo e no total | decidido, a implementar na Fase 5 | reidentificação por célula pequena |
| Posts nunca no site; só notícia com link | decidido, Fase 6 | o texto levaria ao autor |

## Riscos conhecidos, sem solução completa

Declarados porque "seguro" sem ressalva seria falso.

1. **A chave é ponto único de falha.** Se `POLARI_SECRET_KEY` vazar junto de uma cópia do dataset
   bruto, o HMAC deixa de proteger: o espaço de DIDs do Bluesky é enumerável, e quem tiver a chave
   recalcula os IDs e reidentifica os autores. Mitigação atual: a chave vive em GitHub Secrets e em
   `.env` local (fora do git), e o dataset é privado — os dois teriam de vazar juntos. **Não há
   rotação**, e rotacionar quebraria a deduplicação e os links já gravados. Pendência real.
2. **O texto bruto é dado sensível guardado por tempo indeterminado.** Ele é necessário para
   reclassificar (Fases 3 e 4) e não pode ser descartado agora. Falta política de retenção com
   prazo: proposta é revisar ao fim da Fase 4 e avaliar se o texto completo ainda é necessário ou
   se bastam os rótulos.
3. **Remoção depende de detecção.** O mecanismo de apagar existe e foi testado, mas a varredura
   que descobre quais posts sumiram do Bluesky ainda não roda (pendência da Fase 5). Até lá, post
   apagado pelo autor continua na cópia local.
4. **Não há canal para o titular.** Sem contato publicado, os direitos do art. 18 (confirmação,
   acesso, eliminação) não são exercíveis na prática. A corrigir no README, junto de um
   procedimento de remoção por item.
5. **As salvaguardas dependem de disciplina, não de verificação.** O `.gitignore` e a ausência de
   texto em logs valem hoje porque foram conferidos à mão. Proposta de três testes automáticos
   (Fase 5): falhar se arquivo com texto bruto entrar no índice do git; varrer os JSON públicos
   procurando texto ou célula abaixo do k; confirmar que nenhum logger recebe `item.text`.

## Direitos do titular (art. 18)

Procedimento proposto, a publicar no README:

- **Eliminação:** qualquer pessoa pode pedir a remoção dos próprios posts, informando o handle ou
  o link do post. O pedido é atendido apagando o item do bruto, com squash e limpeza de LFS; os
  agregados já publicados não são recalculados, porque não contêm o item individualmente e
  recalcular revelaria qual foi removido.
- **Confirmação e acesso:** respondidos de forma qualitativa (se há ou não posts daquele autor no
  recorte), sem devolver o conteúdo coletado, que é o próprio post público do titular.
- **Apagar o post no Bluesky basta.** A varredura da Fase 5 passa a remover automaticamente o que
  sumiu da origem, sem precisar de pedido.

## Fontes

- [Lei 13.709/2018 (LGPD)](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm): arts. 4º, 5º, 6º, 7º, 11, 18, 37.
- `docs/decisions/armazenamento-bruto.md`: teste de remoção no Hugging Face (05/11/2026).
- `eval/labeling_guide.md`: por que nenhum campo registra lado político.
