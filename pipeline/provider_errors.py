from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, Optional

import requests


@dataclass
class ProviderFailure(RuntimeError):
    provider: str
    code: str
    user_message: str
    detail: Any = None
    retryable: bool = False

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.user_message)

    def to_error_detail(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "code": self.code,
            "retryable": self.retryable,
            "detail": self.detail,
        }


def normalize_provider_exception(
    provider: str,
    exc: Exception,
    *,
    operation: str,
    config_message: str,
    timeout_message: str,
    auth_message: str,
    network_message: str,
    default_message: str,
) -> ProviderFailure:
    if isinstance(exc, ProviderFailure):
        return exc

    lowered_name = type(exc).__name__.lower()
    lowered_text = str(exc).lower()
    provider_prefix = provider.upper()

    if _is_timeout_error(exc, lowered_name, lowered_text):
        return ProviderFailure(
            provider=provider,
            code=f"{provider_prefix}_TIMEOUT",
            user_message=timeout_message,
            detail={"operation": operation, "exception": repr(exc)},
            retryable=True,
        )

    if _is_auth_error(lowered_name, lowered_text):
        return ProviderFailure(
            provider=provider,
            code=f"{provider_prefix}_AUTH_FAILED",
            user_message=auth_message,
            detail={"operation": operation, "exception": repr(exc)},
            retryable=False,
        )

    if _is_config_error(exc, lowered_name, lowered_text):
        return ProviderFailure(
            provider=provider,
            code=f"{provider_prefix}_NOT_CONFIGURED",
            user_message=config_message,
            detail={"operation": operation, "exception": repr(exc)},
            retryable=False,
        )

    if _is_network_error(exc, lowered_name, lowered_text):
        return ProviderFailure(
            provider=provider,
            code=f"{provider_prefix}_UNAVAILABLE",
            user_message=network_message,
            detail={"operation": operation, "exception": repr(exc)},
            retryable=True,
        )

    return ProviderFailure(
        provider=provider,
        code=f"{provider_prefix}_FAILED",
        user_message=default_message,
        detail={"operation": operation, "exception": repr(exc)},
        retryable=False,
    )


def _is_timeout_error(exc: Exception, lowered_name: str, lowered_text: str) -> bool:
    return isinstance(exc, (TimeoutError, subprocess.TimeoutExpired, requests.Timeout)) or (
        "timeout" in lowered_name or "timed out" in lowered_text
    )


def _is_network_error(exc: Exception, lowered_name: str, lowered_text: str) -> bool:
    return isinstance(exc, requests.RequestException) or any(
        marker in lowered_name or marker in lowered_text
        for marker in ("connection", "connecterror", "apiconnection", "dns", "network")
    )


def _is_auth_error(lowered_name: str, lowered_text: str) -> bool:
    return any(
        marker in lowered_name or marker in lowered_text
        for marker in ("auth", "permission", "forbidden", "unauthorized", "invalid_grant", "credential")
    )


def _is_config_error(exc: Exception, lowered_name: str, lowered_text: str) -> bool:
    if isinstance(exc, (FileNotFoundError, ModuleNotFoundError, KeyError)):
        return True
    return any(
        marker in lowered_name or marker in lowered_text
        for marker in ("config", "credential", "not configured", "missing file", "missing")
    )
