"""meetdub CLI — `meetdub install | run | doctor | devices | languages`."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from meetdub import __version__, audio, installer
from meetdub.auth_cli import auth_app
from meetdub.config import CONFIG_PATH, Config
from meetdub.languages import LANGUAGES

app = typer.Typer(
    add_completion=False,
    help="Real-time speech-to-speech translation for any meeting app — your voice, every language.",
    no_args_is_help=True,
)
app.add_typer(auth_app, name="auth")
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"meetdub {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version"),
    ] = None,
) -> None:
    pass


@app.command()
def install() -> None:
    """Install BlackHole and walk through audio device setup."""
    raise typer.Exit(installer.run_install())


@app.command()
def doctor() -> None:
    """Check that everything meetdub needs is in place."""
    table = Table(title="meetdub doctor", show_header=True, header_style="bold cyan")
    table.add_column("check")
    table.add_column("status")
    table.add_column("detail", overflow="fold")
    for c in installer.all_checks():
        mark = "[green]✓[/]" if c.ok else "[red]✗[/]"
        table.add_row(c.name, mark, c.detail)
    console.print(table)
    console.print(f"\nconfig: [dim]{CONFIG_PATH}[/]")


@app.command()
def devices() -> None:
    """List audio devices visible to meetdub."""
    table = Table(title="audio devices", show_header=True, header_style="bold cyan")
    table.add_column("#")
    table.add_column("name")
    table.add_column("in")
    table.add_column("out")
    table.add_column("rate")
    for d in audio.list_devices():
        table.add_row(
            str(d.index),
            d.name,
            str(d.max_input_channels),
            str(d.max_output_channels),
            f"{int(d.default_samplerate)}",
        )
    console.print(table)


@app.command()
def languages() -> None:
    """List supported output languages and their hotkeys."""
    table = Table(title="output languages", show_header=True, header_style="bold cyan")
    table.add_column("code")
    table.add_column("name")
    table.add_column("native")
    table.add_column("hotkey")
    for lang in LANGUAGES:
        table.add_row(lang.code, lang.name, lang.native, lang.hotkey or "-")
    console.print(table)


@app.command()
def run(
    to: Annotated[
        str | None, typer.Option("--to", "-t", help="Target language code (e.g. ja, en, es)")
    ] = None,
    input_device: Annotated[
        str | None, typer.Option("--input", help="Input device substring match")
    ] = None,
    output_device: Annotated[
        str | None, typer.Option("--output", help="Output device (default: BlackHole 2ch)")
    ] = None,
    monitor_device: Annotated[
        str | None, typer.Option("--monitor", help="Also play translation to this device")
    ] = None,
    monitor_sync: Annotated[
        bool,
        typer.Option(
            "--monitor-sync",
            help="Delay monitor playback to match BlackHole/meeting-app timing",
        ),
    ] = False,
    push_to_translate: Annotated[
        bool, typer.Option("--ptt", help="Translate only while Space is held")
    ] = False,
    no_vad: Annotated[
        bool, typer.Option("--no-vad", help="Disable voice activity detection")
    ] = False,
    no_transcript: Annotated[
        bool, typer.Option("--no-transcript", help="Don't save bilingual transcript")
    ] = False,
    passthrough: Annotated[
        bool,
        typer.Option(
            "--passthrough",
            help="Mix attenuated original mic into BlackHole (defaults to 15%; adjust with +/- in TUI)",
        ),
    ] = False,
    passthrough_gain: Annotated[
        float | None,
        typer.Option(
            "--passthrough-gain",
            help="Linear gain 0.0–1.0 for the original mic mix (overrides --passthrough)",
            min=0.0,
            max=1.0,
        ),
    ] = None,
    latency_ms: Annotated[
        int | None,
        typer.Option(
            "--latency-ms",
            help="Output buffer in ms. 0 = device minimum (real-time, may stutter). Bump if you hear choppy audio.",
            min=0,
            max=500,
        ),
    ] = None,
    virtual_jitter_ms: Annotated[
        int | None,
        typer.Option(
            "--virtual-jitter-ms",
            help="Initial jitter buffer for virtual mic output. Lower = less lag, higher = smoother.",
            min=0,
            max=500,
        ),
    ] = None,
    virtual_gain: Annotated[
        float | None,
        typer.Option(
            "--virtual-gain",
            help="Gain for virtual mic output. Lower if Teams/BlackHole sounds clipped.",
            min=0.1,
            max=1.0,
        ),
    ] = None,
    azure: Annotated[
        bool, typer.Option("--azure", help="Use Azure OpenAI instead of api.openai.com")
    ] = False,
    azure_endpoint: Annotated[
        str | None,
        typer.Option(
            "--azure-endpoint", help="my-resource.openai.azure.com (or env AZURE_OPENAI_ENDPOINT)"
        ),
    ] = None,
    azure_deployment: Annotated[
        str | None,
        typer.Option("--azure-deployment", help="Deployment name (or env AZURE_OPENAI_DEPLOYMENT)"),
    ] = None,
    azure_api_version: Annotated[
        str | None,
        typer.Option("--azure-api-version", help="If set, uses preview path; omit for GA"),
    ] = None,
    azure_path: Annotated[
        str | None, typer.Option("--azure-path", help="Override URL path if /translations 404s")
    ] = None,
    debug: Annotated[
        bool, typer.Option("--debug", help="Log every WebSocket event to ~/.meetdub/debug.log")
    ] = False,
) -> None:
    """Start translating. Press Esc to stop. F2–F12 to hot-swap language."""
    cfg = Config.load()
    if input_device:
        cfg.input_device = input_device
    if output_device:
        cfg.output_device = output_device
    if monitor_device:
        cfg.monitor_device = monitor_device
    cfg.monitor_sync = monitor_sync
    cfg.push_to_translate = push_to_translate
    cfg.vad_enabled = not no_vad
    cfg.save_transcripts = not no_transcript
    if passthrough_gain is not None:
        cfg.passthrough_gain = passthrough_gain
    elif passthrough:
        cfg.passthrough_gain = 0.15
    if latency_ms is not None:
        cfg.output_latency_ms = latency_ms
    if virtual_jitter_ms is not None:
        cfg.virtual_jitter_ms = virtual_jitter_ms
    if virtual_gain is not None:
        cfg.virtual_gain = virtual_gain

    if azure or azure_endpoint or azure_deployment:
        cfg.backend = "azure"
        if azure_endpoint:
            cfg.azure_endpoint = azure_endpoint
        if azure_deployment:
            cfg.azure_deployment = azure_deployment
        if azure_api_version is not None:
            cfg.azure_api_version = azure_api_version
        if azure_path is not None:
            cfg.azure_path = azure_path

    from meetdub.config import CONFIG_DIR
    from meetdub.runner import Session

    if debug:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.DEBUG,
            filename=str(CONFIG_DIR / "debug.log"),
            filemode="w",
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        console.print(f"[dim]debug log → {CONFIG_DIR / 'debug.log'}[/]")
        logging.getLogger(__name__).debug("meetdub package path: %s", __import__("meetdub").__file__)
        logging.getLogger(__name__).debug("audio module path: %s", audio.__file__)
    else:
        logging.basicConfig(level=logging.WARNING)
    session = Session(cfg, target_override=to)
    code = asyncio.run(session.run())
    raise typer.Exit(code)


@app.command()
def config() -> None:
    """Print current config path and contents."""
    cfg = Config.load()
    console.print(f"[dim]path:[/] {CONFIG_PATH}")
    console.print(cfg)


@app.command()
def setup() -> None:
    """Interactive wizard — pick language, devices, and passthrough once.

    After this, `meetdub run` works without arguments. Re-run anytime to change
    defaults; everything is saved to ~/.meetdub/config.yaml.
    """
    from meetdub.languages import LANGUAGES, resolve

    cfg = Config.load()
    console.print("[bold cyan]meetdub setup[/]  ·  saved to ~/.meetdub/config.yaml\n")

    # --- Target language ---------------------------------------------------
    console.print("[bold]1. Target language[/]")
    for lang in LANGUAGES:
        if not lang.hotkey:
            continue
        marker = "[green]→[/]" if lang.code == cfg.target_language else " "
        console.print(f"   {marker} [cyan]{lang.code:<3}[/] {lang.name} ({lang.native})")
    while True:
        code = typer.prompt("   code", default=cfg.target_language).strip()
        try:
            cfg.target_language = resolve(code).code
            break
        except ValueError as e:
            console.print(f"   [red]{e}[/]")

    # --- Devices -----------------------------------------------------------
    devices = audio.list_devices()
    inputs = [d for d in devices if d.max_input_channels > 0]
    outputs = [d for d in devices if d.max_output_channels > 0]

    def _pick_device(
        title: str, devs: list, current: str | None, recommend: str | None
    ) -> str | None:
        console.print(f"\n[bold]{title}[/]")
        for i, d in enumerate(devs):
            marker = "[green]→[/]" if current and current.lower() in d.name.lower() else " "
            tag = (
                " [yellow](recommended)[/]"
                if recommend and recommend.lower() in d.name.lower()
                else ""
            )
            console.print(f"   {marker} [cyan][{i}][/] {d.name}{tag}")
        raw = typer.prompt("   number (or empty to keep current, '-' to clear)", default="").strip()
        if not raw:
            return current
        if raw == "-":
            return None
        try:
            return devs[int(raw)].name
        except (ValueError, IndexError):
            console.print("   [red]invalid choice — keeping current[/]")
            return current

    cfg.input_device = _pick_device("2. Input mic", inputs, cfg.input_device, "MacBook")
    cfg.output_device = (
        _pick_device(
            "3. Output → meeting app (must be a virtual mic)",
            outputs,
            cfg.output_device,
            "BlackHole",
        )
        or "BlackHole 2ch"
    )
    cfg.monitor_device = _pick_device(
        "4. Monitor (where you hear yourself; empty = don't monitor)",
        outputs,
        cfg.monitor_device,
        "AirPods" if any("airpods" in d.name.lower() for d in outputs) else None,
    )

    # --- Passthrough -------------------------------------------------------
    console.print("\n[bold]5. Original-mic passthrough[/]")
    console.print(
        "   Mix your own voice into the virtual mic at low volume. Recommended\n"
        "   when conversations mix the source and target language (so the other\n"
        "   side keeps hearing you when no translation is generated)."
    )
    current_pct = int(cfg.passthrough_gain * 100)
    raw = typer.prompt(
        f"   percent 0-100 (current: {current_pct})", default=str(current_pct)
    ).strip()
    try:
        pct = max(0, min(100, int(raw)))
        cfg.passthrough_gain = pct / 100.0
    except ValueError:
        console.print("   [red]not a number — keeping current[/]")

    cfg.save()
    secrets_present = bool(
        cfg.api_key() or (cfg.backend == "azure" and (cfg.azure_endpoint or cfg.azure_deployment))
    )
    console.print(f"\n[green]✓[/] saved to [dim]{CONFIG_PATH}[/]")
    if not secrets_present:
        console.print(
            "   [yellow]next:[/] [bold]meetdub auth openai[/] (or [bold]meetdub auth azure[/])"
        )
    console.print("   then: [bold green]meetdub run[/]")


@app.command("keys-test")
def keys_test() -> None:
    """Listen for keyboard events for 15s and print everything received.

    Use this to verify macOS Input Monitoring / Accessibility permissions
    are granted to your terminal. If you press keys and nothing appears,
    permissions are missing.
    """
    import time

    from pynput import keyboard

    received: list[str] = []
    start = time.monotonic()
    deadline = start + 15.0

    console.print("[bold cyan]Press any keys for 15 seconds (Esc to end early)…[/]")
    console.print("[dim]If nothing appears, your terminal lacks Input Monitoring permission.[/]\n")

    done = False

    def on_press(key) -> bool | None:
        nonlocal done
        try:
            label = key.char if hasattr(key, "char") and key.char else str(key).replace("Key.", "")
        except AttributeError:
            label = str(key)
        elapsed = time.monotonic() - start
        line = f"[{elapsed:5.2f}s]  {label}"
        received.append(line)
        console.print(line)
        if key == keyboard.Key.esc:
            done = True
            return False  # stop listener
        return None

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    try:
        while not done and time.monotonic() < deadline:
            time.sleep(0.1)
    finally:
        listener.stop()

    console.print()
    if received:
        console.print(f"[green]✓[/] received {len(received)} key events — permissions look OK.")
    else:
        console.print("[red]✗ no key events received in 15s.[/]")
        console.print(
            "  → macOS is not delivering keys to this process.\n"
            "  → System Settings → Privacy & Security → [bold]Input Monitoring[/] AND "
            "[bold]Accessibility[/]\n"
            "  → Toggle ON the terminal app you're running this from\n"
            "  → Then [bold]Cmd+Q[/] the terminal completely and reopen it"
        )


@app.command("mic-test")
def mic_test() -> None:
    """Record 5s from the default mic and report peak level.

    Use this to verify macOS Microphone permission. A silent stream means
    permission is missing — macOS hands you zero-filled buffers without erroring.
    """
    import time

    import numpy as np
    import sounddevice as sd

    from meetdub import audio as audio_mod

    console.print("[bold cyan]Recording 5s from default mic — speak now…[/]\n")

    peak = 0.0
    samples_count = 0

    def cb(indata, frames, time_info, status):
        nonlocal peak, samples_count
        arr = np.frombuffer(bytes(indata), dtype=np.int16).astype(np.float32) / 32768.0
        if arr.size:
            peak = max(peak, float(np.max(np.abs(arr))))
            samples_count += arr.size

    with sd.RawInputStream(
        samplerate=audio_mod.SAMPLE_RATE,
        blocksize=audio_mod.FRAME_SAMPLES,
        channels=1,
        dtype="int16",
        callback=cb,
    ):
        for i in range(5, 0, -1):
            console.print(f"  {i}…")
            time.sleep(1)

    dbfs = 20.0 * np.log10(peak + 1e-12) if peak > 0 else -120.0
    console.print(f"\nsamples captured: {samples_count}")
    console.print(f"peak: {dbfs:.1f} dBFS")
    if peak < 1e-5:
        console.print(
            "[red]✗ silent — microphone permission likely missing.[/]\n"
            "  → System Settings → Privacy & Security → [bold]Microphone[/]\n"
            "  → Toggle ON your terminal app, then Cmd+Q and reopen."
        )
    elif dbfs < -50:
        console.print(
            "[yellow]⚠ very quiet[/] — mic permission OK, but consider getting closer to the mic."
        )
    else:
        console.print("[green]✓[/] mic permission OK.")
