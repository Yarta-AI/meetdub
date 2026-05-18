"""Backend abstraction — OpenAI direct vs Azure OpenAI.

OpenAI:
    wss://api.openai.com/v1/realtime/translations?model=gpt-realtime-translate
    header: Authorization: Bearer <OPENAI_API_KEY>

Azure (GA path, recommended):
    wss://<resource>.openai.azure.com/openai/v1/realtime/translations?model=<deployment>
    header: api-key: <AZURE_OPENAI_API_KEY>
            OR Authorization: Bearer <AAD_TOKEN>

Azure (preview path, deprecated 2026-04-30):
    wss://<resource>.openai.azure.com/openai/realtime/translations?api-version=<v>&deployment=<deployment>

Note on translation parity: as of May 2026 Azure's published Realtime docs list
`gpt-realtime`, `gpt-realtime-mini`, and `gpt-realtime-1.5` but do not yet
document `gpt-realtime-translate` or the `/translations` sub-path explicitly.
We default to the `/translations` path optimistically. If your Azure region
hasn't shipped the translate-specific endpoint yet, run with
`--azure-path /openai/v1/realtime` to fall back to the general realtime endpoint
(translation will still work via session.update output.language, but without
the interpreter-tuned voice adaptation).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlencode, urlparse


@dataclass(frozen=True)
class Backend:
    name: str
    ws_url: str
    headers: dict[str, str]

    def describe(self) -> str:
        host = urlparse(self.ws_url).netloc
        return f"{self.name} · {host}"


def openai_backend(api_key: str) -> Backend:
    return Backend(
        name="openai",
        ws_url="wss://api.openai.com/v1/realtime/translations?model=gpt-realtime-translate",
        headers={"Authorization": f"Bearer {api_key}"},
    )


def azure_backend(
    endpoint: str,
    deployment: str,
    api_key: str | None = None,
    aad_token: str | None = None,
    api_version: str | None = None,
    path: str | None = None,
) -> Backend:
    """Build an Azure OpenAI Realtime backend.

    endpoint:    bare host like "my-resource.openai.azure.com" OR a full
                 "https://my-resource.openai.azure.com" URL. Scheme is stripped.
    deployment:  name of your deployed gpt-realtime-translate model.
    api_key:     uses `api-key` header (preferred for non-browser).
    aad_token:   uses `Authorization: Bearer <token>` (Microsoft Entra).
    api_version: if set, uses preview path; if unset, uses GA `/openai/v1` path.
    path:        override the URL path entirely (e.g. "/openai/v1/realtime"
                 if `/translations` is not yet available in your region).
    """
    if not endpoint:
        raise ValueError("Azure endpoint is required (e.g. my-resource.openai.azure.com)")
    if not deployment:
        raise ValueError("Azure deployment name is required")
    if not api_key and not aad_token:
        raise ValueError("Provide either api_key or aad_token for Azure")

    host = endpoint.replace("https://", "").replace("http://", "").rstrip("/")

    if path:
        base_path = path.lstrip("/")
    elif api_version:
        base_path = "openai/realtime/translations"
    else:
        base_path = "openai/v1/realtime/translations"

    if api_version:
        qs = urlencode({"api-version": api_version, "deployment": deployment})
    else:
        qs = urlencode({"model": deployment})

    headers: dict[str, str] = {}
    if aad_token:
        headers["Authorization"] = f"Bearer {aad_token}"
    elif api_key:
        headers["api-key"] = api_key

    return Backend(
        name="azure",
        ws_url=f"wss://{host}/{base_path}?{qs}",
        headers=headers,
    )


def from_env_or_config(cfg) -> Backend:
    """Resolve a Backend from Config + environment variables.

    Selection rules:
      1. If cfg.backend == "azure", build an Azure backend.
      2. Otherwise build an OpenAI backend.
    Required env vars are read here so callers get one clear error.

    Azure auth fallback chain:
      • AZURE_OPENAI_API_KEY        → api-key header
      • AZURE_OPENAI_AAD_TOKEN      → static Bearer
      • cfg.azure_auth_mode == aad  → DefaultAzureCredential (az login, etc.)
      • neither                     → try DefaultAzureCredential anyway
    """
    if cfg.backend == "azure":
        endpoint = cfg.azure_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        deployment = cfg.azure_deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
        api_key = os.environ.get(cfg.azure_api_key_env or "AZURE_OPENAI_API_KEY")
        aad_token = os.environ.get("AZURE_OPENAI_AAD_TOKEN") or None

        force_aad = cfg.azure_auth_mode == "aad"
        if force_aad or (not api_key and not aad_token):
            from meetdub.azure_auth import AzureAuthError, acquire_token

            try:
                aad_token = acquire_token().token
                api_key = None  # AAD takes precedence
            except AzureAuthError as exc:
                if api_key:
                    pass  # fall back to api-key if we have one
                else:
                    raise RuntimeError(str(exc)) from exc

        return azure_backend(
            endpoint=endpoint,
            deployment=deployment,
            api_key=api_key,
            aad_token=aad_token,
            api_version=cfg.azure_api_version or None,
            path=cfg.azure_path or None,
        )

    api_key = os.environ.get(cfg.api_key_env)
    if not api_key:
        raise RuntimeError("Missing OpenAI API key — run `meetdub auth openai` or use --azure.")
    return openai_backend(api_key)
