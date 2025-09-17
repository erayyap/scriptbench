"""OpenAI-powered model wrapper for the Mini-SWE agent."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any

from openai import OpenAI


@dataclass
class OpenAIChatModelConfig:
    model_name: str
    temperature: float | None = None
    max_output_tokens: int | None = None
    base_url: str | None = None
    api_key: str | None = None
    organization: str | None = None
    client_kwargs: dict[str, Any] = field(default_factory=dict)
    request_kwargs: dict[str, Any] = field(default_factory=dict)


class OpenAIChatModel:
    """Minimal wrapper around the official OpenAI SDK for chat completions."""

    def __init__(self, **kwargs):
        self.config = OpenAIChatModelConfig(**kwargs)
        self.cost = 0.0  # Pricing is model-dependent; leave at zero for now.
        self.n_calls = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

        client_kwargs = dict(self.config.client_kwargs)
        if self.config.base_url:
            client_kwargs.setdefault("base_url", self.config.base_url)
        if self.config.organization:
            client_kwargs.setdefault("organization", self.config.organization)

        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
        if api_key:
            client_kwargs.setdefault("api_key", api_key)

        client_kwargs.setdefault("max_retries", 3)

        self._client = OpenAI(**client_kwargs)

    def query(self, messages: list[dict[str, str]], **kwargs) -> dict:
        request_kwargs = {
            "model": self.config.model_name,
            "messages": messages,
        }
        if self.config.temperature is not None:
            request_kwargs.setdefault("temperature", self.config.temperature)
        if self.config.max_output_tokens is not None:
            request_kwargs.setdefault("max_completion_tokens", self.config.max_output_tokens)

        request_kwargs |= self.config.request_kwargs
        request_kwargs |= kwargs

        response = self._client.chat.completions.create(**request_kwargs)

        self.n_calls += 1
        if response.usage:  # pragma: no branch - simple attribute check
            self.total_prompt_tokens += response.usage.prompt_tokens or 0
            self.total_completion_tokens += response.usage.completion_tokens or 0

        message = response.choices[0].message
        content = message.content or ""
        return {
            "content": content,
            "extra": {
                "response": response.model_dump(),
            },
        }

    def get_template_vars(self) -> dict[str, Any]:
        return asdict(self.config) | {
            "n_model_calls": self.n_calls,
            "model_cost": self.cost,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
        }

