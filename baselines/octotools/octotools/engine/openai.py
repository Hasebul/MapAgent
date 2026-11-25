# Reference: https://github.com/zou-group/textgrad/blob/main/textgrad/engine/openai.py
"""OpenAI-compatible chat engine used by the OctoTools baseline.

Configuration comes from the same environment variables as MapAgent:
  * ``MAPAGENT_LLM_PROVIDER``: ``openai`` (default) or ``azure``
  * ``OPENAI_API_KEY`` / ``OPENAI_BASE_URL`` (OpenAI, OpenRouter, vLLM, ...)
  * ``AZURE_OPENAI_API_KEY`` / ``AZURE_OPENAI_ENDPOINT`` / ``AZURE_OPENAI_API_VERSION``

Structured outputs (``response_format`` = a pydantic model) use the native ``parse`` endpoint when the model
supports it and fall back to JSON-in-text parsing otherwise (e.g. GPT-3.5-Turbo or Qwen-2.5-72B).
"""

try:
    import openai
    from openai import AzureOpenAI, OpenAI
except ImportError:  # pragma: no cover
    raise ImportError("Please install the openai package: pip install -r requirements.txt")

import base64
import json
import os
import re
import threading
from typing import List, Union

from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_random_exponential

from .base import CachedEngine, EngineLM

load_dotenv()


class _Usage:
    """Process-wide LLM usage counters (read by solve.py for the cost analysis)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        self.llm_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def add(self, response):
        usage = getattr(response, "usage", None)
        with self._lock:
            self.llm_calls += 1
            self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0


USAGE = _Usage()


def _make_client():
    provider = os.getenv("MAPAGENT_LLM_PROVIDER", "openai").lower()
    if provider == "azure":
        return AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
            max_retries=5,
        )
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Please set the OPENAI_API_KEY environment variable (any value for a local vLLM server).")
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1",
                  max_retries=5)


def _json_block(text: str) -> str:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        raise ValueError(f"No JSON object in the model output: {text[:200]!r}")
    return match.group(0)


class ChatOpenAI(EngineLM, CachedEngine):
    DEFAULT_SYSTEM_PROMPT = "You are a helpful, creative, and smart assistant."

    def __init__(self, model_string="gpt-4o", system_prompt=DEFAULT_SYSTEM_PROMPT, is_multimodal: bool = False,
                 enable_cache: bool = False, **kwargs):
        if enable_cache:
            import platformdirs

            root = platformdirs.user_cache_dir("octotools")
            cache_path = os.path.join(root, f"cache_openai_{model_string.replace('/', '_')}.db")
            super().__init__(cache_path=cache_path)
        self.system_prompt = system_prompt
        self.client = _make_client()
        self.model_string = model_string
        self.is_multimodal = is_multimodal
        self.enable_cache = enable_cache
        self._structured_ok = True  # flipped off when the model rejects native structured outputs

    @retry(wait=wait_random_exponential(min=1, max=5), stop=stop_after_attempt(3), reraise=True)
    def _create(self, **kwargs):
        response = self.client.chat.completions.create(**kwargs)
        USAGE.add(response)
        return response

    def _parse_structured(self, messages, response_format, **kwargs):
        """Pydantic-typed output: native structured outputs if possible, JSON-in-text otherwise."""
        if self._structured_ok:
            parse = getattr(self.client.chat.completions, "parse", None) or self.client.beta.chat.completions.parse
            try:
                response = parse(model=self.model_string, messages=messages, response_format=response_format, **kwargs)
                USAGE.add(response)
                parsed = response.choices[0].message.parsed
                if parsed is not None:
                    return parsed
            except openai.BadRequestError:
                self._structured_ok = False
        fields = ", ".join(f'"{name}"' for name in response_format.model_fields)
        instruction = f"\n\nRespond only with a JSON object with exactly these keys: {fields}."
        messages = [dict(m) for m in messages]
        if isinstance(messages[-1]["content"], str):
            messages[-1]["content"] += instruction
        else:
            messages[-1]["content"] = list(messages[-1]["content"]) + [{"type": "text", "text": instruction}]
        response = self._create(model=self.model_string, messages=messages, **kwargs)
        return response_format.model_validate(json.loads(_json_block(response.choices[0].message.content)))

    def generate(self, content: Union[str, List[Union[str, bytes]]], system_prompt=None, **kwargs):
        try:
            if isinstance(content, str):
                return self._generate_text(content, system_prompt=system_prompt, **kwargs)
            if isinstance(content, list):
                if not self.is_multimodal:
                    raise NotImplementedError("This engine was created with is_multimodal=False.")
                return self._generate_multimodal(content, system_prompt=system_prompt, **kwargs)
            raise TypeError(f"Unsupported content type: {type(content)}")
        except (openai.AuthenticationError, openai.PermissionDeniedError, openai.NotFoundError):
            raise  # configuration errors must stop the run
        except Exception as e:  # noqa: BLE001 - the OctoTools loop handles error dicts
            print(f"Error in generate method ({type(e).__name__}): {e}")
            return {"error": type(e).__name__, "message": str(e)}

    def _messages(self, user_content, system_prompt):
        return [
            {"role": "system", "content": system_prompt or self.system_prompt},
            {"role": "user", "content": user_content},
        ]

    def _generate_text(self, prompt, system_prompt=None, temperature=0, max_tokens=4000, top_p=0.99, response_format=None):
        sys_prompt = system_prompt or self.system_prompt
        if self.enable_cache:
            cached = self._check_cache(sys_prompt + prompt)
            if cached is not None:
                return cached
        params = dict(temperature=temperature, max_tokens=max_tokens, top_p=top_p)
        messages = self._messages(prompt, sys_prompt)
        if response_format is not None:
            response = self._parse_structured(messages, response_format, **params)
        else:
            response = self._create(model=self.model_string, messages=messages, **params).choices[0].message.content
        if self.enable_cache:
            self._save_cache(sys_prompt + prompt, response)
        return response

    def __call__(self, prompt, **kwargs):
        return self.generate(prompt, **kwargs)

    @staticmethod
    def _format_content(content: List[Union[str, bytes]]) -> List[dict]:
        formatted = []
        for item in content:
            if isinstance(item, bytes):
                mime = "image/png" if item[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
                encoded = base64.b64encode(item).decode("utf-8")
                formatted.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}})
            elif isinstance(item, str):
                formatted.append({"type": "text", "text": item})
            else:
                raise ValueError(f"Unsupported input type: {type(item)}")
        return formatted

    def _generate_multimodal(self, content, system_prompt=None, temperature=0, max_tokens=4000, top_p=0.99,
                             response_format=None):
        sys_prompt = system_prompt or self.system_prompt
        formatted = self._format_content(content)
        cache_key = sys_prompt + json.dumps(formatted)
        if self.enable_cache:
            cached = self._check_cache(cache_key)
            if cached is not None:
                return cached
        params = dict(temperature=temperature, max_tokens=max_tokens, top_p=top_p)
        messages = self._messages(formatted, sys_prompt)
        if response_format is not None:
            response = self._parse_structured(messages, response_format, **params)
        else:
            response = self._create(model=self.model_string, messages=messages, **params).choices[0].message.content
        if self.enable_cache:
            self._save_cache(cache_key, response)
        return response
