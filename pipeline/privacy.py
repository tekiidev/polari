"""IDs com hash e criptografia do link original.

O URI de um post do Bluesky (at://did:plc:.../app.bsky.feed.post/...) contém o DID do autor.
Por isso:
  - `item_id` é um HMAC-SHA256 com chave secreta: estável (deduplica entre execuções), mas sem
    a chave não dá para testar URIs candidatos e descobrir o autor;
  - o link original só existe criptografado (`encrypt_ref`), no armazenamento privado do bruto,
    para verificar depois se o post foi apagado. Nunca vai para o git nem para os agregados.

As duas chaves derivam de um único segredo, POLARI_SECRET_KEY. Perder ou trocar esse segredo
quebra a deduplicação e torna os links ilegíveis: guarde um backup fora do repositório.
"""
from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet

from pipeline.config import settings

ID_HEX_LEN = 32  # 128 bits: colisão desprezível no volume do projeto


def _secret(secret: str | None) -> bytes:
    value = settings.secret_key if secret is None else secret
    if len(value) < 32:
        raise RuntimeError(
            "POLARI_SECRET_KEY ausente ou curta (mínimo 32 caracteres). "
            'Gere com: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    return value.encode()


def _subkey(secret: str | None, label: bytes) -> bytes:
    return hmac.new(_secret(secret), label, hashlib.sha256).digest()


def item_id(source: str, native_id: str, secret: str | None = None) -> str:
    """ID público e estável de um item: HMAC(source, id nativo). O `source` entra para que o
    mesmo id nativo em fontes diferentes não colida."""
    msg = f"{source}\x00{native_id.strip()}".encode()
    return hmac.new(_subkey(secret, b"polari/item-id/v1"), msg, hashlib.sha256).hexdigest()[:ID_HEX_LEN]


def _fernet(secret: str | None) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_subkey(secret, b"polari/source-ref/v1")))


def encrypt_ref(ref: str, secret: str | None = None) -> str:
    return _fernet(secret).encrypt(ref.encode()).decode()


def decrypt_ref(token: str, secret: str | None = None) -> str:
    return _fernet(secret).decrypt(token.encode()).decode()
