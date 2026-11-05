# Decisão: onde guardar o texto bruto

**Status:** aceita (Fase 1). Dataset privado `tekiidev/polari-raw` criado; token fine-grained com escrita só nele.

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

## Fontes

- [Hugging Face — storage limits](https://huggingface.co/docs/hub/storage-limits)
- [Backblaze B2 — sign-up](https://www.backblaze.com/b2/sign-up.html)
- [freetier.co — Cloudflare R2](https://freetier.co/directory/products/cloudflare-r2) (fonte de terceiros; condições a conferir no cadastro)
