# Decisão: onde guardar o texto bruto

**Status:** aceita (Fase 1), confirmada por teste na Fase 2. Dataset privado `tekiidev/polari-raw` criado; token fine-grained com escrita só nele. Implementação: `pipeline/remote.py`.

## Problema

O GitHub Actions apaga o disco ao fim de cada execução, e o repositório é público. Sem um lugar
privado e persistente para o bruto não há reclassificação (Fases 3 e 4), estado incremental nem
remoção de posts apagados pelos autores.

## Requisitos

1. Privado e gratuito, no volume do projeto. Estimativa: dezenas de milhares de posts × ~0,5 KB, ou
   seja, dezenas de MB (confirmar com `docs/feasibility.md`).
2. Acessível do Actions com um token guardado em GitHub Secrets.
3. **Remoção de verdade:** um post apagado pelo autor tem de sumir também das cópias antigas.
4. Funciona com o formato local (`pipeline/storage.py`: um Parquet por fonte e dia), enviando só
   as partições que mudaram.

## Opções

| | Hugging Face (dataset privado) | Backblaze B2 | Cloudflare R2 |
|---|---|---|---|
| Grátis | 100 GB privados | 10 GB; download grátis até 3× o armazenado | 10 GB; download grátis |
| Cartão no cadastro | não | não, segundo a página de cadastro | provavelmente sim (fontes divergem) |
| Conta nova? | não: a Fase 4 já publica o modelo no HF | sim | sim |
| Envio incremental | `huggingface_hub.upload_folder` envia só arquivos alterados | API S3 (`boto3`, nova dependência) | API S3 (`boto3`) |
| Remoção de verdade | **não por padrão**: o repositório é git e guarda o histórico. Exige `HfApi.super_squash_history` depois de cada remoção | sim, com o versionamento do bucket desligado | sim |
| Risco principal | alguém tornar o repositório público por engano | mais um segredo e mais uma conta | cartão vinculado |

## Recomendação

**Dataset privado no Hugging Face**, com três salvaguardas:

- toda remoção de posts é seguida de `super_squash_history`, para que o histórico não guarde o que
  foi removido;
- o link original já está criptografado (`pipeline/privacy.py`). Se o repositório vazar, o texto
  continua sem autor identificável;
- token de escrita com permissão só nesse repositório (fine-grained), guardado em GitHub Secrets.

Justificativa: é a única opção sem conta nova e sem cartão. Usa uma biblioteca que o projeto vai
precisar de qualquer forma na Fase 4, e 100 GB sobram com folga.

**Muda para B2** se o squash do histórico se mostrar pouco confiável no teste da Fase 2, ou se os
termos do HF para dados coletados de redes sociais impedirem o uso.

## Teste da remoção (Fase 2, 05/11/2026)

Com dados sintéticos no próprio `tekiidev/polari-raw`:

1. **Só o `super_squash_history` não basta.** Depois do squash, o arquivo removido continuava
   baixável pelo SHA do commit antigo: o HF guarda os arquivos LFS fora do histórico git e não os
   apaga ao reescrever a branch.
2. **Squash + `permanently_delete_lfs_files` nos LFS órfãos resolve.** A partição removida e a versão
   antiga de uma partição reescrita ficaram inacessíveis também pelo commit antigo, e a versão viva
   continuou baixável no `main`. Órfão = LFS cujo `file_oid` não é o SHA-256 de nenhum arquivo do
   commit atual.

Por isso `RemoteRaw.push` faz as duas coisas depois de qualquer remoção, e o HF continua valendo
(o critério para trocar pelo B2 era o squash não ser confiável; com a limpeza dos LFS, é).
Outra salvaguarda: `push` nunca espelha o diretório local apagando o que falta no remoto; só apaga
caminhos listados um a um.

## Fontes

- [Hugging Face — storage limits](https://huggingface.co/docs/hub/storage-limits)
- [Backblaze B2 — sign-up](https://www.backblaze.com/b2/sign-up.html)
- [freetier.co — Cloudflare R2](https://freetier.co/directory/products/cloudflare-r2) (fonte de terceiros; condições a conferir no cadastro)
