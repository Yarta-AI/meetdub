"""Global hotkeys via pynput.

F2–F12: hot-swap target language
Space (hold): push-to-translate (only while held)
+ / -:  raise / lower passthrough gain (original mic mix into BlackHole)
0:      mute passthrough
Esc:    quit

pynput needs Accessibility permission on macOS. We surface that in `doctor`.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from pynput import keyboard

from meetdub.languages import BY_HOTKEY


class Hotkeys:
    def __init__(
        self,
        on_language: Callable[[str], None],
        on_quit: Callable[[], None],
        on_push_to_translate: Callable[[bool], None] | None = None,
        on_volume: Callable[[str], None] | None = None,
    ) -> None:
        self._on_language = on_language
        self._on_quit = on_quit
        self._on_ptt = on_push_to_translate
        self._on_volume = on_volume
        self._listener: keyboard.Listener | None = None
        self._space_down = False
        self._stop = threading.Event()

    def _press(self, key) -> None:
        try:
            name = key.name if hasattr(key, "name") else None
        except AttributeError:
            name = None
        if name and name.upper() in {f"F{i}" for i in range(2, 13)}:
            lang = BY_HOTKEY.get(name.upper())
            if lang:
                self._on_language(lang.code)
            return
        if key == keyboard.Key.esc:
            self._on_quit()
            self._stop.set()
            return
        if key == keyboard.Key.space and self._on_ptt and not self._space_down:
            self._space_down = True
            self._on_ptt(True)
            return
        if self._on_volume and hasattr(key, "char") and key.char:
            ch = key.char
            if ch in ("+", "="):
                self._on_volume("VolUp")
            elif ch == "-":
                self._on_volume("VolDown")
            elif ch == "0":
                self._on_volume("VolMute")

    def _release(self, key) -> None:
        if key == keyboard.Key.space and self._on_ptt and self._space_down:
            self._space_down = False
            self._on_ptt(False)

    def __enter__(self) -> Hotkeys:
        self._listener = keyboard.Listener(on_press=self._press, on_release=self._release)
        self._listener.start()
        return self

    def __exit__(self, *exc) -> None:
        if self._listener:
            self._listener.stop()
