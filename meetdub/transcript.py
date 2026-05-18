"""Bilingual transcript writer — saves source + target side-by-side as Markdown."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from meetdub.config import TRANSCRIPTS_DIR


class TranscriptWriter:
    def __init__(self, target_language: str) -> None:
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path: Path = TRANSCRIPTS_DIR / f"meetdub_{stamp}_{target_language}.md"
        self._fp = self.path.open("w", encoding="utf-8")
        self._fp.write(f"# meetdub session — {stamp}\n\n")
        self._fp.write(f"Target language: `{target_language}`\n\n")
        self._fp.write("| time | source | translation |\n|---|---|---|\n")
        self._source_buf = ""
        self._target_buf = ""

    def append_source(self, text: str, done: bool) -> None:
        self._source_buf += text
        if done:
            self._flush()

    def append_target(self, text: str, done: bool) -> None:
        self._target_buf += text
        if done:
            self._flush()

    def _flush(self) -> None:
        if not (self._source_buf or self._target_buf):
            return
        ts = datetime.now().strftime("%H:%M:%S")
        src = self._source_buf.replace("|", "\\|").replace("\n", " ").strip()
        tgt = self._target_buf.replace("|", "\\|").replace("\n", " ").strip()
        self._fp.write(f"| {ts} | {src} | {tgt} |\n")
        self._fp.flush()
        self._source_buf = ""
        self._target_buf = ""

    def close(self) -> None:
        self._flush()
        self._fp.close()
