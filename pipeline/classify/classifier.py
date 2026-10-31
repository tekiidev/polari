"""Classificador LLM com saída estruturada.

O que implementar:
  1. Carregar o prompt (load_prompt, já pronto).
  2. Chamar o modelo (Gemini free tier) pedindo JSON que obedeça o schema.
     Use o modo de saída estruturada do SDK (confira a doc atual do google-genai).
  3. Validar a resposta com `Classification.model_validate_json`. Se falhar, tente 1x de novo;
     persistindo a falha, marque o item como erro (não invente rótulo).
  4. Respeitar limites do free tier (≈15 req/min, ≈1.500/dia no Flash; confira os atuais):
     use backoff e processe em lotes pequenos.
  5. Gravar prompt_version junto do resultado para reprodutibilidade.
"""
from __future__ import annotations

from pipeline.config import settings
from pipeline.models import Classification

PROMPT_VERSION = "v1"


def load_prompt() -> str:
    return settings.prompt_path.read_text(encoding="utf-8")


def classify(text: str) -> Classification:
    # TODO(D2): chamada ao LLM + validação (veja o docstring do módulo).
    raise NotImplementedError("Implemente a chamada ao LLM.")
