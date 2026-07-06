"""Provider configuration status for the Admin UI."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from config.provider_catalog import PROVIDER_CATALOG

from .manifest import FIELDS


def provider_config_status(
    state: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return provider configuration status without making network calls."""

    if state is None:
        from .values import load_value_state

        state = load_value_state()
    statuses: list[dict[str, Any]] = []
    for provider_id, descriptor in PROVIDER_CATALOG.items():
        if descriptor.credential_env is None:
            base_url = ""
            if descriptor.base_url_attr is not None:
                base_url = _value_for_settings_attr(state, descriptor.base_url_attr)
            statuses.append(
                {
                    "provider_id": provider_id,
                    "display_name": descriptor.display_name,
                    "kind": "local",
                    "status": "missing_url" if not base_url.strip() else "unknown",
                    "label": "Missing URL" if not base_url.strip() else "Not checked",
                    "base_url": base_url or descriptor.default_base_url or "",
                }
            )
            continue

        value = str(state.get(descriptor.credential_env, {}).get("value", ""))
        configured = bool(value.strip())
        status_entry = {
            "provider_id": provider_id,
            "display_name": descriptor.display_name,
            "kind": "remote",
            "status": "configured" if configured else "missing_key",
            "label": "Configured" if configured else "Missing key",
            "credential_env": descriptor.credential_env,
        }
        if configured and provider_id == "cloudflare":
            mismatched_slots = _cloudflare_mismatched_pair_slots(state)
            if mismatched_slots:
                status_entry["status"] = "configured_with_warning"
                slot_list = ", ".join(f"#{n}" for n in mismatched_slots)
                status_entry["label"] = (
                    f"Configured (account {slot_list}: token/account ID not paired)"
                )
        statuses.append(status_entry)
    return statuses


def _cloudflare_mismatched_pair_slots(
    state: Mapping[str, Mapping[str, Any]],
) -> list[int]:
    """Return extra-account slot numbers where only one of
    CLOUDFLARE_API_TOKEN_N / CLOUDFLARE_ACCOUNT_ID_N is set.

    A token without its account id (or vice versa) can't be used - see
    providers.runtime.key_pool.discover_paired_extra_values, which silently
    skips such a slot rather than guessing. This surfaces the same
    condition in the Admin UI itself instead of leaving it to be noticed
    only in server logs.
    """
    from providers.runtime import pooled_env_keys

    mismatched: list[int] = []
    token_slots = pooled_env_keys("CLOUDFLARE_API_TOKEN")[1:]
    account_slots = pooled_env_keys("CLOUDFLARE_ACCOUNT_ID")[1:]
    for slot_number, (token_key, account_key) in enumerate(
        zip(token_slots, account_slots), start=2
    ):
        token_set = bool(str(state.get(token_key, {}).get("value", "")).strip())
        account_set = bool(str(state.get(account_key, {}).get("value", "")).strip())
        if token_set != account_set:
            mismatched.append(slot_number)
    return mismatched


def _value_for_settings_attr(
    state: Mapping[str, Mapping[str, Any]], settings_attr: str
) -> str:
    for field in FIELDS:
        if field.settings_attr == settings_attr:
            return str(state.get(field.key, {}).get("value", field.default))
    return ""
