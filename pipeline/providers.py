from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Dict

from ai_editor.ai_client import get_provider_readiness
from ai_editor.google_auth import (
    GoogleCredentialError,
    resolve_drive_oauth_client_secret_path,
    resolve_drive_token_path,
    resolve_google_credentials_path,
    validate_service_account_json,
)


@dataclass
class ProviderStatus:
    name: str
    required: bool
    configured: bool
    ready: bool
    code: str = ""
    message: str = ""
    detail: Any = None

    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)


def get_provider_health(
    *,
    require_llm: bool,
    require_render: bool,
    require_drive: bool,
    preferred_provider: str | None = None,
) -> Dict[str, Any]:
    llm_status = _build_llm_status(required=require_llm, preferred_provider=preferred_provider)
    render_status = _build_render_status(required=require_render)
    drive_status = _build_drive_status(required=require_drive)
    providers = {
        "model_provider": llm_status.to_payload(),
        "render_provider": render_status.to_payload(),
        "drive_storage": drive_status.to_payload(),
    }
    ready = all((not item["required"]) or item["ready"] for item in providers.values())
    return {"ready": ready, "providers": providers}


def summarize_missing_required_providers(provider_health: Dict[str, Any]) -> list[Dict[str, Any]]:
    providers = provider_health.get("providers") or {}
    return [
        payload
        for payload in providers.values()
        if payload.get("required") and not payload.get("ready")
    ]


def _build_llm_status(*, required: bool, preferred_provider: str | None) -> ProviderStatus:
    readiness = get_provider_readiness(preferred_provider=preferred_provider)
    active_provider = readiness.get("active_provider") or ""
    if readiness.get("ready"):
        return ProviderStatus(
            name="model_provider",
            required=required,
            configured=True,
            ready=True,
            message=f"AI controller provider ready ({active_provider or 'configured'}).",
            detail=readiness,
        )
    return ProviderStatus(
        name="model_provider",
        required=required,
        configured=False,
        ready=False,
        code="MODEL_PROVIDER_NOT_CONFIGURED",
        message="Set HF_API_KEY, OPENROUTER_API_KEY, or GROQ to enable AI controller decisions.",
        detail=readiness,
    )


def _build_render_status(*, required: bool) -> ProviderStatus:
    shotstack_key = str(os.getenv("SHOTSTACK_KEY", "") or "").strip()
    if shotstack_key:
        return ProviderStatus(
            name="render_provider",
            required=required,
            configured=True,
            ready=True,
            message="Render provider is configured.",
        )
    return ProviderStatus(
        name="render_provider",
        required=required,
        configured=False,
        ready=False,
        code="RENDER_PROVIDER_NOT_CONFIGURED",
        message="Set SHOTSTACK_KEY to enable final renders.",
    )


def _build_drive_status(*, required: bool) -> ProviderStatus:
    mode = str(os.getenv("DRIVE_AUTH_MODE", "oauth_user") or "oauth_user").strip().lower()
    try:
        if mode in {"service_account", "service-account", "sa"}:
            credentials_path = resolve_google_credentials_path()
            validate_service_account_json(credentials_path)
            return ProviderStatus(
                name="drive_storage",
                required=required,
                configured=True,
                ready=True,
                message="Drive storage is configured via service account.",
                detail={"mode": mode, "credentials_path": str(credentials_path)},
            )

        if mode in {"oauth", "oauth_user", "user"}:
            client_secret_path = resolve_drive_oauth_client_secret_path()
            token_path = resolve_drive_token_path()
            connected = token_path.exists()
            return ProviderStatus(
                name="drive_storage",
                required=required,
                configured=True,
                ready=connected,
                code="" if connected else "DRIVE_STORAGE_NOT_CONNECTED",
                message=(
                    "Drive OAuth is connected."
                    if connected
                    else "Drive OAuth client secret exists, but the account is not connected yet."
                ),
                detail={
                    "mode": mode,
                    "client_secret_path": str(client_secret_path),
                    "token_path": str(token_path),
                    "connected": connected,
                },
            )

        return ProviderStatus(
            name="drive_storage",
            required=required,
            configured=False,
            ready=False,
            code="DRIVE_STORAGE_CONFIG_INVALID",
            message=f"Unsupported DRIVE_AUTH_MODE '{mode}'.",
            detail={"mode": mode},
        )
    except GoogleCredentialError as exc:
        return ProviderStatus(
            name="drive_storage",
            required=required,
            configured=False,
            ready=False,
            code="DRIVE_STORAGE_NOT_CONFIGURED",
            message=str(exc),
            detail={"mode": mode},
        )
