"""Kilo Gateway provider implementation (OpenAI-compatible chat completions).

Kilo Gateway (https://kilo.ai/docs/gateway) is a multi-model routing gateway
- "similar to OpenRouter" per its own docs - reachable at
``https://api.kilo.ai/api/gateway`` with a standard OpenAI-compatible
``/chat/completions`` endpoint and Bearer auth, so it needs no
provider-specific request-shaping quirks beyond the default policy. Model
ids are provider-prefixed, e.g. ``anthropic/claude-sonnet-4.5``.
"""

from __future__ import annotations

from typing import Any

from providers.base import ProviderConfig
from providers.defaults import KILO_DEFAULT_BASE
from providers.transports.openai_chat import (
    OpenAIChatRequestPolicy,
    OpenAIChatTransport,
    build_openai_chat_request_body,
)

_REQUEST_POLICY = OpenAIChatRequestPolicy(provider_name="KILO")


class KiloProvider(OpenAIChatTransport):
    """Kilo Gateway using ``https://api.kilo.ai/api/gateway/chat/completions``."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="KILO",
            base_url=config.base_url or KILO_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_openai_chat_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
            policy=_REQUEST_POLICY,
        )
