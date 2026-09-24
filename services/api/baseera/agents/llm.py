"""Language-model providers for the analyst team.

Three engines share one small interface:

* ``AnthropicProvider`` – Claude through the official Anthropic SDK: tool use, adaptive
  thinking, prompt caching and server-side refusal fallbacks. The recommended engine.
* ``OllamaProvider`` – a local model through Ollama's chat API with function calling,
  for deployments where no data may leave the premises.
* ``None`` (deterministic) – no model at all. The orchestrator then runs its built-in
  expert playbook, so the product still produces a complete analysis offline.

A provider opens a ``ChatSession`` that owns its own message history in the provider's
native format, so the orchestrator's tool loop is provider-agnostic.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from ..config import Settings
from ..errors import AppError


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class Turn:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: dict[str, Any] = field(default_factory=dict)


class ChatSession(Protocol):
    def send(self, text: str) -> Turn: ...

    def send_tool_results(self, results: list[tuple[ToolCall, str, bool]]) -> Turn: ...


class Provider(Protocol):
    name: str
    model: str

    def status(self) -> dict[str, Any]: ...

    def session(
        self, system: str, tools: list[dict[str, Any]], json_schema: dict[str, Any] | None = None
    ) -> ChatSession: ...


# --------------------------------------------------------------------------- Anthropic
class AnthropicProvider:
    name = "anthropic"

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self.model = settings.anthropic_model
        self._client = client

    def client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key,
                timeout=self.settings.anthropic_timeout_seconds,
                max_retries=2,
            )
        return self._client

    def status(self) -> dict[str, Any]:
        return {
            "provider": "anthropic",
            "model": self.model,
            "status": "configured"
            if self.settings.anthropic_api_key or self._client
            else "not_configured",
            "effort": self.settings.anthropic_effort,
            "execution": "hosted",
            "refusal_fallbacks": self.settings.anthropic_fallbacks,
        }

    def session(
        self, system: str, tools: list[dict[str, Any]], json_schema: dict[str, Any] | None = None
    ) -> AnthropicSession:
        return AnthropicSession(self, system, tools, json_schema)


class AnthropicSession:
    def __init__(
        self,
        provider: AnthropicProvider,
        system: str,
        tools: list[dict[str, Any]],
        json_schema: dict[str, Any] | None,
    ) -> None:
        self.provider = provider
        self.system = system
        self.tools = tools
        self.json_schema = json_schema
        self.messages: list[dict[str, Any]] = []

    def _create(self) -> Any:
        import anthropic

        settings = self.provider.settings
        output_config: dict[str, Any] = {"effort": settings.anthropic_effort}
        if self.json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": self.json_schema}
        params: dict[str, Any] = {
            "model": self.provider.model,
            "max_tokens": 16000,
            "system": self.system,
            "messages": self.messages,
            "thinking": {"type": "adaptive"},
            "output_config": output_config,
            # Stable system prompt and tool list first: repeated turns hit the cache.
            "cache_control": {"type": "ephemeral"},
        }
        if self.tools:
            params["tools"] = self.tools
        client = self.provider.client()
        try:
            if settings.anthropic_fallbacks:
                return client.beta.messages.create(
                    **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
                )
            return client.messages.create(**params)
        except anthropic.AuthenticationError as exc:
            raise AppError(
                503, "provider_auth_failed", "The Anthropic API key was rejected."
            ) from exc
        except anthropic.PermissionDeniedError as exc:
            raise AppError(
                503, "provider_denied", "The Anthropic key lacks access to this model."
            ) from exc
        except anthropic.NotFoundError as exc:
            raise AppError(
                503, "model_missing", f"Model {self.provider.model!r} is unavailable."
            ) from exc
        except anthropic.RateLimitError as exc:
            raise AppError(
                429, "provider_busy", "The model provider is rate limiting; retry shortly."
            ) from exc
        except anthropic.BadRequestError as exc:
            raise AppError(
                502, "provider_request_invalid", f"The model rejected the request: {exc.message}"
            ) from exc
        except anthropic.APIStatusError as exc:
            raise AppError(
                503, "provider_unavailable", f"The model provider failed ({exc.status_code})."
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise AppError(
                503, "provider_unavailable", "Could not reach the Anthropic API."
            ) from exc

    def _turn(self) -> Turn:
        started = time.monotonic()
        response = self._create()
        # Thinking and tool-use blocks must be returned unchanged on the next request.
        self.messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "refusal":
            raise AppError(422, "provider_refused", "The model declined this request.")
        text = "".join(block.text for block in response.content if block.type == "text")
        calls = [
            ToolCall(block.id, block.name, dict(block.input or {}))
            for block in response.content
            if block.type == "tool_use"
        ]
        usage = getattr(response, "usage", None)
        return Turn(
            text=text,
            tool_calls=calls,
            stop_reason=str(response.stop_reason),
            usage={
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None),
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "model": getattr(response, "model", self.provider.model),
            },
        )

    def send(self, text: str) -> Turn:
        self.messages.append({"role": "user", "content": text})
        return self._turn()

    def send_tool_results(self, results: list[tuple[ToolCall, str, bool]]) -> Turn:
        # Every result goes back in one user message so parallel tool use keeps working.
        self.messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": content,
                        **({"is_error": True} if is_error else {}),
                    }
                    for call, content, is_error in results
                ],
            }
        )
        return self._turn()


# ------------------------------------------------------------------------------ Ollama
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "ollama"}


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self.model = settings.llm_model
        self.transport = transport

    def base_url(self) -> str:
        url = self.settings.llm_base_url or ""
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise AppError(503, "provider_configuration_invalid", "Review the Ollama base URL.")
        if parsed.scheme == "http" and parsed.hostname not in LOCAL_HOSTS:
            raise AppError(503, "provider_configuration_invalid", "Remote Ollama requires HTTPS.")
        return url.rstrip("/")

    def status(self) -> dict[str, Any]:
        return {
            "provider": "ollama",
            "model": self.model,
            "status": "configured" if self.settings.llm_base_url else "not_configured",
            "execution": "local",
        }

    def session(
        self, system: str, tools: list[dict[str, Any]], json_schema: dict[str, Any] | None = None
    ) -> OllamaSession:
        return OllamaSession(self, system, tools, json_schema)


class OllamaSession:
    def __init__(
        self,
        provider: OllamaProvider,
        system: str,
        tools: list[dict[str, Any]],
        json_schema: dict[str, Any] | None,
    ) -> None:
        self.provider = provider
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            for tool in tools
        ]
        self.json_schema = json_schema
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": system}]

    def _turn(self) -> Turn:
        settings = self.provider.settings
        payload: dict[str, Any] = {
            "model": self.provider.model,
            "messages": self.messages,
            "stream": False,
            "think": False,
            "keep_alive": "10m",
            "options": {
                "temperature": 0,
                "seed": 20260630,
                "num_ctx": min(max(settings.llm_context_tokens, 8192), 32768),
                "num_predict": 2048,
                "num_thread": min(max(settings.llm_threads, 1), 16),
            },
        }
        if self.tools:
            payload["tools"] = self.tools
        if self.json_schema is not None:
            payload["format"] = self.json_schema
        started = time.monotonic()
        timeout = httpx.Timeout(min(max(settings.llm_timeout_seconds, 10), 600), connect=5)
        try:
            with httpx.Client(
                timeout=timeout, trust_env=False, transport=self.provider.transport
            ) as client:
                response = client.post(f"{self.provider.base_url()}/api/chat", json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.TimeoutException as exc:
            raise AppError(504, "provider_timeout", "The local model timed out.") from exc
        except httpx.HTTPError as exc:
            raise AppError(503, "provider_unavailable", "Could not reach local Ollama.") from exc
        message = body.get("message") or {}
        self.messages.append(
            {
                "role": "assistant",
                "content": message.get("content", ""),
                **({"tool_calls": message["tool_calls"]} if message.get("tool_calls") else {}),
            }
        )
        calls = []
        for index, call in enumerate(message.get("tool_calls") or []):
            function = call.get("function", {})
            arguments = function.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    arguments = {}
            calls.append(
                ToolCall(f"call-{len(self.messages)}-{index}", function.get("name", ""), arguments)
            )
        return Turn(
            text=message.get("content", "") or "",
            tool_calls=calls,
            stop_reason="tool_use" if calls else str(body.get("done_reason", "stop")),
            usage={
                "input_tokens": body.get("prompt_eval_count"),
                "output_tokens": body.get("eval_count"),
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "model": self.provider.model,
            },
        )

    def send(self, text: str) -> Turn:
        self.messages.append({"role": "user", "content": text})
        return self._turn()

    def send_tool_results(self, results: list[tuple[ToolCall, str, bool]]) -> Turn:
        for call, content, _ in results:
            self.messages.append({"role": "tool", "content": content, "tool_name": call.name})
        return self._turn()


# ---------------------------------------------------------------------------- choose
def select_provider(settings: Settings) -> Provider | None:
    """Pick the engine for this deployment. ``None`` means the deterministic playbook."""

    choice = settings.agent_provider
    if choice == "deterministic":
        return None
    if choice in {"anthropic", "claude"}:
        return AnthropicProvider(settings)
    if choice == "ollama":
        return OllamaProvider(settings)
    # auto: a configured key selects Claude. Other credential sources (an OAuth profile,
    # workload identity) are honoured when BASEERA_AGENT_PROVIDER=anthropic is set.
    if settings.anthropic_api_key:
        return AnthropicProvider(settings)
    if settings.llm_provider == "ollama" and settings.llm_base_url:
        return OllamaProvider(settings)
    return None


def engine_status(settings: Settings) -> dict[str, Any]:
    provider = select_provider(settings)
    if provider is None:
        return {
            "provider": "deterministic",
            "model": None,
            "status": "available",
            "execution": "local",
            "description": {
                "en": "Built-in expert engine: complete statistical analysis and templated "
                "narrative without a language model. Configure Claude for conversational "
                "reasoning and richer writing.",
                "ar": "المحرك الخبير المدمج: تحليل إحصائي كامل وسرد منظم دون نموذج لغوي. "
                "اضبط Claude للحصول على حوار واستدلال وكتابة أغنى.",
            },
        }
    return provider.status()
