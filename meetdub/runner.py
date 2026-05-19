"""Glue: mic → VAD → translator → BlackHole + TUI + hotkeys + transcript."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

from rich.console import Console

from meetdub import audio, secrets
from meetdub.backend import from_env_or_config
from meetdub.config import Config
from meetdub.hotkeys import Hotkeys
from meetdub.languages import BY_HOTKEY, resolve
from meetdub.transcript import TranscriptWriter
from meetdub.translator import RealtimeTranslator, TranslatorEvents
from meetdub.tui_input import TtyKeys
from meetdub.ui import CaptionsUI
from meetdub.vad import VAD

console = Console()
log = logging.getLogger(__name__)


class Session:
    def __init__(self, cfg: Config, target_override: str | None = None) -> None:
        self.cfg = cfg
        target = target_override or cfg.target_language
        self.target = resolve(target).code
        self.cfg.target_language = self.target
        self._stop = asyncio.Event()
        self._ptt_active = not cfg.push_to_translate  # PTT off = always-on

    def _request_stop(self) -> None:
        self._stop.set()

    async def run(self) -> int:
        secrets.load_into_env()
        try:
            backend = from_env_or_config(self.cfg)
        except (RuntimeError, ValueError) as exc:
            console.print(f"[red]{exc}[/]")
            console.print(
                "[dim]hint: run `meetdub auth openai` or `meetdub auth azure` to save credentials.[/]"
            )
            return 1

        out_dev = audio.find_device(self.cfg.output_device, "output")
        if out_dev is None:
            console.print(
                f"[red]Output device '{self.cfg.output_device}' not found.[/] "
                "Run [bold]meetdub install[/] or [bold]meetdub devices[/]."
            )
            return 1

        # Input: configured name if set, else prefer built-in mic over wireless
        # (AirPods mic pickup is unreliable for translation accuracy).
        in_dev_idx: int | None = None
        if self.cfg.input_device:
            inf = audio.find_device(self.cfg.input_device, "input")
            in_dev_idx = inf.index if inf else None
        else:
            for hint in ("MacBook", "Built-in", "内蔵"):
                inf = audio.find_device(hint, "input")
                if inf:
                    in_dev_idx = inf.index
                    console.print(f"[dim]input auto-selected:[/] {inf.name}")
                    break

        monitor_idx: int | None = None
        if self.cfg.monitor_device:
            mon = audio.find_device(self.cfg.monitor_device, "output")
            monitor_idx = mon.index if mon else None

        latency: float | str = (
            "low" if self.cfg.output_latency_ms <= 0 else self.cfg.output_latency_ms / 1000.0
        )
        speaker = audio.Speaker(out_dev.index, monitor_idx, latency=latency)
        speaker.start()

        transcript: TranscriptWriter | None = None
        if self.cfg.save_transcripts:
            transcript = TranscriptWriter(self.target)

        ui = CaptionsUI(self.target, ptt_enabled=self.cfg.push_to_translate)
        vad = VAD() if self.cfg.vad_enabled else None
        loop = asyncio.get_running_loop()

        events = TranslatorEvents(
            on_audio=speaker.write,
            on_input_text=lambda t, d: (
                ui.push_source(t, d),
                transcript and transcript.append_source(t, d),
            ),
            on_output_text=lambda t, d: (
                ui.push_target(t, d),
                transcript and transcript.append_target(t, d),
            ),
            on_status=ui.set_status,
            on_error=lambda m: ui.set_status(f"error: {m}"),
        )

        # macOS signal handling
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, self._request_stop)

        with ui:
            async with RealtimeTranslator(
                backend, self.target, events, self.cfg.noise_reduction
            ) as translator:
                recv_task = asyncio.create_task(translator.receive_loop())

                def lang_change(code: str) -> None:
                    ui.set_target(code)
                    asyncio.run_coroutine_threadsafe(translator.switch_language(code), loop)

                def ptt(active: bool) -> None:
                    if self.cfg.push_to_translate:
                        self._ptt_active = active
                        ui.set_status("speaking…" if active else "muted (PTT)")

                def volume(action: str) -> None:
                    g = self.cfg.passthrough_gain
                    if action == "VolUp":
                        g = min(1.0, round(g + 0.05, 2))
                    elif action == "VolDown":
                        g = max(0.0, round(g - 0.05, 2))
                    elif action == "VolMute":
                        g = 0.0
                    self.cfg.passthrough_gain = g
                    ui.set_passthrough(g)

                def tty_key(name: str) -> None:
                    if name == "Esc":
                        self._request_stop()
                    elif name == "Space" and self.cfg.push_to_translate:
                        # Raw TTY can't see press/release — toggle PTT instead.
                        ptt(not self._ptt_active)
                    elif name in ("VolUp", "VolDown", "VolMute"):
                        volume(name)
                    else:
                        lang = BY_HOTKEY.get(name)
                        if lang:
                            lang_change(lang.code)

                ui.set_passthrough(self.cfg.passthrough_gain)

                with (
                    Hotkeys(
                        on_language=lang_change,
                        on_quit=self._request_stop,
                        on_push_to_translate=ptt,
                        on_volume=volume,
                    ),
                    TtyKeys(tty_key),
                ):
                    async with audio.MicCapture(in_dev_idx) as mic:
                        await self._pump(mic, translator, vad, ui, speaker)

                recv_task.cancel()

        speaker.close()
        if transcript:
            transcript.close()
            console.print(f"[green]Transcript saved:[/] {transcript.path}")
        self.cfg.save()
        return 0

    async def _pump(
        self,
        mic: audio.MicCapture,
        translator: RealtimeTranslator,
        vad: VAD | None,
        ui: CaptionsUI,
        speaker: audio.Speaker,
    ) -> None:
        last_cost_update = 0.0
        while not self._stop.is_set():
            try:
                chunk = await asyncio.wait_for(mic.queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if not self._ptt_active:
                continue

            # Passthrough original mic into BlackHole at the configured gain.
            # Runs unconditionally on speech AND silence so the other side
            # always hears something (this is the cookbook's recommendation
            # for same-language fallback).
            gain = self.cfg.passthrough_gain
            if gain > 0.0:
                speaker.write_primary(audio.attenuate_pcm16(chunk, gain))

            if vad is not None and not vad.is_speech(chunk):
                continue
            await translator.send_audio(chunk)
            if translator.cost_usd - last_cost_update > 0.001:
                ui.set_cost(translator.cost_usd)
                last_cost_update = translator.cost_usd
