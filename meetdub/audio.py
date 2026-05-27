"""Audio capture (mic) and playback (BlackHole) using sounddevice.

gpt-realtime-translate expects 24 kHz mono PCM16 little-endian.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

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


def _device_rate(device: int | str) -> int:
    try:
        return int(sd.query_devices(device)["default_samplerate"]) or SAMPLE_RATE
    except Exception:
        return SAMPLE_RATE


def _is_virtual_loopback(device: int | str) -> bool:
    """A loopback / virtual-mic device exposes BOTH input and output channels
    (BlackHole 2ch, Loopback, "Microsoft Teams Audio"). Real speakers and
    headphones are output-only. We use this to decide which sink a device
    needs — only virtual mics require the continuous-signal treatment."""
    try:
        info = sd.query_devices(device)
        return info["max_input_channels"] > 0 and info["max_output_channels"] > 0
    except Exception:
        return False


class _DirectSink:
    """Low-latency output for a *real* device (headphones, speakers).

    A background thread drains a queue and does blocking sd writes. Between
    utterances the queue is simply empty and nothing is written — the gap is
    real silence, which is exactly what you want on a speaker. Whole 200ms
    chunks are written atomically, so any underrun lands on a chunk boundary
    (where the model's audio is already near-silent) rather than mid-word.

    This is the original behaviour that sounded clean on AirPods. No jitter
    buffer, no added latency. write() only does a non-blocking queue put, so
    the asyncio loop is never stalled by the blocking sd write.
    """

    QUEUE_MAX = 64

    def __init__(self, device: int | str, latency: float | str = "low") -> None:
        import queue
        import threading

        self._device_rate = _device_rate(device)
        self._stream = sd.RawOutputStream(
            samplerate=self._device_rate,
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
            if self._device_rate != SAMPLE_RATE:
                pcm = resample_pcm16(pcm, SAMPLE_RATE, self._device_rate)
            try:
                self._stream.write(pcm)
            except Exception:
                return

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1)
        with contextlib.suppress(Exception):
            self._stream.stop()
            self._stream.close()


class _VirtualMicSink:
    """Continuous output for a *virtual mic* (BlackHole) feeding another app.

    BlackHole is a microphone as far as Teams is concerned, and a real mic
    never stops — it emits silence when nobody speaks. A write-when-we-have-
    data stream leaves holes between translated chunks; Teams' pipeline reads
    those holes as a mic cutting in and out → choppy, garbled downstream.

    So the stream runs forever via a PortAudio callback: it pulls from `_buf`
    and emits silence on underrun rather than stalling. A small jitter buffer
    smooths chunk-boundary timing; clicks that slip through are absorbed by
    Teams' own downstream jitter buffer, so we keep the cushion modest to
    stay close to real time.
    """

    JITTER_MS = 10
    IDLE_RESET_MS = 100
    FADE_MS = 5
    OUTPUT_GAIN = 0.2

    def __init__(
        self,
        device: int | str,
        latency: float | str = "low",
        jitter_ms: int | None = None,
        gain: float | None = None,
    ) -> None:
        import threading

        jitter_ms = self.JITTER_MS if jitter_ms is None else jitter_ms
        self._gain = self.OUTPUT_GAIN if gain is None else gain
        self._device_rate = _device_rate(device)
        self._jitter_bytes = int(self._device_rate * 2 * jitter_ms / 1000)
        self._idle_reset_bytes = int(self._device_rate * 2 * self.IDLE_RESET_MS / 1000)
        self._fade_samples = max(1, int(self._device_rate * self.FADE_MS / 1000))
        self._max_bytes = self._device_rate * 2 * 4  # ~4s cap
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._armed = False
        self._idle_bytes = 0
        self._last_sample = 0
        self._queued_tail_sample = 0
        self._has_queued_tail = False

        self._stream = sd.RawOutputStream(
            samplerate=self._device_rate,
            device=device,
            channels=1,
            dtype=DTYPE,
            latency=latency,
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, outdata, frames, time_info, status) -> None:
        need = frames * 2
        with self._lock:
            if not self._armed:
                if len(self._buf) >= self._jitter_bytes:
                    self._armed = True
                else:
                    outdata[:] = b"\x00" * need
                    self._last_sample = 0
                    return
            have = len(self._buf)
            if have >= need:
                outdata[:] = self._declick_block(bytes(self._buf[:need]))
                del self._buf[:need]
                self._idle_bytes = 0
            else:
                block = bytearray(need)
                block[:have] = bytes(self._buf)
                self._fade_out_tail(block, have)
                outdata[:] = self._declick_block(bytes(block))
                self._buf.clear()
                silent_bytes = need - have if have else need
                self._idle_bytes += silent_bytes
                if self._idle_bytes >= self._idle_reset_bytes:
                    self._armed = False

    def _declick_block(self, pcm: bytes) -> bytes:
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return pcm
        n = min(self._fade_samples, samples.size)
        offset = self._last_sample - samples[0]
        if offset:
            samples[:n] += offset * np.linspace(1.0, 0.0, n, dtype=np.float32)
        np.clip(np.round(samples), -32768, 32767, out=samples)
        out = samples.astype(np.int16)
        self._last_sample = int(out[-1])
        return out.tobytes()

    def _fade_out_tail(self, block: bytearray, audio_bytes: int) -> None:
        if audio_bytes <= 0:
            return
        samples = np.frombuffer(block, dtype=np.int16, count=audio_bytes // 2).astype(np.float32)
        n = min(self._fade_samples, samples.size)
        samples[-n:] *= np.linspace(1.0, 0.0, n, dtype=np.float32)
        np.clip(np.round(samples), -32768, 32767, out=samples)
        block[:audio_bytes] = samples.astype(np.int16).tobytes()

    def write(self, pcm: bytes) -> None:
        if self._device_rate != SAMPLE_RATE:
            pcm = resample_pcm16(pcm, SAMPLE_RATE, self._device_rate)
        pcm = attenuate_pcm16(pcm, self._gain)
        with self._lock:
            pcm = self._declick_append(pcm)
            self._buf.extend(pcm)
            if pcm:
                self._idle_bytes = 0
                self._queued_tail_sample = int(np.frombuffer(pcm, dtype=np.int16)[-1])
                self._has_queued_tail = True
            if len(self._buf) > self._max_bytes:
                del self._buf[: len(self._buf) - self._max_bytes]

    def _declick_append(self, pcm: bytes) -> bytes:
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return pcm

        if self._buf:
            previous = int(np.frombuffer(self._buf[-2:], dtype=np.int16)[0])
        elif self._has_queued_tail:
            previous = self._queued_tail_sample
        else:
            previous = self._last_sample

        n = min(self._fade_samples, samples.size)
        offset = previous - samples[0]
        if offset:
            samples[:n] += offset * np.linspace(1.0, 0.0, n, dtype=np.float32)
        np.clip(np.round(samples), -32768, 32767, out=samples)
        return samples.astype(np.int16).tobytes()

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._stream.stop()
            self._stream.close()


def _make_sink(
    device: int | str,
    latency: float | str,
    *,
    force_continuous: bool = False,
    jitter_ms: int | None = None,
    gain: float | None = None,
):
    """Virtual mics need the continuous callback sink; real devices get the
    low-latency direct sink."""
    if force_continuous or _is_virtual_loopback(device):
        log.info(
            "audio sink: continuous device=%r latency=%r jitter_ms=%s gain=%s idle_reset_ms=%s fade_ms=%s",
            device,
            latency,
            _VirtualMicSink.JITTER_MS if jitter_ms is None else jitter_ms,
            _VirtualMicSink.OUTPUT_GAIN if gain is None else gain,
            _VirtualMicSink.IDLE_RESET_MS,
            _VirtualMicSink.FADE_MS,
        )
        return _VirtualMicSink(device, latency=latency, jitter_ms=jitter_ms, gain=gain)
    log.info("audio sink: direct device=%r latency=%r", device, latency)
    return _DirectSink(device, latency=latency)


class Speaker:
    """Plays PCM16 chunks to one or two output devices.

    The output device is auto-classified: a virtual mic (BlackHole) gets the
    continuous callback sink so Teams sees an unbroken signal; a real device
    (headphones, speakers) gets the low-latency direct sink. Receive
    `output_audio.delta`, decode base64, hand off here.
    """

    def __init__(
        self,
        primary_device: int | str,
        monitor_device: int | str | None = None,
        latency: float | str = "low",
        sync_monitor: bool = False,
        virtual_jitter_ms: int | None = None,
        virtual_gain: float | None = None,
    ) -> None:
        primary_is_virtual = _is_virtual_loopback(primary_device)
        self._primary = _make_sink(
            primary_device,
            latency,
            jitter_ms=virtual_jitter_ms,
            gain=virtual_gain,
        )
        self._monitor = (
            _make_sink(
                monitor_device,
                latency,
                force_continuous=sync_monitor and primary_is_virtual,
                jitter_ms=virtual_jitter_ms,
                gain=virtual_gain,
            )
            if monitor_device is not None
            else None
        )

    def start(self) -> None:
        pass  # sinks start their own streams in __init__

    def write(self, pcm: bytes) -> None:
        """Send translated audio to the primary output and (optionally) the monitor."""
        self._primary.write(pcm)
        if self._monitor:
            self._monitor.write(pcm)

    def write_primary(self, pcm: bytes) -> None:
        """Send to the primary output only — used for attenuated mic passthrough
        so we don't double the user's own voice in their headphones."""
        self._primary.write(pcm)

    def close(self) -> None:
        self._primary.close()
        if self._monitor:
            self._monitor.close()


def resample_pcm16(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Resample mono int16 PCM from src_rate to dst_rate via linear interpolation.

    Linear interp is more than enough for speech upsampling (e.g. 24k→48k for
    BlackHole). It introduces mild high-frequency rolloff but no artefacts —
    unlike a sample-rate mismatch, which garbles the audio outright.
    """
    if src_rate == dst_rate or not pcm:
        return pcm
    src = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    if src.size == 0:
        return pcm
    n_dst = int(round(src.size * dst_rate / src_rate))
    if n_dst <= 0:
        return b""
    positions = np.linspace(0.0, src.size - 1, n_dst)
    dst = np.interp(positions, np.arange(src.size), src)
    # Round (not truncate) and clip before narrowing to int16 — avoids
    # quantisation bias and any chance of an overflow wrap.
    dst = np.clip(np.round(dst), -32768, 32767)
    return dst.astype(np.int16).tobytes()


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
