"""Model client for interacting with different LLM providers.

Supports multiple providers with a unified interface:
- Anthropic (Claude)
- OpenAI (GPT)
- Google (Gemini)
- DeepSeek
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ModelResponse:
    """Response from an LLM."""
    content: str
    usage: dict
    model: str
    finish_reason: str = ""


class BaseModelClient(ABC):
    """Abstract base class for model clients."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_version: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get(self._get_env_key())
        self.model_version = model_version or self._get_default_version()
        self.base_url = base_url

    @abstractmethod
    def _get_env_key(self) -> str:
        """Get the environment variable key for API key."""
        pass

    @abstractmethod
    def _get_default_version(self) -> str:
        """Get the default model version."""
        pass

    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> ModelResponse:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional provider-specific options

        Returns:
            ModelResponse with the completion
        """
        pass


class AnthropicClient(BaseModelClient):
    """Client for Anthropic Claude models."""

    def _get_env_key(self) -> str:
        return "ANTHROPIC_API_KEY"

    def _get_default_version(self) -> str:
        return "claude-3-opus-20240229"

    async def chat(self, messages: list[dict], **kwargs) -> ModelResponse:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)

        # Convert messages to Anthropic format
        system_msg = ""
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_messages.append(msg)

        response = client.messages.create(
            model=self.model_version,
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.0),
            system=system_msg,
            messages=user_messages,
        )

        return ModelResponse(
            content=response.content[0].text,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            model=self.model_version,
            finish_reason=response.stop_reason or "",
        )


class OpenAIClient(BaseModelClient):
    """Client for OpenAI models (also used for OpenAI-compatible providers)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_version: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        super().__init__(api_key=api_key, model_version=model_version, base_url=base_url)
        if not self.base_url:
            self.base_url = os.environ.get("OPENAI_BASE_URL")

    def _get_env_key(self) -> str:
        return "OPENAI_API_KEY"

    def _get_default_version(self) -> str:
        return "gpt-4o"

    async def chat(self, messages: list[dict], **kwargs) -> ModelResponse:
        import openai

        client_kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        client = openai.AsyncOpenAI(**client_kwargs)

        response = await client.chat.completions.create(
            model=self.model_version,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.0),
        )

        usage = response.usage
        return ModelResponse(
            content=response.choices[0].message.content or "",
            usage={
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(usage, "total_tokens", 0) or 0,
            },
            model=self.model_version,
            finish_reason=response.choices[0].finish_reason or "",
        )


class GoogleClient(BaseModelClient):
    """Client for Google Gemini models."""

    def _get_env_key(self) -> str:
        return "GOOGLE_API_KEY"

    def _get_default_version(self) -> str:
        return "gemini-1.5-pro"

    async def chat(self, messages: list[dict], **kwargs) -> ModelResponse:
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model_version)

        # Convert messages to Gemini format
        chat = model.start_chat(history=[])
        for msg in messages:
            if msg["role"] == "user":
                response = chat.send_message(msg["content"])

        return ModelResponse(
            content=response.text,
            usage={"total_tokens": 0},  # Gemini doesn't always provide token counts
            model=self.model_version,
        )


class DeepSeekClient(OpenAIClient):
    """Client for DeepSeek models (OpenAI-compatible)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_version: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        super().__init__(
            api_key=api_key,
            model_version=model_version,
            base_url=base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        )

    def _get_env_key(self) -> str:
        return "DEEPSEEK_API_KEY"

    def _get_default_version(self) -> str:
        return "deepseek-chat"


class MiMoClient(OpenAIClient):
    """Client for Xiaomi MiMo models (OpenAI-compatible API)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_version: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        super().__init__(
            api_key=api_key,
            model_version=model_version,
            base_url=base_url
            or os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1"),
        )

    def _get_env_key(self) -> str:
        return "MIMO_API_KEY"

    def _get_default_version(self) -> str:
        return "mimo-v2.5-pro"


class ModelClient:
    """Factory for creating model clients."""

    _clients = {
        "anthropic": AnthropicClient,
        "openai": OpenAIClient,
        "google": GoogleClient,
        "deepseek": DeepSeekClient,
        "mimo": MiMoClient,
        "custom": OpenAIClient,
    }

    @classmethod
    def create(
        cls,
        provider: str,
        api_key: Optional[str] = None,
        model_version: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> BaseModelClient:
        """Create a model client for the given provider.

        Args:
            provider: Provider name (anthropic, openai, google, deepseek, mimo, custom)
            api_key: API key (optional, will use env var if not provided)
            model_version: Model version (optional)
            base_url: Optional custom API base URL (OpenAI-compatible providers)

        Returns:
            Configured model client
        """
        if provider not in cls._clients:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(cls._clients.keys())}")

        return cls._clients[provider](
            api_key=api_key,
            model_version=model_version,
            base_url=base_url,
        )
