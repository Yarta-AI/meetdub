"""Audio capture (mic) and playback (BlackHole) using sounddevice.

gpt-realtime-translate expects 24 kHz mono PCM16 little-endian.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 24_000
CHANNELS_IN = 1
DTYPE = "int16"
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000


@dataclass
class DeviceInfo:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float


def list_devices() -> list[DeviceInfo]:
    devices = sd.query_devices()
    return [
        DeviceInfo(
            index=i,
            name=d["name"],
            max_input_channels=d["max_input_channels"],
            max_output_channels=d["max_output_channels"],
            default_samplerate=d["default_samplerate"],
        )
        for i, d in enumerate(devices)
    ]


def find_device(name_substring: str, kind: str) -> DeviceInfo | None:
    needle = name_substring.lower()
    for d in list_devices():
        if needle in d.name.lower():
            if kind == "input" and d.max_input_channels > 0:
                return d
            if kind == "output" and d.max_output_channels > 0:
                return d
    return None


class MicCapture:
    """Captures mic audio into an asyncio queue of 20ms PCM16 frames."""

    def __init__(self, device: int | str | None = None) -> None:
        self.device = device
        self.queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._stream: sd.RawInputStream | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            pass
        data = bytes(indata)
        if self._loop is not None:
            with contextlib.suppress(asyncio.QueueFull):
                self._loop.call_soon_threadsafe(self.queue.put_nowait, data)

    async def __aenter__(self) -> MicCapture:
        self._loop = asyncio.get_running_loop()
        self._stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=FRAME_SAMPLES,
            device=self.device,
            channels=CHANNELS_IN,
            dtype=DTYPE,
            callback=self._callback,
        )
        self._stream.start()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()


class Speaker:
    """Plays PCM16 chunks straight to output devices.

    Matches the OpenAI Realtime cookbook pattern: receive `output_audio.delta`,
    decode base64, write to a sounddevice output stream. No custom buffering.
    """

    def __init__(
        self,
        primary_device: int | str,
        monitor_device: int | str | None = None,
    ) -> None:
        self._primary = sd.RawOutputStream(
            samplerate=SAMPLE_RATE,
            device=primary_device,
            channels=1,
            dtype=DTYPE,
        )
        self._monitor: sd.RawOutputStream | None = None
        if monitor_device is not None:
            self._monitor = sd.RawOutputStream(
                samplerate=SAMPLE_RATE,
                device=monitor_device,
                channels=1,
                dtype=DTYPE,
            )

    def start(self) -> None:
        self._primary.start()
        if self._monitor:
            self._monitor.start()

    def write(self, pcm: bytes) -> None:
        """Send translated audio to BlackHole and (optionally) the monitor."""
        self._primary.write(pcm)
        if self._monitor:
            self._monitor.write(pcm)

    def write_primary(self, pcm: bytes) -> None:
        """Send to BlackHole only (used for attenuated mic passthrough — we don't
        want to also push the user's own raw voice back into their headphones)."""
        self._primary.write(pcm)

    def close(self) -> None:
        self._primary.stop()
        self._primary.close()
        if self._monitor:
            self._monitor.stop()
            self._monitor.close()


def attenuate_pcm16(pcm: bytes, gain: float) -> bytes:
    """Scale int16 PCM samples by a linear gain (0.0 = silence, 1.0 = passthrough).

    Clipping-safe via float32 intermediate.
    """
    if gain <= 0.0:
        return b""
    if gain >= 1.0:
        return pcm
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) * gain
    np.clip(arr, -32768, 32767, out=arr)
    return arr.astype(np.int16).tobytes()


def rms_dbfs(pcm: bytes) -> float:
    """Return RMS level of PCM16 buffer in dBFS (silent ≈ -inf, full = 0)."""
    if not pcm:
        return -120.0
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    if arr.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(arr * arr)) + 1e-12)
    return 20.0 * np.log10(rms)
