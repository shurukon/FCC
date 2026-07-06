"""Multi-account API key pooling with sequential-with-cooldown failover.

Lets each provider credential in :mod:`config.provider_catalog` be backed by
more than one account. Slot 1 is the credential's existing env var (e.g.
``NVIDIA_NIM_API_KEY``, resolved by :mod:`config.settings` as usual); slots
2..N are optional numbered siblings (``NVIDIA_NIM_API_KEY_2``,
``NVIDIA_NIM_API_KEY_3``, ...) that are *not* declared as Settings fields, so
adding another account is just adding an env var - no code change, no new
Admin UI field wiring beyond what :mod:`api.admin_config.provider_manifest`
already generates from this same numbering.

Rotation is sequential, not load-balanced: every caller uses the pool's
current key until it fails, at which point that key is put on cooldown and
the shared cursor advances to the next non-cooldown key for *all* callers
going forward (including concurrent in-flight requests, which will pick the
new cursor position up on their own next attempt). A cooled-down key is
retried automatically once its cooldown elapses.

This module intentionally has no dependency on ``providers.base`` or any
concrete provider/transport, so it can be imported from either side of the
provider package (including from inside ``providers/base.py`` itself) with
no risk of a circular import.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from config.env_files import env_file_override, settings_env_files

T = TypeVar("T")

# Slot 1 is the bare credential env var; slots 2..MAX_POOLED_KEYS are that
# name suffixed with "_2" .. "_{MAX_POOLED_KEYS}". Raise this if someone
# genuinely needs more accounts on one provider than this.
MAX_POOLED_KEYS = 8

# How long a key sits out after a failure before it's tried again.
# Auth failures (401/403) get a much longer cooldown than rate limits
# (429/503) since a revoked/invalid key won't fix itself the way a quota
# reset will - there's little point retrying it every minute forever.
DEFAULT_COOLDOWN_SECONDS = 60.0
AUTH_FAILURE_COOLDOWN_SECONDS = 600.0

_AUTH_STATUS_CODES = frozenset({401, 403})

# Status codes that mean "this specific key is the problem" (bad/expired
# key, forbidden, quota/rate exhausted) rather than "the upstream is down" -
# rotating to a sibling key can plausibly fix these. Plain 5xx is
# deliberately excluded: GlobalRateLimiter.execute_with_retry() already
# retries 5xx on the same key with backoff, and a genuine outage isn't
# fixed by switching accounts. 503 is the one exception kept in-scope
# because some gateways (e.g. Kilo) document translating an upstream 402
# Payment Required into a 503 to avoid leaking billing details to the
# client - that *is* a per-account condition worth rotating away from.
FAILOVER_ELIGIBLE_STATUS_CODES = frozenset({401, 403, 429, 503})


def pooled_env_keys(base_env_key: str) -> tuple[str, ...]:
    """Return every env-var name that can contribute to one provider's pool."""

    return (base_env_key,) + tuple(
        f"{base_env_key}_{n}" for n in range(2, MAX_POOLED_KEYS + 1)
    )


def _resolve_pooled_value(env_key: str) -> str | None:
    """Resolve one env var the way ``Settings`` would resolve it.

    Process env wins over dotenv files, which is pydantic-settings' default
    source precedence - this project does not override
    ``settings_customise_sources``, so that default is what actually runs.
    """

    if env_key in os.environ:
        return os.environ[env_key]
    return env_file_override({"env_file": settings_env_files()}, env_key)


def discover_extra_keys(base_env_key: str, *, primary_value: str) -> list[str]:
    """Collect additional pooled keys (slots 2..N) beyond the primary value.

    Blank slots are skipped, so a key can be removed from the middle of the
    numbering without renumbering the rest. Values that duplicate
    ``primary_value`` or an already-collected extra are skipped too, so
    accidentally pasting the same key into two slots doesn't create a
    pointless one-key "pool".
    """

    seen = {primary_value.strip()} if primary_value.strip() else set()
    extras: list[str] = []
    for env_key in pooled_env_keys(base_env_key)[1:]:
        value = _resolve_pooled_value(env_key)
        if not value:
            continue
        stripped = value.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        extras.append(stripped)
    return extras


def discover_paired_extra_values(
    primary_base_env_key: str,
    primary_value: str,
    secondary_base_env_key: str,
    secondary_primary_value: str,
) -> list[tuple[str, str]]:
    """Discover extra slots (2..N) for a two-field paired credential.

    Some providers (Cloudflare: account id + API token) need *both* fields
    to identify one usable account - pooling the token alone the way
    ``discover_extra_keys`` does isn't enough, since a rotated-in token from
    a different account paired with the wrong account id would just fail.

    A slot only counts if both its fields are set; a slot with only one of
    the two (e.g. ``CLOUDFLARE_API_TOKEN_2`` set but not
    ``CLOUDFLARE_ACCOUNT_ID_2``) is skipped - logged as a warning, since
    that's very likely a copy-paste mistake rather than intentional - and
    does not get treated as a usable account. Returns pairs for slots 2..N
    only; the caller is expected to treat (primary_value,
    secondary_primary_value) as slot 1 itself.
    """

    from loguru import logger

    pairs: list[tuple[str, str]] = []
    seen = {(primary_value.strip(), secondary_primary_value.strip())}
    primary_slot_keys = pooled_env_keys(primary_base_env_key)[1:]
    secondary_slot_keys = pooled_env_keys(secondary_base_env_key)[1:]
    for slot_number, (a_env, b_env) in enumerate(
        zip(primary_slot_keys, secondary_slot_keys), start=2
    ):
        a_value = _resolve_pooled_value(a_env)
        b_value = _resolve_pooled_value(b_env)
        a_set = bool(a_value and a_value.strip())
        b_set = bool(b_value and b_value.strip())
        if a_set != b_set:
            logger.warning(
                "KEY_POOL: {} is set without a matching {} - both must be "
                "set together for account slot #{} to be usable; ignoring "
                "this slot until it is.",
                a_env if a_set else b_env,
                b_env if a_set else a_env,
                slot_number,
            )
            continue
        if not a_set:
            continue
        pair = (a_value.strip(), b_value.strip())
        if pair in seen:
            continue
        seen.add(pair)
        pairs.append(pair)
    return pairs


@dataclass
class _KeySlot:
    key: str
    label: str
    cooldown_until: float = 0.0


class ProviderKeyPool:
    """Thread-safe sequential-with-cooldown pool of API keys for one provider."""

    __slots__ = ("_slots", "_cursor", "_lock")

    def __init__(self, keys: list[str]):
        if not keys:
            raise ValueError("ProviderKeyPool requires at least one key")
        self._slots = [
            _KeySlot(key=key, label=f"#{i}") for i, key in enumerate(keys, start=1)
        ]
        self._cursor = 0
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._slots)

    def slot_label(self, key: str) -> str:
        """Return a short human-readable label (``"#2"``) for a pooled key."""

        for slot in self._slots:
            if slot.key == key:
                return slot.label
        return "?"

    def current_key(self) -> str:
        """Return the pool's current key, skipping any still in cooldown."""

        with self._lock:
            now = time.monotonic()
            n = len(self._slots)
            for offset in range(n):
                idx = (self._cursor + offset) % n
                if self._slots[idx].cooldown_until <= now:
                    self._cursor = idx
                    return self._slots[idx].key
            # Every key is cooling down: use whichever recovers soonest
            # rather than hard-failing the request outright.
            soonest = min(range(n), key=lambda i: self._slots[i].cooldown_until)
            self._cursor = soonest
            return self._slots[soonest].key

    def report_failure(self, key: str, *, status_code: int | None = None) -> None:
        """Put a key on cooldown and advance the shared cursor past it."""

        cooldown = (
            AUTH_FAILURE_COOLDOWN_SECONDS
            if status_code in _AUTH_STATUS_CODES
            else DEFAULT_COOLDOWN_SECONDS
        )
        with self._lock:
            for idx, slot in enumerate(self._slots):
                if slot.key == key:
                    slot.cooldown_until = time.monotonic() + cooldown
                    self._cursor = (idx + 1) % len(self._slots)
                    break

    def report_success(self, key: str) -> None:
        """Clear cooldown on a key that just worked."""

        with self._lock:
            for slot in self._slots:
                if slot.key == key:
                    slot.cooldown_until = 0.0
                    break


def build_key_pool(
    base_env_key: str | None, primary_value: str
) -> ProviderKeyPool | None:
    """Build a key pool for one provider credential.

    Returns ``None`` when pooling doesn't apply - no credential env (static
    or local providers), an empty primary value (nothing configured yet), or
    no configured siblings. ``None`` is the exact case that must behave
    identically to how the provider worked before this feature existed, and
    every call site in the transports treats it that way.
    """

    if base_env_key is None or not primary_value.strip():
        return None
    extras = discover_extra_keys(base_env_key, primary_value=primary_value)
    if not extras:
        return None
    return ProviderKeyPool([primary_value.strip(), *extras])


def extract_http_status(error: BaseException) -> int | None:
    """Best-effort HTTP status extraction across openai-SDK/httpx/provider
    exception shapes, via duck typing so this module needn't import any of
    them (and stays a dependency-free leaf module).
    """

    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status
    return None


def is_failover_eligible(error: BaseException) -> bool:
    """Return whether ``error`` should trigger rotation to the next pooled key."""

    return extract_http_status(error) in FAILOVER_ELIGIBLE_STATUS_CODES


async def call_with_key_rotation(
    pool: ProviderKeyPool,
    attempt: Callable[[str], Awaitable[T]],
    *,
    on_rotate: Callable[[str, str], None] | None = None,
) -> T:
    """Call ``attempt(key)``, rotating through ``pool`` on failover-eligible
    errors until one attempt succeeds or every key has been tried.

    ``attempt`` must raise on failure rather than swallowing it into a
    return value - only the raised exception's HTTP status decides whether
    the pool rotates and retries, or the error is re-raised as-is (e.g. a
    400 Bad Request, which no amount of key rotation will fix).

    Callers with no pool configured should skip this helper entirely and
    just call ``attempt(single_key)`` directly - see each transport's
    ``if self._key_pool is None`` branch - so a user who hasn't configured
    extra keys gets the exact unmodified single-key code path.
    """

    tried: set[str] = set()
    last_error: BaseException | None = None
    while len(tried) < len(pool):
        key = pool.current_key()
        if key in tried:
            break
        tried.add(key)
        try:
            result = await attempt(key)
        except Exception as error:  # noqa: BLE001 - status inspected, not swallowed
            if not is_failover_eligible(error):
                raise
            status = extract_http_status(error)
            pool.report_failure(key, status_code=status)
            if on_rotate is not None:
                on_rotate(pool.slot_label(key), type(error).__name__)
            last_error = error
            continue
        pool.report_success(key)
        return result

    assert last_error is not None
    raise last_error
