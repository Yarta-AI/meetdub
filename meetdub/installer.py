"""One-shot installer.

What this does:
  1. Verify macOS (BlackHole is macOS-only).
  2. Install Homebrew if missing — we ASK first; we never run `curl | bash` ourselves.
  3. `brew install --cask blackhole-2ch`.
  4. Print step-by-step guidance for the one manual step macOS doesn't expose
     to scripts: creating a Multi-Output Device in Audio MIDI Setup so the
     user can hear themselves while Teams hears the translation.

We avoid AppleScript automation of Audio MIDI Setup because it requires
accessibility prompts and has flaky selectors across macOS versions —
a clear 30-second checklist is more robust than a brittle automator.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from meetdub import audio

console = Console()


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return proc.returncode, (proc.stdout + proc.stderr)
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"


def check_platform() -> Check:
    is_mac = platform.system() == "Darwin"
    return Check("macOS", is_mac, platform.platform())


def check_brew() -> Check:
    path = shutil.which("brew")
    return Check("Homebrew", path is not None, path or "not found")


def check_blackhole() -> Check:
    dev = audio.find_device("BlackHole", "output")
    return Check(
        "BlackHole 2ch",
        dev is not None,
        dev.name if dev else "not installed",
    )


def check_api_key(env_var: str = "OPENAI_API_KEY") -> Check:
    import os

    from meetdub import secrets

    secrets.load_into_env()
    val = os.environ.get(env_var)
    source = "secrets.env" if env_var in secrets.read_all() else "shell env"
    return Check(
        env_var,
        bool(val),
        f"set via {source}" if val else "unset — run `meetdub auth openai`",
    )


def check_azure() -> list[Check]:
    import os

    from meetdub.config import Config

    cfg = Config.load()
    if cfg.backend != "azure":
        return []
    endpoint = cfg.azure_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    deployment = cfg.azure_deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
    api_key = os.environ.get(cfg.azure_api_key_env, "")
    aad = os.environ.get("AZURE_OPENAI_AAD_TOKEN", "")
    return [
        Check("AZURE_OPENAI_ENDPOINT", bool(endpoint), endpoint or "unset"),
        Check("AZURE_OPENAI_DEPLOYMENT", bool(deployment), deployment or "unset"),
        Check(
            "Azure auth",
            bool(api_key or aad),
            f"{cfg.azure_api_key_env} set"
            if api_key
            else ("AAD token set" if aad else "no api-key or AAD token"),
        ),
    ]


def all_checks() -> list[Check]:
    base = [check_platform(), check_brew(), check_blackhole(), check_api_key()]
    return base + check_azure()


def install_homebrew_if_missing() -> bool:
    if shutil.which("brew"):
        return True
    console.print(
        Panel(
            "Homebrew is not installed.\n\n"
            "meetdub will not install it automatically. Please install it yourself "
            "from [bold cyan]https://brew.sh[/] and re-run [bold]meetdub install[/].",
            title="Homebrew required",
            border_style="yellow",
        )
    )
    return False


def install_blackhole() -> bool:
    if check_blackhole().ok:
        console.print("[green]✓[/] BlackHole 2ch already installed.")
        return True
    if not shutil.which("brew"):
        return False
    if not Confirm.ask(
        "Install [bold]BlackHole 2ch[/] via Homebrew? (sudo prompt will appear)",
        default=True,
    ):
        return False
    console.print("[dim]running: brew install --cask blackhole-2ch[/]")
    code, out = _run(["brew", "install", "--cask", "blackhole-2ch"])
    if code != 0:
        console.print(f"[red]brew failed[/]\n{out}")
        return False
    console.print("[green]✓[/] BlackHole 2ch installed.")
    return True


def print_audio_midi_guide() -> None:
    """Walks the user through the one manual step macOS can't safely script."""
    console.print(
        Panel(
            """
[bold]Set up a Multi-Output Device so you can hear yourself.[/]

When meetdub is running, your translated voice goes to BlackHole, and Teams/Zoom
listens to BlackHole. But if BlackHole is your only output, [italic]you[/] won't
hear anything either. A Multi-Output Device sends audio to BlackHole [bold]and[/]
your speakers/headphones at the same time.

  1. Open [cyan]/Applications/Utilities/Audio MIDI Setup.app[/]
  2. Click [bold]+[/] (bottom-left) → [bold]Create Multi-Output Device[/]
  3. Tick: [cyan]Built-in Output[/] (or your headphones) and [cyan]BlackHole 2ch[/]
  4. Rename it to [bold]"meetdub Multi-Output"[/] for clarity
  5. Right-click it → [bold]Use This Device For Sound Output[/]

In Teams/Zoom/Meet:
  • Microphone → [bold]BlackHole 2ch[/]
  • Speaker → [bold]meetdub Multi-Output[/] (or your headphones directly)

That's it. Run [bold green]meetdub doctor[/] to verify.
            """.strip(),
            title="One manual step",
            border_style="cyan",
        )
    )


def run_install() -> int:
    if not check_platform().ok:
        console.print("[red]meetdub install currently supports macOS only (BlackHole is macOS).[/]")
        return 1
    if not install_homebrew_if_missing():
        return 1
    if not install_blackhole():
        return 1
    print_audio_midi_guide()
    console.print("\n[bold green]Install complete.[/] Try: [bold]meetdub run --to ja[/]")
    return 0
