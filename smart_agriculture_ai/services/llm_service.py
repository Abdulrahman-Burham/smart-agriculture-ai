"""Thin abstraction around a pluggable LLM provider."""

from __future__ import annotations

from typing import Any


class LLMService:
    """Lightweight adapter that can be replaced by a hosted LLM provider later."""

    def __init__(self, provider: str = "openai", model_name: str = "gpt-4o-mini", api_key: str | None = None):
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key

    def generate_text(self, prompt: str) -> str:
        """Generate text from a prompt using the configured LLM provider."""

        if self.api_key:
            return f"[mock llm response for {self.model_name}]\n{prompt[:200]}"
        return "LLM provider not configured. Please set API keys in the environment."

    def rewrite_query(self, query: str) -> str:
        """Perform a lightweight query rewrite via the configured LLM provider."""

        return self.generate_text(f"Rewrite this agricultural query into canonical Egyptian Arabic:\n{query}")


def build_llm_service(provider: str, model_name: str, api_key: str | None = None) -> LLMService:
    """Factory for constructing the configured LLM service."""

    return LLMService(provider=provider, model_name=model_name, api_key=api_key)
