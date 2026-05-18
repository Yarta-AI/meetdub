"""Rich TUI: bilingual live captions, cost meter, hotkey legend.

Layout:
    ┌────────────────────────────── meetdub ──────────────────────────────┐
    │ status: connected · target=ja · cost: $0.024 · 02:14 elapsed         │
    ├──────────────────────── source (auto-detect) ────────────────────────┤
    │ Hello everyone, let's get started.                                   │
    ├────────────────────────── target (ja) ───────────────────────────────┤
    │ 皆さん、こんにちは。始めましょう。                                   │
    ├────────────────────────────  hotkeys ────────────────────────────────┤
    │ F2 EN  F3 JA  F4 ES  F5 FR  F6 DE  F7 ZH  F8 KO  F9 PT … Space=PTT   │
    └──────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import time
from collections import deque

from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from meetdub.languages import BY_CODE, LANGUAGES


class CaptionsUI:
    def __init__(self, target_language: str) -> None:
        self.target = target_language
        self._status = "connecting…"
        self._cost = 0.0
        self._t0 = time.monotonic()
        self._source_lines: deque[str] = deque(maxlen=6)
        self._target_lines: deque[str] = deque(maxlen=6)
        self._partial_source = ""
        self._partial_target = ""
        self._live: Live | None = None

    def __enter__(self) -> CaptionsUI:
        self._live = Live(self._render(), refresh_per_second=12, screen=False)
        self._live.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        if self._live:
            self._live.__exit__(*exc)

    def set_status(self, status: str) -> None:
        self._status = status
        self._refresh()

    def set_target(self, code: str) -> None:
        self.target = code
        self._refresh()

    def set_cost(self, usd: float) -> None:
        self._cost = usd
        self._refresh()

    def push_source(self, text: str, done: bool) -> None:
        self._partial_source += text
        if done and self._partial_source.strip():
            self._source_lines.append(self._partial_source.strip())
            self._partial_source = ""
        self._refresh()

    def push_target(self, text: str, done: bool) -> None:
        self._partial_target += text
        if done and self._partial_target.strip():
            self._target_lines.append(self._partial_target.strip())
            self._partial_target = ""
        self._refresh()

    def _refresh(self) -> None:
        if self._live:
            self._live.update(self._render())

    def _status_line(self) -> Text:
        elapsed = int(time.monotonic() - self._t0)
        mins, secs = divmod(elapsed, 60)
        lang = BY_CODE.get(self.target)
        target_label = f"{lang.native} ({lang.code})" if lang else self.target
        return Text.assemble(
            ("● ", "bold green"),
            (self._status, "white"),
            ("  ·  ", "dim"),
            ("target: ", "dim"),
            (target_label, "bold cyan"),
            ("  ·  ", "dim"),
            ("cost: ", "dim"),
            (f"${self._cost:.4f}", "bold yellow"),
            ("  ·  ", "dim"),
            (f"{mins:02d}:{secs:02d}", "dim"),
        )

    def _captions(self, lines: deque[str], partial: str, title: str, color: str) -> Panel:
        body = Text()
        for line in lines:
            body.append(line + "\n", style="dim")
        if partial:
            body.append(partial, style=color)
        return Panel(body, title=title, border_style=color, padding=(0, 1))

    def _hotkeys(self) -> Panel:
        body = Text()
        for lang in LANGUAGES:
            if not lang.hotkey:
                continue
            body.append(f" {lang.hotkey} ", style="reverse cyan")
            body.append(f"{lang.code.upper()} ", style="white")
        body.append("  Space ", style="reverse magenta")
        body.append("push-to-translate  ", style="white")
        body.append(" Esc ", style="reverse red")
        body.append("quit", style="white")
        return Panel(body, border_style="dim")

    def _render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(Panel(self._status_line(), border_style="green"), size=3),
            Layout(name="captions", ratio=1),
            Layout(self._hotkeys(), size=3),
        )
        layout["captions"].split_column(
            Layout(self._captions(self._source_lines, self._partial_source, "source", "white")),
            Layout(
                self._captions(self._target_lines, self._partial_target, f"→ {self.target}", "cyan")
            ),
        )
        return layout
