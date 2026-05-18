"""Read F-keys / Space / Esc from the TTY in raw mode.

When macOS Input Monitoring permission is missing (pynput's
`This process is not trusted!` case), global hotkeys silently fail.

This module reads keys directly from `/dev/tty` using termios — no
system-wide permission required — so language switching still works
while meetdub's terminal is the focused window. When meetdub is in the
background (Teams focused), only pynput global hotkeys can fire; that's
a macOS-level constraint, not something we can work around in userspace.

We run alongside `Hotkeys` (pynput) so the user gets whichever path is
available: pynput when permitted, TTY when focused.
"""

from __future__ import annotations

import contextlib
import os
import select
import termios
import threading
import tty
from collections.abc import Callable

# Escape sequences emitted by xterm-family terminals for the function keys.
# F1-F4 use SS3 (ESC O), F5-F12 use CSI (ESC [). Covered: Terminal.app,
# iTerm2, Warp, VS Code integrated terminal, Cursor, kitty, alacritty.
_KEY_SEQ: dict[bytes, str] = {
    b"\x1bOP": "F1",
    b"\x1bOQ": "F2",
    b"\x1bOR": "F3",
    b"\x1bOS": "F4",
    b"\x1b[15~": "F5",
    b"\x1b[17~": "F6",
    b"\x1b[18~": "F7",
    b"\x1b[19~": "F8",
    b"\x1b[20~": "F9",
    b"\x1b[21~": "F10",
    b"\x1b[23~": "F11",
    b"\x1b[24~": "F12",
}
_SORTED = sorted(_KEY_SEQ.items(), key=lambda kv: -len(kv[0]))


class TtyKeys:
    """Reads function keys, Space, and Esc from /dev/tty.

    Use as a context manager — terminal state is restored on exit.
    """

    def __init__(self, on_key: Callable[[str], None]) -> None:
        self._on_key = on_key
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._fd: int | None = None
        self._saved: list | None = None

    def __enter__(self) -> TtyKeys:
        try:
            self._fd = os.open("/dev/tty", os.O_RDONLY | os.O_NOCTTY)
        except OSError:
            return self  # no controlling terminal (CI, piped input) — no-op
        self._saved = termios.tcgetattr(self._fd)
        # cbreak (non-canonical, no echo) keeps SIGINT/Ctrl+C signals working
        # so the user can still escape with Ctrl+C if anything goes wrong.
        tty.setcbreak(self._fd)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._fd is not None and self._saved is not None:
            with contextlib.suppress(OSError):
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
            with contextlib.suppress(OSError):
                os.close(self._fd)
        self._fd = None
        self._saved = None

    def _loop(self) -> None:
        assert self._fd is not None
        buf = bytearray()
        while not self._stop.is_set():
            try:
                r, _, _ = select.select([self._fd], [], [], 0.1)
            except (OSError, ValueError):
                return
            if not r:
                # Timeout: flush a lone Esc that wasn't followed by anything
                if bytes(buf) == b"\x1b":
                    self._on_key("Esc")
                    buf.clear()
                continue
            try:
                data = os.read(self._fd, 64)
            except OSError:
                return
            if not data:
                continue
            buf.extend(data)
            self._drain(buf)

    def _drain(self, buf: bytearray) -> None:
        while buf:
            matched = False
            for seq, name in _SORTED:
                if buf.startswith(seq):
                    self._on_key(name)
                    del buf[: len(seq)]
                    matched = True
                    break
            if matched:
                continue
            first = buf[0]
            if first == 0x20:  # Space
                self._on_key("Space")
                del buf[0]
            elif first in (ord("+"), ord("=")):
                self._on_key("VolUp")
                del buf[0]
            elif first == ord("-"):
                self._on_key("VolDown")
                del buf[0]
            elif first == ord("0"):
                self._on_key("VolMute")
                del buf[0]
            elif first == 0x1B:
                if len(buf) == 1:
                    return  # potential start of a longer ESC sequence — wait
                del buf[0]  # unknown ESC sequence, drop the marker and continue
            else:
                del buf[0]  # any other byte (regular character typed in TUI)
