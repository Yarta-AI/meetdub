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


class _AudioSink:
    """One sounddevice output stream fed by a background writer thread.

    Why a thread: sd.RawOutputStream.write() blocks until the device buffer
    has space. Calling it from the asyncio loop (where the WS receive task
    lives) stalls every other coroutine, so audio events pile up and arrive
    in bursts — the classic "ぷつぷつ" symptom. We push chunks to a queue
    and let a dedicated thread drain them; asyncio never waits on audio I/O.

    The queue is bounded (~1 s) so a stuck device doesn't grow memory; on
    overflow we drop the oldest chunk, since lagging by more than a second
    is already worse than a dropout.
    """

    QUEUE_MAX = 50  # ~10s of 200ms chunks; we never approach this in healthy state

    def __init__(self, device: int | str, latency: float | str = "low") -> None:
        """latency: 'low' (device minimum, ~10-20ms on macOS — closest to real-time),
        'high' (smoothest, ~150-200ms), or an explicit seconds value.

        The cookbook doesn't address this trade-off; we default to 'low' because
        translation already adds 1-2s of inherent latency, and any playback
        latency stacks on top. If you hear stutter, bump via --latency-ms."""
        import queue
        import threading

        self._stream = sd.RawOutputStream(
            samplerate=SAMPLE_RATE,
            device=device,
            channels=1,
            dtype=DTYPE,
            latency=latency,
        )
        self._stream.start()
        self._q: queue.Queue[bytes] = queue.Queue(maxsize=self.QUEUE_MAX)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()

    def write(self, pcm: bytes) -> None:
        import queue

        try:
            self._q.put_nowait(pcm)
        except queue.Full:
            # Drop oldest to keep latency bounded.
            with contextlib.suppress(queue.Empty):
                self._q.get_nowait()
            with contextlib.suppress(queue.Full):
                self._q.put_nowait(pcm)

    def _drain(self) -> None:
        import queue

        while not self._stop.is_set():
            try:
                pcm = self._q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._stream.write(pcm)
            except Exception:
                # Device may be torn down during shutdown; bail quietly.
                return

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1)
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass


class Speaker:
    """Plays PCM16 chunks to one or two output devices without blocking the
    asyncio loop. Receive `output_audio.delta`, decode base64, hand off here."""

    def __init__(
        self,
        primary_device: int | str,
        monitor_device: int | str | None = None,
        latency: float | str = "low",
    ) -> None:
        self._primary = _AudioSink(primary_device, latency=latency)
        self._monitor: _AudioSink | None = (
            _AudioSink(monitor_device, latency=latency) if monitor_device is not None else None
        )

    def start(self) -> None:
        pass  # sinks start their own streams + threads in __init__

    def write(self, pcm: bytes) -> None:
        """Send translated audio to BlackHole and (optionally) the monitor."""
        self._primary.write(pcm)
        if self._monitor:
            self._monitor.write(pcm)

    def write_primary(self, pcm: bytes) -> None:
        """Send to BlackHole only — used for attenuated mic passthrough so we
        don't double the user's own voice in their headphones."""
        self._primary.write(pcm)

    def close(self) -> None:
        self._primary.close()
        if self._monitor:
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
