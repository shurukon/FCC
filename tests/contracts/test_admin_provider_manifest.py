"""Ensure admin UI manifest exposes every catalog credential/proxy binding."""

from __future__ import annotations

from api.admin_config.manifest import FIELD_BY_KEY
from config.provider_catalog import PROVIDER_CATALOG
from config.settings import Settings


def test_provider_catalog_remote_credentials_in_admin_manifest() -> None:
    missing: list[str] = []
    wrong_attr: list[str] = []

    for provider_id, desc in PROVIDER_CATALOG.items():
        if desc.credential_env is None:
            continue
        if desc.credential_attr is None:
            missing.append(
                f"{provider_id}: credential_env set but credential_attr missing"
            )
            continue
        entry = FIELD_BY_KEY.get(desc.credential_env)
        if entry is None:
            missing.append(
                f"{provider_id}: {desc.credential_env} not in admin FIELD_BY_KEY"
            )
            continue
        if entry.settings_attr != desc.credential_attr:
            wrong_attr.append(
                f"{provider_id}: {desc.credential_env} maps settings_attr="
                f"{entry.settings_attr!r}, catalog expects "
                f"{desc.credential_attr!r}"
            )

    assert not missing and not wrong_attr, "\n".join(missing + wrong_attr)


def test_provider_catalog_local_base_urls_in_admin_manifest() -> None:
    missing_key: list[str] = []
    wrong_attr: list[str] = []

    for provider_id, desc in PROVIDER_CATALOG.items():
        if desc.base_url_attr is None:
            continue
        mf = Settings.model_fields[desc.base_url_attr]
        alias = mf.validation_alias
        if alias is None:
            missing_key.append(
                f"{provider_id}: {desc.base_url_attr} has no validation_alias "
                "(admin manifest expects env-backed base URL)"
            )
            continue
        env_key = str(alias)
        entry = FIELD_BY_KEY.get(env_key)
        if entry is None:
            missing_key.append(
                f"{provider_id}: base URL env {env_key} not in FIELD_BY_KEY"
            )
            continue
        if entry.settings_attr != desc.base_url_attr:
            wrong_attr.append(
                f"{provider_id}: {env_key} maps settings_attr="
                f"{entry.settings_attr!r}, catalog expects {desc.base_url_attr!r}"
            )

    assert not missing_key and not wrong_attr, "\n".join(missing_key + wrong_attr)


def test_provider_catalog_proxy_attrs_in_admin_manifest() -> None:
    missing_key: list[str] = []
    wrong_attr: list[str] = []

    for provider_id, desc in PROVIDER_CATALOG.items():
        if desc.proxy_attr is None:
            continue
        mf = Settings.model_fields[desc.proxy_attr]
        alias = mf.validation_alias
        if alias is None:
            missing_key.append(
                f"{provider_id}: {desc.proxy_attr} has no validation_alias "
                "(admin manifest expects env-backed proxy)"
            )
            continue
        env_key = str(alias)
        entry = FIELD_BY_KEY.get(env_key)
        if entry is None:
            missing_key.append(
                f"{provider_id}: proxy env {env_key} not in FIELD_BY_KEY"
            )
            continue
        if entry.settings_attr != desc.proxy_attr:
            wrong_attr.append(
                f"{provider_id}: {env_key} maps settings_attr="
                f"{entry.settings_attr!r}, catalog expects {desc.proxy_attr!r}"
            )

    assert not missing_key and not wrong_attr, "\n".join(missing_key + wrong_attr)


def test_provider_catalog_display_names_are_admin_status_source() -> None:
    from api.admin_config.status import provider_config_status

    status_by_provider = {
        entry["provider_id"]: entry for entry in provider_config_status()
    }

    assert set(status_by_provider) == set(PROVIDER_CATALOG)
    for provider_id, desc in PROVIDER_CATALOG.items():
        assert status_by_provider[provider_id]["display_name"] == desc.display_name


def test_cloudflare_account_id_is_admin_provider_field() -> None:
    entry = FIELD_BY_KEY["CLOUDFLARE_ACCOUNT_ID"]

    assert entry.settings_attr == "cloudflare_account_id"
    assert entry.section_id == "providers"
    assert entry.secret is False


def test_cloudflare_mismatched_extra_account_pair_warns_in_admin_status() -> None:
    from api.admin_config.status import provider_config_status

    def status_for(state: dict) -> dict:
        base_state = {"CLOUDFLARE_API_TOKEN": {"value": "primary-token"}}
        base_state.update(state)
        by_provider = {
            entry["provider_id"]: entry for entry in provider_config_status(base_state)
        }
        return by_provider["cloudflare"]

    # Token set for account #2 but no matching account id: flagged.
    warned = status_for(
        {"CLOUDFLARE_API_TOKEN_2": {"value": "second-token"}},
    )
    assert warned["status"] == "configured_with_warning"
    assert "#2" in warned["label"]

    # Account id set for account #2 but no matching token: also flagged.
    warned_other_way = status_for(
        {"CLOUDFLARE_ACCOUNT_ID_2": {"value": "second-account"}},
    )
    assert warned_other_way["status"] == "configured_with_warning"

    # Fully paired extra account: healthy, no warning.
    paired = status_for(
        {
            "CLOUDFLARE_API_TOKEN_2": {"value": "second-token"},
            "CLOUDFLARE_ACCOUNT_ID_2": {"value": "second-account"},
        },
    )
    assert paired["status"] == "configured"

    # No extra slots configured at all: just the base single-account case.
    single_account = status_for({})
    assert single_account["status"] == "configured"
