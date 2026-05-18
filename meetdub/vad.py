"""RMS-based voice activity detector.

Cheap energy gate: skip frames quieter than `threshold_dbfs` so we don't pay
to stream silence. Keeps a small hangover so trailing low-energy phonemes
(soft consonants at sentence ends) still get through.

Why not webrtcvad? It's unmaintained since 2017 and breaks on Python 3.14+
(no `pkg_resources`). For a meeting microphone in front of a deliberate
speaker, simple RMS gating is more than adequate.
"""

from __future__ import annotations

from collections import deque

import numpy as np


class VAD:
    def __init__(
        self,
        threshold_dbfs: float = -55.0,
        hangover_frames: int = 25,
    ) -> None:
        self._threshold = threshold_dbfs
        self._tail: deque[bool] = deque(maxlen=hangover_frames)

    def is_speech(self, pcm16: bytes) -> bool:
        if not pcm16:
            return False
        arr = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(arr * arr)) + 1e-12)
        dbfs = 20.0 * np.log10(rms)
        speech = dbfs > self._threshold
        self._tail.append(speech)
        return any(self._tail)
