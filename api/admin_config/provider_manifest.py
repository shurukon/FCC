"""Catalog-derived Admin UI provider fields."""

from __future__ import annotations

from typing import Any

from config.provider_catalog import PROVIDER_CATALOG
from config.settings import Settings

_PROVIDER_FIELD_OVERRIDES: dict[str, dict[str, Any]] = {
    "NVIDIA_NIM_API_KEY": {
        "label": "NVIDIA NIM API Key",
        "description": "Used by NVIDIA NIM chat and optional NIM voice transcription.",
    },
    "MISTRAL_API_KEY": {
        "label": "Mistral API Key",
        "description": (
            "Mistral La Plateforme (api.mistral.ai); Experiment plan is free tier with rate limits."
        ),
    },
    "CODESTRAL_API_KEY": {
        "label": "Codestral API Key",
        "description": (
            "Mistral Codestral endpoint (codestral.mistral.ai); distinct from Mistral "
            "La Plateforme ``MISTRAL_API_KEY``. See Mistral docs for coding/FIM domains."
        ),
    },
    "OPENCODE_API_KEY": {
        "label": "OpenCode API Key",
        "description": (
            "OpenCode Zen curated gateway (opencode.ai/zen/v1) and OpenCode Go subscription "
            "gateway (opencode.ai/zen/go/v1); single key from opencode.ai/auth."
        ),
    },
    "ZAI_API_KEY": {
        "label": "Z.ai API Key",
        "description": "Z.ai Coding Plan API key.",
    },
    "FIREWORKS_API_KEY": {
        "label": "Fireworks API Key",
        "description": "Fireworks AI inference API key.",
    },
    "CLOUDFLARE_API_TOKEN": {
        "label": "Cloudflare API Token",
        "description": (
            "Cloudflare API token for account-scoped AI REST requests. "
            "Use with CLOUDFLARE_ACCOUNT_ID."
        ),
    },
    "GEMINI_API_KEY": {
        "label": "Gemini API Key",
        "description": (
            "Google AI Studio Gemini API key (Google AI Studio / Gemini API "
            "[OpenAI-compatible](https://ai.google.dev/gemini-api/docs/openai)); "
            "free tier has per-model rate limits and data may be used for improvement "
            "outside the UK/CH/EEA/EU."
        ),
    },
    "GROQ_API_KEY": {
        "label": "Groq API Key",
        "description": (
            "GroqCloud OpenAI-compatible API key ([console.groq.com/keys]("
            "https://console.groq.com/keys)); see Groq "
            "[OpenAI compatibility docs](https://console.groq.com/docs/openai)."
        ),
    },
    "CEREBRAS_API_KEY": {
        "label": "Cerebras API Key",
        "description": (
            "Cerebras Inference API key (create in [Cloud Console](https://cloud.cerebras.ai)); "
            "see [Quickstart](https://inference-docs.cerebras.ai/quickstart) and "
            "[OpenAI compatibility](https://inference-docs.cerebras.ai/resources/openai)."
        ),
    },
    "KILO_API_KEY": {
        "label": "Kilo Gateway API Key",
        "description": (
            "Kilo Gateway (kilo.ai/docs/gateway) OpenAI-compatible multi-model routing "
            "API; free-tier/no-card-required models are available alongside paid routing."
        ),
    },
}

# Extra pooled-account slots shown directly in the Admin UI (slot 1 is the
# field above; this adds slots 2..N). providers.runtime.key_pool actually
# discovers up to key_pool.MAX_POOLED_KEYS slots at runtime regardless of
# how many the UI pre-renders - anything beyond this can still be added by
# hand to the managed .env file using the same "..._5", "..._6" naming.
_UI_POOLED_KEY_SLOTS = 4


def provider_field_specs() -> tuple[dict[str, Any], ...]:
    """Return provider fields generated from the provider catalog."""

    return (
        *_credential_field_specs(),
        *_pooled_credential_field_specs(),
        *_cloudflare_account_field_specs(),
        *_local_base_url_field_specs(),
        *_proxy_field_specs(),
    )


def _credential_field_specs() -> tuple[dict[str, Any], ...]:
    specs: list[dict[str, Any]] = []
    seen_env_keys: set[str] = set()
    for descriptor in PROVIDER_CATALOG.values():
        if descriptor.credential_env is None:
            continue
        if descriptor.credential_env in seen_env_keys:
            continue
        seen_env_keys.add(descriptor.credential_env)
        spec = {
            "key": descriptor.credential_env,
            "label": f"{descriptor.display_name} API Key",
            "section_id": "providers",
            "field_type": "secret",
            "settings_attr": descriptor.credential_attr,
            "secret": True,
        }
        spec.update(_PROVIDER_FIELD_OVERRIDES.get(descriptor.credential_env, {}))
        specs.append(spec)
    return tuple(specs)


def _pooled_credential_field_specs() -> tuple[dict[str, Any], ...]:
    """Return optional slot-2..N key fields for multi-account pooling.

    These mirror ``_credential_field_specs()`` one-for-one but for the
    numbered sibling env vars (``..._2``, ``..._3``, ...) that
    ``providers.runtime.key_pool`` discovers and rotates through
    automatically - see that module for the failover behavior these feed
    into. They deliberately have no ``settings_attr``: Settings only ever
    resolves slot 1, so these are validated/persisted purely as plain
    env-file entries (``field_input_key`` already skips fields with no
    ``settings_attr`` when building the Settings validation preview).
    """
    from providers.runtime import pooled_env_keys

    specs: list[dict[str, Any]] = []
    seen_env_keys: set[str] = set()
    for descriptor in PROVIDER_CATALOG.values():
        if descriptor.credential_env is None:
            continue
        if descriptor.credential_env in seen_env_keys:
            continue
        seen_env_keys.add(descriptor.credential_env)
        base_label = _PROVIDER_FIELD_OVERRIDES.get(
            descriptor.credential_env, {}
        ).get("label", f"{descriptor.display_name} API Key")
        extra_slots = pooled_env_keys(descriptor.credential_env)[1:_UI_POOLED_KEY_SLOTS]
        for slot, env_key in enumerate(extra_slots, start=2):
            specs.append(
                {
                    "key": env_key,
                    "label": f"{base_label} #{slot} (extra account)",
                    "section_id": "providers",
                    "field_type": "secret",
                    "secret": True,
                    "advanced": True,
                    "description": (
                        "Optional additional account for this provider. Used "
                        "automatically as a fallback when earlier keys hit a "
                        "rate limit or are rejected - leave blank if you only "
                        "have one account."
                    ),
                }
            )
    return tuple(specs)


def _local_base_url_field_specs() -> tuple[dict[str, Any], ...]:
    specs: list[dict[str, Any]] = []
    for descriptor in PROVIDER_CATALOG.values():
        if descriptor.base_url_attr is None:
            continue
        specs.append(
            {
                "key": _settings_env_key(descriptor.base_url_attr),
                "label": f"{descriptor.display_name} Base URL",
                "section_id": "providers",
                "settings_attr": descriptor.base_url_attr,
                "default": descriptor.default_base_url or "",
            }
        )
    return tuple(specs)


def _cloudflare_account_field_specs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "key": "CLOUDFLARE_ACCOUNT_ID",
            "label": "Cloudflare Account ID",
            "section_id": "providers",
            "settings_attr": "cloudflare_account_id",
            "description": (
                "Cloudflare account ID used to build the /accounts/{id}/ai/v1 endpoint."
            ),
        },
    )


def _proxy_field_specs() -> tuple[dict[str, Any], ...]:
    specs: list[dict[str, Any]] = []
    for descriptor in PROVIDER_CATALOG.values():
        if descriptor.proxy_attr is None:
            continue
        specs.append(
            {
                "key": _settings_env_key(descriptor.proxy_attr),
                "label": f"{descriptor.display_name} Proxy",
                "section_id": "providers",
                "field_type": "secret",
                "settings_attr": descriptor.proxy_attr,
                "secret": True,
                "advanced": True,
            }
        )
    return tuple(specs)


def _settings_env_key(settings_attr: str) -> str:
    model_field = Settings.model_fields[settings_attr]
    alias = model_field.validation_alias
    return str(alias) if alias is not None else settings_attr
