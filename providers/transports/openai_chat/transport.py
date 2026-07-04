"""OpenAI-compatible chat transport base."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
from openai import AsyncOpenAI

from core.anthropic.streaming import AnthropicStreamLedger
from providers.base import BaseProvider, ProviderConfig
from providers.error_mapping import (
    extract_provider_error_detail,
    map_error,
    user_visible_message_for_mapped_provider_error,
)
from providers.model_listing import extract_openai_model_ids
from providers.rate_limit import GlobalRateLimiter

from .stream import OpenAIChatStreamAdapter


class OpenAIChatTransport(BaseProvider):
    """Base for OpenAI-compatible ``/chat/completions`` adapters."""

    def __init__(
        self,
        config: ProviderConfig,
        *,
        provider_name: str,
        base_url: str,
        api_key: str,
    ):
        super().__init__(config)
        self._provider_name = provider_name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        # Optional providers.runtime.key_pool.ProviderKeyPool for multi-account
        # credentials; None means "single key", the untouched original behavior.
        self._key_pool = config.key_pool
        self._global_rate_limiter = GlobalRateLimiter.get_scoped_instance(
            provider_name.lower(),
            rate_limit=config.rate_limit,
            rate_window=config.rate_window,
            max_concurrency=config.max_concurrency,
        )
        self._http_client: httpx.AsyncClient | None = None
        if config.proxy:
            self._http_client = httpx.AsyncClient(
                proxy=config.proxy,
                timeout=httpx.Timeout(
                    config.http_read_timeout,
                    connect=config.http_connect_timeout,
                    read=config.http_read_timeout,
                    write=config.http_write_timeout,
                ),
            )
        # One AsyncOpenAI client per pooled key, built lazily on first use and
        # cached thereafter; every client shares the same proxy-configured
        # httpx client (if any), so pooling costs no extra connection pools
        # beyond what a proxy setup already needed. Seeding this now with the
        # primary key means self._client below is always the exact same
        # object a single-key setup would have built.
        self._clients_by_key: dict[str, AsyncOpenAI] = {}
        self._client = self._client_for_key(self._api_key)

    def _client_for_key(self, key: str) -> AsyncOpenAI:
        """Return the cached (or lazily built) OpenAI client for a pooled key."""
        cached = self._clients_by_key.get(key)
        if cached is not None:
            return cached
        config = self._config
        client = AsyncOpenAI(
            api_key=key,
            base_url=self._base_url,
            max_retries=0,
            timeout=httpx.Timeout(
                config.http_read_timeout,
                connect=config.http_connect_timeout,
                read=config.http_read_timeout,
                write=config.http_write_timeout,
            ),
            http_client=self._http_client,
        )
        self._clients_by_key[key] = client
        return client

    def _log_key_rotation(self, slot_label: str, error_type: str) -> None:
        from loguru import logger

        logger.warning(
            "{}_KEY_POOL: rotating away from key {} after {}",
            self._provider_name,
            slot_label,
            error_type,
        )

    async def cleanup(self) -> None:
        """Release HTTP client resources for every pooled key's client.

        Closes ``self._client`` first (covering both normal operation, where
        it's one of the cached clients below, and tests that monkeypatch it
        directly to a mock), then closes any other cached per-key clients
        exactly once each.
        """
        closed_ids: set[int] = set()
        client = getattr(self, "_client", None)
        if client is not None:
            await client.close()
            closed_ids.add(id(client))
        for cached_client in self._clients_by_key.values():
            if id(cached_client) in closed_ids:
                continue
            await cached_client.close()
            closed_ids.add(id(cached_client))
        if self._http_client is not None:
            await self._http_client.aclose()

    async def list_model_ids(self) -> frozenset[str]:
        """Return model ids from the provider's OpenAI-compatible models endpoint."""
        key = self._key_pool.current_key() if self._key_pool is not None else self._api_key
        payload = await self._client_for_key(key).models.list()
        return extract_openai_model_ids(payload, provider_name=self._provider_name)

    @abstractmethod
    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        """Build request body. Must be implemented by subclasses."""

    def _handle_extra_reasoning(
        self, delta: Any, ledger: AnthropicStreamLedger, *, thinking_enabled: bool
    ) -> Iterator[str]:
        """Hook for provider-specific reasoning."""
        return iter(())

    def _get_retry_request_body(self, error: Exception, body: dict) -> dict | None:
        """Return a modified request body for one retry, or None."""
        return None

    def _prepare_create_body(self, body: dict[str, Any]) -> dict[str, Any]:
        """Return the body passed to the upstream OpenAI-compatible client."""
        return body

    def _record_tool_call_extra_content(
        self, tool_call_id: str, extra_content: dict[str, Any]
    ) -> None:
        """Hook for providers that must replay OpenAI tool-call metadata later."""

    def _tool_argument_aliases(self, body: dict[str, Any]) -> dict[str, dict[str, str]]:
        """Return provider-specific per-tool argument aliases for this request."""
        return {}

    def _anthropic_usage_fields(self, usage_info: Any) -> dict[str, int]:
        """Return provider-specific Anthropic usage fields for final SSE usage."""
        return {}

    async def _create_stream(self, body: dict) -> tuple[Any, dict]:
        """Create a streaming chat completion, optionally retrying once.

        When a key pool is configured, each attempt below transparently
        rotates through pooled keys on a failover-eligible error (bad/expired
        key, exhausted quota) before this method's own caller ever sees a
        failure - see ``key_pool.call_with_key_rotation``. Without a pool
        this is the original single-client behavior, unchanged.
        """
        from providers.runtime.key_pool import call_with_key_rotation

        create_body = self._prepare_create_body(body)

        async def attempt(key: str) -> Any:
            return await self._global_rate_limiter.execute_with_retry(
                self._client_for_key(key).chat.completions.create,
                **create_body,
                stream=True,
            )

        try:
            if self._key_pool is not None:
                stream = await call_with_key_rotation(
                    self._key_pool, attempt, on_rotate=self._log_key_rotation
                )
            else:
                stream = await attempt(self._api_key)
            return stream, body
        except Exception as error:
            retry_body = self._get_retry_request_body(error, body)
            if retry_body is None:
                raise

            create_retry_body = self._prepare_create_body(retry_body)

            async def retry_attempt(key: str) -> Any:
                return await self._global_rate_limiter.execute_with_retry(
                    self._client_for_key(key).chat.completions.create,
                    **create_retry_body,
                    stream=True,
                )

            if self._key_pool is not None:
                stream = await call_with_key_rotation(
                    self._key_pool, retry_attempt, on_rotate=self._log_key_rotation
                )
            else:
                stream = await retry_attempt(self._api_key)
            return stream, retry_body

    def _openai_error_message(self, error: Exception, request_id: str | None) -> str:
        mapped_error = map_error(error, rate_limiter=self._global_rate_limiter)
        return user_visible_message_for_mapped_provider_error(
            mapped_error,
            provider_name=self._provider_name,
            read_timeout_s=self._config.http_read_timeout,
            detail=extract_provider_error_detail(error),
            request_id=request_id,
        )

    async def stream_response(
        self,
        request: Any,
        input_tokens: int = 0,
        *,
        request_id: str | None = None,
        thinking_enabled: bool | None = None,
    ) -> AsyncIterator[str]:
        """Stream response in Anthropic SSE format."""
        adapter = OpenAIChatStreamAdapter(
            self,
            request=request,
            input_tokens=input_tokens,
            request_id=request_id,
            thinking_enabled=thinking_enabled,
        )
        async for event in adapter.run():
            yield event
