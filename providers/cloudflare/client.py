"""Cloudflare AI REST provider using Anthropic-compatible Messages."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from providers.base import ProviderConfig
from providers.defaults import CLOUDFLARE_AI_REST_ROOT
from providers.exceptions import AuthenticationError
from providers.transports.anthropic_messages import (
    AnthropicMessagesTransport,
    NativeMessagesRequestPolicy,
    build_native_messages_request_body,
)

_ANTHROPIC_VERSION = "2023-06-01"
_REQUEST_POLICY = NativeMessagesRequestPolicy(
    provider_name="CLOUDFLARE",
    extra_body="reject",
    reject_extra_body_message=(
        "Cloudflare native Messages API does not support extra_body on requests."
    ),
)


def cloudflare_ai_base_url(api_root: str | None, account_id: str) -> str:
    """Return the account-scoped Cloudflare AI REST base URL."""

    return f"{_cloudflare_account_api_url(api_root, account_id)}/ai/v1"


def _cloudflare_model_search_url(api_root: str | None, account_id: str) -> str:
    """Return the Cloudflare account model-search endpoint URL."""

    return f"{_cloudflare_account_api_url(api_root, account_id)}/ai/models/search"


def _cloudflare_account_api_url(api_root: str | None, account_id: str) -> str:
    """Return the account-scoped Cloudflare API root URL."""

    stripped_account = account_id.strip()
    if not stripped_account:
        raise AuthenticationError(
            "CLOUDFLARE_ACCOUNT_ID is not set. Add it to your .env file."
        )
    root = (api_root or CLOUDFLARE_AI_REST_ROOT).rstrip("/")
    encoded_account = quote(stripped_account, safe="")
    return f"{root}/accounts/{encoded_account}"


class CloudflareProvider(AnthropicMessagesTransport):
    """Cloudflare account-scoped AI REST provider.

    Cloudflare is the one provider in this catalog whose credential is a
    *pair* - an API token alone isn't enough to build the request URL, the
    account id it belongs to is baked into the path
    (``/accounts/{account_id}/ai/v1/...``). Pooling multiple accounts (not
    just multiple tokens on the same account) therefore has to rotate the
    URL along with the token, not just the Authorization header - see
    ``_stream_request_url`` below and
    ``providers.runtime.key_pool.discover_paired_extra_values``, which
    ``providers.runtime.factory._create_cloudflare`` uses to build
    ``account_id_by_token``.
    """

    def __init__(
        self,
        config: ProviderConfig,
        *,
        account_id: str,
        account_id_by_token: dict[str, str] | None = None,
    ):
        self._api_root = config.base_url or CLOUDFLARE_AI_REST_ROOT
        self._default_account_id = account_id
        # Maps each pooled API token -> the account id it belongs to, so a
        # rotated-in token from account #2 gets account #2's URL, not
        # account #1's. Built once in factory._create_cloudflare from the
        # CLOUDFLARE_ACCOUNT_ID_N / CLOUDFLARE_API_TOKEN_N pairs; falls back
        # to {primary token: primary account} only, for single-account setups.
        self._account_id_by_token = account_id_by_token or {
            config.api_key.strip(): account_id.strip()
        }
        base_url = cloudflare_ai_base_url(self._api_root, account_id)
        self._model_search_url = _cloudflare_model_search_url(
            self._api_root, account_id
        )
        super().__init__(
            config.model_copy(update={"base_url": base_url}),
            provider_name="CLOUDFLARE",
            default_base_url=base_url,
        )

    def _account_id_for_key(self, api_key: str | None) -> str:
        token = self._effective_api_key(api_key)
        return self._account_id_by_token.get(token.strip(), self._default_account_id)

    def _stream_request_url(self, api_key: str | None) -> str:
        """Return the account-scoped absolute URL for whichever pooled
        token this attempt is using - overriding the base class's fixed
        "/messages" relative path, since here the account (and therefore
        the URL) can change per pooled credential, not just the auth header.
        """
        account_id = self._account_id_for_key(api_key)
        return f"{cloudflare_ai_base_url(self._api_root, account_id)}/messages"

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_native_messages_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
            policy=_REQUEST_POLICY,
        )

    def _request_headers(self, api_key: str | None = None) -> dict[str, str]:
        return {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self._effective_api_key(api_key)}",
            "Content-Type": "application/json",
            "anthropic-version": _ANTHROPIC_VERSION,
        }

    def _model_list_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._effective_api_key(None)}"}

    async def _send_model_list_request(self) -> httpx.Response:
        return await self._client.get(
            self._model_search_url,
            params={"format": "openrouter"},
            headers=self._model_list_headers(),
        )
