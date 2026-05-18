"""`meetdub auth …` subcommands.

UX:
  meetdub auth openai                 # interactive prompt for OPENAI_API_KEY
  meetdub auth openai --key sk-…      # non-interactive
  meetdub auth azure                  # interactive: endpoint, deployment, key
  meetdub auth azure --endpoint X --deployment Y --key Z
  meetdub auth show                   # masked summary
  meetdub auth clear                  # remove all secrets
  meetdub auth clear --openai         # remove only OpenAI secret
  meetdub auth path                   # print secrets.env path
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from meetdub import secrets as secrets_mod
from meetdub.config import Config

auth_app = typer.Typer(
    help="Manage API keys (stored in ~/.meetdub/secrets.env, chmod 600).", no_args_is_help=True
)
console = Console()


def _prompt_secret(label: str, current: str | None) -> str:
    suffix = f" [{secrets_mod.mask(current)}]" if current else ""
    return typer.prompt(
        f"{label}{suffix}", hide_input=True, default=current or "", show_default=False
    )


@auth_app.command("openai")
def openai_cmd(
    key: Annotated[str | None, typer.Option("--key", help="API key (skip to be prompted)")] = None,
) -> None:
    """Set OpenAI API key."""
    existing = secrets_mod.read_all()
    value = key or _prompt_secret("OPENAI_API_KEY", existing.get("OPENAI_API_KEY"))
    if not value:
        console.print("[yellow]no value entered — nothing changed[/]")
        raise typer.Exit(1)
    secrets_mod.set_value("OPENAI_API_KEY", value)
    cfg = Config.load()
    cfg.backend = "openai"
    cfg.save()
    console.print(f"[green]✓[/] OpenAI key saved → [dim]{secrets_mod.SECRETS_PATH}[/]")


@auth_app.command("azure")
def azure_cmd(
    endpoint: Annotated[
        str | None, typer.Option("--endpoint", help="my-resource.openai.azure.com")
    ] = None,
    deployment: Annotated[str | None, typer.Option("--deployment", help="Deployment name")] = None,
    key: Annotated[str | None, typer.Option("--key", help="API key")] = None,
    aad_token: Annotated[
        str | None, typer.Option("--aad-token", help="Microsoft Entra Bearer token")
    ] = None,
) -> None:
    """Set Azure OpenAI credentials."""
    existing = secrets_mod.read_all()
    endpoint = endpoint or typer.prompt(
        "AZURE_OPENAI_ENDPOINT (e.g. my-resource.openai.azure.com)",
        default=existing.get("AZURE_OPENAI_ENDPOINT", ""),
    )
    deployment = deployment or typer.prompt(
        "AZURE_OPENAI_DEPLOYMENT (deployment name)",
        default=existing.get("AZURE_OPENAI_DEPLOYMENT", ""),
    )
    if not aad_token and not key:
        key = _prompt_secret("AZURE_OPENAI_API_KEY", existing.get("AZURE_OPENAI_API_KEY"))

    if endpoint:
        secrets_mod.set_value("AZURE_OPENAI_ENDPOINT", endpoint)
    if deployment:
        secrets_mod.set_value("AZURE_OPENAI_DEPLOYMENT", deployment)
    if key:
        secrets_mod.set_value("AZURE_OPENAI_API_KEY", key)
        secrets_mod.clear_keys(["AZURE_OPENAI_AAD_TOKEN"])
    if aad_token:
        secrets_mod.set_value("AZURE_OPENAI_AAD_TOKEN", aad_token)
        secrets_mod.clear_keys(["AZURE_OPENAI_API_KEY"])

    cfg = Config.load()
    cfg.backend = "azure"
    if endpoint:
        cfg.azure_endpoint = endpoint
    if deployment:
        cfg.azure_deployment = deployment
    cfg.save()
    console.print(f"[green]✓[/] Azure credentials saved → [dim]{secrets_mod.SECRETS_PATH}[/]")


@auth_app.command("show")
def show_cmd() -> None:
    """Show what's stored (values masked)."""
    values = secrets_mod.read_all()
    if not values:
        console.print(f"[yellow]no secrets stored[/] · [dim]{secrets_mod.SECRETS_PATH}[/]")
        return
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("key")
    table.add_column("value")
    for k in secrets_mod.KNOWN_KEYS:
        if k in values:
            table.add_row(
                k, secrets_mod.mask(values[k]) if "KEY" in k or "TOKEN" in k else values[k]
            )
    console.print(table)
    console.print(f"[dim]file: {secrets_mod.SECRETS_PATH}[/]")


@auth_app.command("clear")
def clear_cmd(
    openai: Annotated[bool, typer.Option("--openai", help="Clear OpenAI key only")] = False,
    azure: Annotated[bool, typer.Option("--azure", help="Clear Azure credentials only")] = False,
    all_: Annotated[bool, typer.Option("--all", help="Clear everything")] = False,
) -> None:
    """Remove stored secrets."""
    if not (openai or azure or all_):
        if not typer.confirm("Clear ALL stored secrets?", default=False):
            raise typer.Exit()
        all_ = True
    if all_:
        secrets_mod.clear_keys(None)
        console.print("[green]✓[/] all secrets cleared")
        return
    to_clear: list[str] = []
    if openai:
        to_clear.append("OPENAI_API_KEY")
    if azure:
        to_clear.extend(
            [
                "AZURE_OPENAI_ENDPOINT",
                "AZURE_OPENAI_DEPLOYMENT",
                "AZURE_OPENAI_API_KEY",
                "AZURE_OPENAI_AAD_TOKEN",
            ]
        )
    secrets_mod.clear_keys(to_clear)
    console.print(f"[green]✓[/] cleared: {', '.join(to_clear)}")


@auth_app.command("path")
def path_cmd() -> None:
    """Print the secrets file path."""
    console.print(str(secrets_mod.SECRETS_PATH))


@auth_app.command("login")
def login_cmd() -> None:
    """Interactive browser login for Azure Entra ID (no `az` CLI required).

    Opens your default browser, signs you in, and warms the azure-identity
    token cache so subsequent `meetdub run --azure` calls can grab fresh
    tokens automatically. Use this when your Azure OpenAI resource is
    configured for Microsoft Entra ID authentication (api-key disabled).
    """
    from meetdub.azure_auth import AzureAuthError, interactive_login

    console.print("[cyan]opening browser to sign you into Azure…[/]")
    try:
        result = interactive_login()
    except AzureAuthError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc
    cfg = Config.load()
    cfg.backend = "azure"
    cfg.azure_auth_mode = "aad"
    cfg.save()
    console.print(f"[green]✓[/] signed in via {result.method}.")
    console.print("[dim]Token cached. `meetdub run --azure` will reuse this login.[/]")
