"""Provider-agnostic chat-completion client built on the OpenAI Python SDK (>= 1.x).

Providers
---------
``openai``  The OpenAI API, or any OpenAI-compatible server selected with ``base_url`` /
            ``OPENAI_BASE_URL`` (e.g. OpenRouter for Qwen-2.5-72B, or a local vLLM server for
            Qwen-2.5-VL-72B, as used in the paper).
``azure``   Azure OpenAI. ``model`` is then the *deployment* name.

Environment variables
---------------------
``OPENAI_API_KEY``, ``OPENAI_BASE_URL``,
``AZURE_OPENAI_API_KEY``, ``AZURE_OPENAI_ENDPOINT``, ``AZURE_OPENAI_API_VERSION``.

Transient failures (rate limits, timeouts, 5xx) are retried by the SDK with exponential
back-off. Authentication and configuration errors are raised immediately instead of being
swallowed, so a misconfigured run fails fast rather than silently producing empty answers.
"""

from __future__ import annotations

import base64
import mimetypes
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .usage import UsageTracker

PROVIDERS = ("openai", "azure")
DEFAULT_AZURE_API_VERSION = "2024-06-01"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


@dataclass
class LLMResponse:
    """The parts of a chat completion that MapAgent uses."""

    content: str
    tool_calls: List[Any] = field(default_factory=list)
    finish_reason: Optional[str] = None


def image_to_data_url(path: str) -> str:
    """Encode a local image as a base64 data URL with the correct MIME type."""
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def user_message(text: str, image_path: Optional[str] = None) -> Dict[str, Any]:
    """Build a user message, optionally with an attached image (for VLMs)."""
    if not image_path:
        return {"role": "user", "content": text}
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}},
        ],
    }


class LLMClient:
    """Small wrapper around ``openai.OpenAI`` / ``openai.AzureOpenAI``."""

    def __init__(
        self,
        provider: str = "openai",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        api_version: Optional[str] = None,
        max_retries: int = 5,
        timeout: float = 120.0,
        usage: Optional[UsageTracker] = None,
    ) -> None:
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - dependency error
            raise ImportError("The `openai` package is required: pip install -r requirements.txt") from exc

        self._openai = openai
        self.provider = (provider or "openai").lower()
        self.usage = usage or UsageTracker()
        # Parameters that a model rejected once (e.g. reasoning models reject `max_tokens`).
        self._unsupported: Dict[str, set] = {}

        if self.provider == "azure":
            key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
            endpoint = base_url or os.getenv("AZURE_OPENAI_ENDPOINT")
            if not key or not endpoint:
                raise ValueError(
                    "Azure OpenAI needs AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT "
                    "(or --api_key / --base_url)."
                )
            self._client = openai.AzureOpenAI(
                api_key=key,
                azure_endpoint=endpoint,
                api_version=api_version or os.getenv("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION),
                max_retries=max_retries,
                timeout=timeout,
            )
        elif self.provider == "openai":
            key = api_key or os.getenv("OPENAI_API_KEY")
            if not key:
                raise ValueError(
                    "OPENAI_API_KEY is not set. For an OpenAI-compatible server without authentication "
                    "(e.g. a local vLLM server) set it to any non-empty value such as 'EMPTY'."
                )
            self._client = openai.OpenAI(
                api_key=key,
                # explicit default: an empty OPENAI_BASE_URL (e.g. from .env) would otherwise break every request
                base_url=base_url or os.getenv("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL,
                max_retries=max_retries,
                timeout=timeout,
            )
        else:
            raise ValueError(f"Unknown LLM provider {provider!r}; expected one of {PROVIDERS}.")

    # ------------------------------------------------------------------ public API
    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        *,
        temperature: Optional[float] = 0.0,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> LLMResponse:
        """Run one chat completion and record its token usage."""
        kwargs: Dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens:
            kwargs["max_tokens"] = int(max_tokens)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        response = self._create(kwargs)
        usage = getattr(response, "usage", None)
        self.usage.add_llm_call(
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
        )
        if not response.choices:
            return LLMResponse(content="", finish_reason="empty")
        choice = response.choices[0]
        message = choice.message
        return LLMResponse(
            content=(message.content or "").strip(),
            tool_calls=list(message.tool_calls or []),
            finish_reason=choice.finish_reason,
        )

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        system: Optional[str] = None,
        image_path: Optional[str] = None,
        temperature: Optional[float] = 0.0,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Single-turn helper: optional system prompt, one user message, optional image."""
        messages: List[Dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(user_message(prompt, image_path))
        return self.chat(model, messages, temperature=temperature, max_tokens=max_tokens)

    # ------------------------------------------------------------------ internals
    def _create(self, kwargs: Dict[str, Any]):
        model = kwargs["model"]
        for name in self._unsupported.get(model, ()):
            self._adapt(kwargs, name)
        for _ in range(2):
            try:
                return self._client.chat.completions.create(**kwargs)
            except self._openai.BadRequestError as exc:
                message = str(exc).lower()
                if "max_tokens" in message and "max_tokens" in kwargs:
                    rejected = "max_tokens"
                elif "temperature" in message and "temperature" in kwargs:
                    rejected = "temperature"
                else:
                    raise
                self._unsupported.setdefault(model, set()).add(rejected)
                self._adapt(kwargs, rejected)
        return self._client.chat.completions.create(**kwargs)

    @staticmethod
    def _adapt(kwargs: Dict[str, Any], rejected: str) -> None:
        if rejected == "max_tokens" and "max_tokens" in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
        elif rejected == "temperature":
            kwargs.pop("temperature", None)


def is_fatal_llm_error(exc: BaseException) -> bool:
    """Errors that will not go away by retrying (bad key, missing model, no permission)."""
    try:
        import openai
    except ImportError:  # pragma: no cover
        return False
    return isinstance(
        exc,
        (openai.AuthenticationError, openai.PermissionDeniedError, openai.NotFoundError),
    )
