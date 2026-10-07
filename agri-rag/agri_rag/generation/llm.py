"""LLM provider abstraction. All providers expose the same async streaming interface."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from ..config import Settings


class LLMClient(Protocol):
    def stream(self, system: str, messages: list[dict], max_tokens: int | None = None) -> AsyncIterator[str]: ...

    async def complete(self, system: str, messages: list[dict], max_tokens: int | None = None) -> str: ...


class _BaseLLM:
    async def complete(self, system: str, messages: list[dict], max_tokens: int | None = None) -> str:
        return "".join([t async for t in self.stream(system, messages, max_tokens)])


class AnthropicLLM(_BaseLLM):
    def __init__(self, s: Settings):
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=s.llm_api_key, timeout=s.llm_timeout_s, max_retries=1)
        self._s = s

    async def stream(self, system, messages, max_tokens=None):
        async with self._client.messages.stream(
            model=self._s.llm_model, max_tokens=max_tokens or self._s.llm_max_tokens,
            temperature=self._s.llm_temperature, system=system, messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text


class OpenAICompatLLM(_BaseLLM):
    """Works with Gemini OpenAI-compat, OpenAI, Ollama, vLLM with automatic multi-key rotation & model fallback."""

    def __init__(self, s: Settings):
        self._s = s
        self._rr_idx = 0

    def _get_key_pool(self) -> list[str]:
        import json
        import os
        from pathlib import Path

        keys: list[str] = []
        raw_sources = [
            self._s.llm_api_key or "",
            os.environ.get("AGRI_LLM_API_KEYS", ""),
            os.environ.get("GEMINI_API_KEYS", ""),
            os.environ.get("GEMINI_API_KEY", ""),
            os.environ.get("GEMINI_API_KEY_2", ""),
            os.environ.get("GEMINI_API_KEY_3", ""),
        ]
        for src in raw_sources:
            for part in str(src).split(","):
                k = part.strip()
                if k and k not in keys:
                    keys.append(k)

        # Also check runtime key pool file managed via /dev-panel
        for candidate in [
            Path("/home/azureuser/smart-agriculture-ai/data/gemini_keys.json"),
            Path(__file__).resolve().parent.parent.parent.parent / "data" / "gemini_keys.json",
        ]:
            try:
                if candidate.exists():
                    data = json.loads(candidate.read_text(encoding="utf-8"))
                    for k in data.get("keys", []):
                        ks = str(k).strip()
                        if ks and ks not in keys:
                            keys.append(ks)
            except Exception:
                pass

        return keys or ["not-needed"]

    def _get_model_candidates(self) -> list[str]:
        primary = self._s.llm_model or "gemini-2.5-flash"
        models = [primary]
        if "gemini" in primary.lower():
            for fb in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                if fb not in models:
                    models.append(fb)
        return models

    async def stream(self, system, messages, max_tokens=None):
        from openai import AsyncOpenAI

        keys = self._get_key_pool()
        models = self._get_model_candidates()
        n_keys = len(keys)
        start_idx = self._rr_idx % n_keys
        self._rr_idx += 1

        ordered_keys = [keys[(start_idx + i) % n_keys] for i in range(n_keys)]
        last_err: Exception | None = None

        for api_key in ordered_keys:
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=self._s.llm_base_url,
                timeout=self._s.llm_timeout_s,
                max_retries=1,
            )
            for model_name in models:
                try:
                    resp = await client.chat.completions.create(
                        model=model_name,
                        stream=True,
                        temperature=self._s.llm_temperature,
                        max_tokens=max_tokens or self._s.llm_max_tokens,
                        messages=[{"role": "system", "content": system}, *messages],
                    )
                    async for event in resp:
                        if event.choices and event.choices[0].delta.content:
                            yield event.choices[0].delta.content
                    return
                except Exception as exc:
                    last_err = exc
                    continue

        if last_err:
            raise last_err


class FakeLLM(_BaseLLM):
    """Deterministic stand-in for tests and demos without an API key."""

    def __init__(self, reply: str = "إجابة تجريبية بناءً على المصدر [1]."):
        self.reply = reply
        self.calls: list[dict] = []

    async def stream(self, system, messages, max_tokens=None):
        self.calls.append({"system": system, "messages": messages})
        for word in self.reply.split(" "):
            yield word + " "


def get_llm(s: Settings) -> LLMClient:
    if s.llm_provider == "anthropic":
        return AnthropicLLM(s)
    if s.llm_provider == "openai_compat":
        return OpenAICompatLLM(s)
    if s.llm_provider == "fake":
        return FakeLLM()
    raise ValueError(f"Unknown llm_provider: {s.llm_provider}")
