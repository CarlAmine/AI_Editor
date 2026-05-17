from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import OpenAI

from pipeline.provider_errors import ProviderFailure, normalize_provider_exception


@dataclass
class _Provider:
    name: str
    model: str
    base_url: str
    env_key: str
    client: OpenAI


_PROVIDER_CONFIGS = [
    {
        "name": "huggingface",
        "model": "meta-llama/llama-3.3-70b-instruct",
        "base_url": "https://router.huggingface.co/novita/v3/openai",
        "env_key": "HF_API_KEY",
    },
    {
        "name": "openrouter",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
    },
    {
        "name": "groq",
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ",
    },
]


def _build_providers() -> List[_Provider]:
    providers: List[_Provider] = []
    for cfg in _PROVIDER_CONFIGS:
        api_key = os.getenv(cfg["env_key"])
        if not api_key:
            continue
        providers.append(
            _Provider(
                name=cfg["name"],
                model=cfg["model"],
                base_url=cfg["base_url"],
                env_key=cfg["env_key"],
                client=OpenAI(api_key=api_key, base_url=cfg["base_url"]),
            )
        )
    return providers


def _ordered_providers(preferred_provider: Optional[str]) -> List[_Provider]:
    providers = _build_providers()
    if not providers or not preferred_provider:
        return providers

    preferred = preferred_provider.strip().lower()
    for idx, provider in enumerate(providers):
        if provider.name == preferred:
            return [providers[idx]] + providers[:idx] + providers[idx + 1 :]
    return providers


def get_provider_readiness(preferred_provider: Optional[str] = None) -> Dict[str, Any]:
    statuses: List[Dict[str, Any]] = []
    ordered_names = [provider.name for provider in _ordered_providers(preferred_provider)]
    for cfg in _PROVIDER_CONFIGS:
        configured = bool(os.getenv(cfg["env_key"]))
        statuses.append(
            {
                "name": cfg["name"],
                "model": cfg["model"],
                "env_key": cfg["env_key"],
                "configured": configured,
                "ready": configured,
                "preferred": cfg["name"] == (preferred_provider or "").strip().lower(),
                "priority": ordered_names.index(cfg["name"]) if cfg["name"] in ordered_names else None,
                "message": (
                    f"{cfg['env_key']} is configured."
                    if configured
                    else f"Set {cfg['env_key']} to enable this model provider."
                ),
            }
        )
    return {
        "providers": statuses,
        "ready": any(status["ready"] for status in statuses),
        "active_provider": get_active_model_name(),
    }


def _strip_markdown_fences(text: str) -> str:
    if not text:
        return text
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def chat_json(
    messages: List[Dict[str, Any]],
    temperature: float = 0.2,
    max_tokens: int = 2048,
    preferred_provider: Optional[str] = None,
    *,
    raise_on_failure: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Try providers in priority order. For each, call chat.completions.create() with
    response_format={"type": "json_object"}. Parse and return the JSON dict.
    Strip markdown fences if present. Return None if all providers fail.
    Log which provider is being tried and whether it succeeded or failed.
    """
    providers = _ordered_providers(preferred_provider)
    if not providers:
        failure = ProviderFailure(
            provider="model_provider",
            code="MODEL_PROVIDER_NOT_CONFIGURED",
            user_message="No AI controller model provider is configured. Set HF_API_KEY, OPENROUTER_API_KEY, or GROQ.",
            detail={"preferred_provider": preferred_provider},
            retryable=False,
        )
        if raise_on_failure:
            raise failure
        return None

    attempts: List[Dict[str, Any]] = []
    last_failure: Optional[ProviderFailure] = None
    for provider in providers:
        label = f"{provider.name}/{provider.model}"
        print(f"AI client: trying {label}")
        try:
            completion = provider.client.chat.completions.create(
                messages=messages,
                model=provider.model,
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
            raw = completion.choices[0].message.content or ""
            raw = _strip_markdown_fences(raw)
            data = json.loads(raw)
            print(f"AI client: {label} succeeded")
            return data
        except Exception as e:
            print(f"AI client: {label} failed: {e}")
            failure = normalize_provider_exception(
                "model_provider",
                e,
                operation=f"chat_json:{label}",
                config_message="The configured AI model provider is not usable. Check the provider API key and client setup.",
                timeout_message="The AI controller timed out while choosing the next action. Please retry.",
                auth_message="The AI model provider rejected authentication. Check the configured API key.",
                network_message="The AI model provider is temporarily unavailable. Please retry.",
                default_message="The AI controller failed to get a structured decision from the model provider.",
            )
            attempts.append({"provider": label, "code": failure.code, "detail": failure.detail})
            last_failure = failure
            continue
    if raise_on_failure and last_failure is not None:
        raise ProviderFailure(
            provider=last_failure.provider,
            code=last_failure.code,
            user_message=last_failure.user_message,
            detail={"attempts": attempts},
            retryable=last_failure.retryable,
        )
    return None


def chat_text(
    messages: List[Dict[str, Any]],
    temperature: float = 0.4,
    max_tokens: int = 1024,
    preferred_provider: Optional[str] = None,
    *,
    raise_on_failure: bool = False,
) -> Optional[str]:
    """Same but no response_format constraint. Return raw text content or None."""
    providers = _ordered_providers(preferred_provider)
    if not providers:
        failure = ProviderFailure(
            provider="model_provider",
            code="MODEL_PROVIDER_NOT_CONFIGURED",
            user_message="No AI text model provider is configured. Set HF_API_KEY, OPENROUTER_API_KEY, or GROQ.",
            detail={"preferred_provider": preferred_provider},
            retryable=False,
        )
        if raise_on_failure:
            raise failure
        return None

    attempts: List[Dict[str, Any]] = []
    last_failure: Optional[ProviderFailure] = None
    for provider in providers:
        label = f"{provider.name}/{provider.model}"
        print(f"AI client: trying {label}")
        try:
            completion = provider.client.chat.completions.create(
                messages=messages,
                model=provider.model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = completion.choices[0].message.content
            if content is None:
                raise ValueError("Empty response content")
            print(f"AI client: {label} succeeded")
            return content
        except Exception as e:
            print(f"AI client: {label} failed: {e}")
            failure = normalize_provider_exception(
                "model_provider",
                e,
                operation=f"chat_text:{label}",
                config_message="The configured AI text provider is not usable. Check the provider API key and client setup.",
                timeout_message="The AI text provider timed out. Please retry.",
                auth_message="The AI text provider rejected authentication. Check the configured API key.",
                network_message="The AI text provider is temporarily unavailable. Please retry.",
                default_message="The AI text provider failed to respond.",
            )
            attempts.append({"provider": label, "code": failure.code, "detail": failure.detail})
            last_failure = failure
            continue
    if raise_on_failure and last_failure is not None:
        raise ProviderFailure(
            provider=last_failure.provider,
            code=last_failure.code,
            user_message=last_failure.user_message,
            detail={"attempts": attempts},
            retryable=last_failure.retryable,
        )
    return None


def get_active_model_name() -> str:
    """Return 'provider/model' string for the first configured provider, for logging."""
    providers = _build_providers()
    if not providers:
        return ""
    provider = providers[0]
    return f"{provider.name}/{provider.model}"
