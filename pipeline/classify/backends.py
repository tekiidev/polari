"""Backends de LLM com a mesma interface, para a avaliação tratar os três igual.

Candidatos (`docs/decisions/escolha-llm.md`): Gemini Flash (plano gratuito), Claude Haiku 5.5
(pago barato) e um modelo aberto local via Ollama. Cada um recebe o MESMO prompt
(`prompts/classifier.md`); só muda o envelope — onde vai o schema e como se pede JSON.

Regras iguais para todos, porque são o que a avaliação mede:
  - saída estruturada pelo schema do provedor, quando existe;
  - uma nova tentativa **só** em JSON inválido ou erro de rede, nunca por "resposta ruim";
  - falha persistente devolve `ClassifyError`, nunca um rótulo inventado;
  - `model_id` fixo e registrado no resultado: alias tipo `-latest` mistura versões na série.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import ValidationError

from pipeline.config import settings
from pipeline.models import Classification

# Falhas que valem uma nova tentativa: transitórias do serviço, não da resposta.
RETRIABLE = ("429", "500", "502", "503", "504", "timeout", "deadline", "unavailable", "overloaded")


@dataclass
class ClassifyResult:
    """Resultado de um item. `classification` é None quando falhou: o erro entra nas métricas."""

    item_id: str
    classification: Classification | None
    model_id: str
    prompt_version: str
    latency_s: float
    attempts: int
    error: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_text: str | None = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        return self.classification is not None

    @property
    def invalid_json(self) -> bool:
        """JSON inválido ou fora do schema: entra na taxa que elimina um modelo (limite 2%)."""
        return self.error is not None and self.error.startswith(("json:", "schema:"))


class Backend(Protocol):
    name: str
    model_id: str

    def complete(self, prompt: str) -> tuple[str, int | None, int | None]:
        """Devolve (texto da resposta, tokens de entrada, tokens de saída)."""
        ...


def load_prompt() -> str:
    return settings.prompt_path.read_text(encoding="utf-8")


def prompt_version(template: str | None = None) -> str:
    """Lê a versão do título do próprio arquivo do prompt: `# Prompt do classificador (v4)`.

    Uma constante aqui já divergiu do arquivo em 11/11: o Qwen rodou com o v2 e o Gemma com o v3
    sem que nada avisasse, e a comparação entre os dois ficou inválida. A versão gravada em cada
    resultado precisa vir do texto que foi realmente enviado.
    """
    head = (load_prompt() if template is None else template).lstrip().split("\n", 1)[0]
    match = re.search(r"\((v\d+)\)", head)
    if not match:
        raise RuntimeError(
            f"versão não encontrada no título do prompt: {head!r}. "
            "A primeira linha precisa terminar com a versão entre parênteses, ex.: '(v4)'."
        )
    return match.group(1)


def load_schema() -> dict:
    return json.loads(settings.schema_path.read_text(encoding="utf-8"))


def build_prompt(text: str, template: str | None = None) -> str:
    """Põe o texto do item no lugar de {{TEXT}}.

    O texto do post é dado, não instrução: o prompt já manda ignorar comandos dentro dele (regra
    15), e aqui garantimos que ele não possa fechar o delimitador do template.
    """
    tpl = load_prompt() if template is None else template
    safe = text.replace('"""', '\\"\\"\\"')
    return tpl.replace("{{TEXT}}", safe)


def extract_json(raw: str) -> str:
    """Recorta o objeto JSON de uma resposta que veio com cerca ou texto em volta.

    Modelo pequeno costuma embrulhar em ```json; preferimos recortar a reprovar o item, porque a
    métrica que interessa é a régua do conteúdo, não a formatação do envelope.
    """
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    return raw[start : end + 1] if 0 <= start < end else raw.strip()


def classify_one(backend: Backend, item_id: str, text: str, *, max_attempts: int = 2) -> ClassifyResult:
    """Classifica um item, com uma nova tentativa em JSON inválido ou erro transitório."""
    prompt = build_prompt(text)
    started = time.monotonic()
    last_error = "sem tentativa"
    raw = None
    tokens_in = tokens_out = None

    for attempt in range(1, max_attempts + 1):
        try:
            raw, tokens_in, tokens_out = backend.complete(prompt)
        except Exception as exc:  # o SDK de cada provedor levanta exceções próprias
            last_error = f"api: {type(exc).__name__}: {exc}"[:200]
            if attempt < max_attempts and any(s in str(exc).lower() for s in RETRIABLE):
                time.sleep(2**attempt)  # backoff: o limite do plano gratuito é por minuto
                continue
            break

        try:
            payload = json.loads(extract_json(raw))
        except json.JSONDecodeError as exc:
            last_error = f"json: {exc}"[:200]
            if attempt < max_attempts:
                continue
            break

        try:
            classification = Classification.model_validate(payload)
        except ValidationError as exc:
            # Inclui as regras de coerência: tipo preenchido com total negativo, por exemplo.
            last_error = f"schema: {exc.errors()[0]['msg'] if exc.errors() else exc}"[:200]
            if attempt < max_attempts:
                continue
            break

        return ClassifyResult(
            item_id=item_id,
            classification=classification,
            model_id=backend.model_id,
            prompt_version=prompt_version(),
            latency_s=time.monotonic() - started,
            attempts=attempt,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            raw_text=raw,
        )

    return ClassifyResult(
        item_id=item_id,
        classification=None,
        model_id=backend.model_id,
        prompt_version=prompt_version(),
        latency_s=time.monotonic() - started,
        attempts=max_attempts,
        error=last_error,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        raw_text=raw,
    )


class GeminiBackend:
    """Candidato A: Gemini Flash no plano gratuito.

    Plano gratuito decidido em 10/11 (`docs/decisions/escolha-llm.md`): o Google pode usar as
    entradas e revisores humanos podem lê-las, então a privacidade pesa contra ele no desempate, e
    a rotulagem em volume da Fase 4 vai para o plano pago se ele vencer.
    """

    name = "gemini"

    def __init__(self, model_id: str | None = None, think: bool = False):
        from google import genai

        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY ausente no .env")
        # ID exato, nunca alias com -latest: a série não pode trocar de modelo sem aviso.
        self.model_id = model_id or settings.gemini_model
        # Medido em 10/11 no mesmo item: com raciocínio, 7,2 s e ~1.000 tokens de pensamento; sem,
        # 3,3 s e a mesma resposta. A tarefa é classificação com régua escrita, então não se paga.
        self._think = think
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def complete(self, prompt: str) -> tuple[str, int | None, int | None]:
        config = {
            "response_mime_type": "application/json",
            "response_json_schema": load_schema(),
            "temperature": 0.0,  # fixo: duas execuções do mesmo item devem concordar
        }
        if not self._think:
            config["thinking_config"] = {"thinking_budget": 0}
        response = self._client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=config,
        )
        usage = getattr(response, "usage_metadata", None)
        return (
            response.text or "",
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
        )


class OpenAIBackend:
    """Candidato pago (decisão de 10/11, depois de a cota gratuita inviabilizar o Gemini).

    Usa saída estruturada por JSON schema (`json_schema` com `strict`), que garante resposta
    válida pelo schema em vez de pedir JSON no prompt e torcer.

    O modelo vem do `.env` (`OPENAI_MODEL`) e é registrado em cada resultado: a série não pode
    trocar de modelo sem aviso. Precisa de `OPENAI_API_KEY`.
    """

    name = "openai"

    def __init__(self, model_id: str | None = None):
        import openai

        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY ausente no .env")
        self.model_id = model_id or settings.openai_model
        if not self.model_id:
            raise RuntimeError("OPENAI_MODEL ausente no .env (ID exato, nunca alias)")
        self._client = openai.OpenAI(api_key=settings.openai_api_key)
        self._schema = load_schema()

    def complete(self, prompt: str) -> tuple[str, int | None, int | None]:
        response = self._client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "user", "content": prompt}],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "classification",
                    "strict": True,
                    "schema": self._schema,
                },
            },
        )
        usage = response.usage
        return (
            response.choices[0].message.content or "",
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
        )


class ClaudeBackend:
    """Claude Haiku 5.5. **Fora dos candidatos avaliados nesta fase** (decisão de 10/11).

    Implementado e testado, mas não entra na comparação: exige cartão de crédito, e o projeto
    demonstra custo de API zero. Fica pronto para depois da candidatura, quando acrescentar um
    candidato custa só a execução. Precisa de `ANTHROPIC_API_KEY` no ambiente.

    US$ 0,10/0,50 por milhão de tokens (entrada/saída), metade no Batch. A API comercial não treina
    com os dados por padrão. Esforço `low` porque a tarefa é classificação com régua escrita, e
    pensamento longo aqui só gasta tokens de saída.
    """

    name = "claude"

    def __init__(self, model_id: str = "claude-haiku-5-5"):
        import anthropic

        self.model_id = model_id
        self._client = anthropic.Anthropic()
        self._schema = load_schema()

    def complete(self, prompt: str) -> tuple[str, int | None, int | None]:
        response = self._client.messages.create(
            model=self.model_id,
            max_tokens=1024,
            output_config={
                "effort": "low",
                "format": {
                    "type": "json_schema",
                    "schema": self._schema,
                },
            },
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        return text, response.usage.input_tokens, response.usage.output_tokens


class OllamaBackend:
    """Candidatos B e C: modelos abertos locais. Privacidade absoluta e pesos fixos.

    Dois modelos de origens diferentes (Qwen, da Alibaba; Gemma, do Google) para o teste de
    simetria comparar treinos distintos. Não resolvem o pipeline diário: o runner do Actions é
    efêmero e sem GPU — quem roda todo dia é o BERTimbau (Fase 4).

    O risco destes candidatos é tempo, não custo: 16 GB rodam um por vez, e o eliminatório é
    ~7 s por item.
    """

    name = "ollama"

    def __init__(
        self,
        model_id: str = "qwen3:8b",
        host: str = "http://localhost:11434",
        think: bool = False,
    ):
        self.model_id = model_id
        self._host = host
        self._schema = load_schema()
        # Qwen3 raciocina antes de responder por padrão: medido em 10/11, gastava 450–630 tokens de
        # saída para um JSON de ~80 e levava ~29 s por item, contra o limite de ~7 s. A tarefa é
        # classificação com régua escrita, então o raciocínio longo não se paga aqui.
        self._think = think

    def complete(self, prompt: str) -> tuple[str, int | None, int | None]:
        import httpx

        payload = {
            "model": self.model_id,
            "prompt": prompt,
            "stream": False,
            "format": self._schema,  # JSON schema: o Ollama restringe a geração
            "options": {"temperature": 0.0},
        }
        if not self._think:
            payload["think"] = False  # modelos sem modo de raciocínio ignoram o campo
        response = httpx.post(
            f"{self._host}/api/generate",
            json=payload,
            timeout=180.0,  # modelo local em CPU/GPU integrada é lento
        )
        response.raise_for_status()
        body = response.json()
        return (
            body.get("response", ""),
            body.get("prompt_eval_count"),
            body.get("eval_count"),
        )


def _qwen(**kwargs) -> OllamaBackend:
    return OllamaBackend(model_id=kwargs.pop("model_id", "qwen3:8b"), **kwargs)


def _gemma(**kwargs) -> OllamaBackend:
    return OllamaBackend(model_id=kwargs.pop("model_id", "gemma3:12b"), **kwargs)


def _luna(**kwargs) -> OpenAIBackend:
    """Nome próprio para o `gpt-6-luna`: o arquivo de resultados é por backend, e um mesmo
    nome para dois modelos misturaria as duas execuções no mesmo `openai__dev__run1.jsonl`."""
    return OpenAIBackend(model_id=kwargs.pop("model_id", "gpt-6-luna"), **kwargs)


# Candidatos avaliados nesta fase. `openai` entrou em 10/11, quando a cota de 20 requisições por
# dia do plano gratuito do Gemini inviabilizou o candidato A e o Qwen reprovou no tempo.
CANDIDATES = ("openai", "luna", "gemini", "qwen", "gemma")

BACKENDS = {
    "gemini": GeminiBackend,
    "qwen": _qwen,
    "gemma": _gemma,
    "openai": OpenAIBackend,
    "luna": _luna,
    "ollama": OllamaBackend,  # genérico: qualquer modelo do Ollama por --model-id
    "claude": ClaudeBackend,  # implementado, fora dos candidatos; precisa de ANTHROPIC_API_KEY
}


def make_backend(name: str, **kwargs) -> Backend:
    if name not in BACKENDS:
        raise SystemExit(f"backend desconhecido: {name}. Opções: {', '.join(BACKENDS)}")
    return BACKENDS[name](**kwargs)
