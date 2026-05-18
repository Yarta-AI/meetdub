"""Azure Entra ID (AAD) token acquisition.

When an Azure OpenAI resource is configured for "Microsoft Entra ID
authentication only" (api-key disabled), we need to send a Bearer token
acquired against the cognitive-services scope.

Tokens last ~60 minutes. We grab a fresh one at session start; a single
meeting < 1h is covered by one token, and the WebSocket only authenticates
during the handshake, so mid-session expiry doesn't drop the call.

Auth methods, in the order we try them:

  1. AZURE_OPENAI_AAD_TOKEN env var or secrets.env — already-acquired token.
  2. Cached azure-identity credentials (`az login`, VS Code Azure account,
     Azure PowerShell, Managed Identity, service-principal env vars).
     This is `DefaultAzureCredential`'s natural job.
  3. `meetdub auth login` — interactive browser login that populates the
     shared azure-identity token cache so (2) starts working with no
     external prerequisites.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

SCOPE = "https://cognitiveservices.azure.com/.default"


@dataclass
class TokenResult:
    token: str
    method: str  # human description for status line / doctor


class AzureAuthError(RuntimeError):
    pass


def acquire_token() -> TokenResult:
    """Try every method until one yields a token. Raise AzureAuthError otherwise."""
    pre_acquired = os.environ.get("AZURE_OPENAI_AAD_TOKEN")
    if pre_acquired:
        return TokenResult(pre_acquired, "AZURE_OPENAI_AAD_TOKEN env")

    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise AzureAuthError(
            "azure-identity is not installed. Run `pipx inject meetdub azure-identity` "
            "or reinstall meetdub."
        ) from exc

    try:
        cred = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        tok = cred.get_token(SCOPE)
        return TokenResult(tok.token, "DefaultAzureCredential")
    except Exception as exc:  # noqa: BLE001 — azure-identity raises many subtypes
        raise AzureAuthError(
            "no Azure credential available.\n"
            "  Easiest fix: run `meetdub auth login` (browser login)\n"
            "  Or:          `brew install azure-cli && az login`\n"
            "  Or set:      AZURE_CLIENT_ID / AZURE_TENANT_ID / AZURE_CLIENT_SECRET "
            "(service principal)\n"
            f"  Underlying error: {exc}"
        ) from exc


def interactive_login() -> TokenResult:
    """Open a browser to log the user into Azure AD and warm the shared cache."""
    try:
        from azure.identity import InteractiveBrowserCredential
    except ImportError as exc:
        raise AzureAuthError("azure-identity is not installed.") from exc
    cred = InteractiveBrowserCredential()
    tok = cred.get_token(SCOPE)
    return TokenResult(tok.token, "InteractiveBrowserCredential")
