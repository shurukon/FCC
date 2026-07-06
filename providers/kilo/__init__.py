"""Kilo Gateway (OpenAI-compat) adapter."""

from providers.defaults import KILO_DEFAULT_BASE

from .client import KiloProvider

__all__ = ["KILO_DEFAULT_BASE", "KiloProvider"]
