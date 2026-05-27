import threading

from meetdub import audio


def _virtual_sink_without_stream() -> audio._VirtualMicSink:
    sink = audio._VirtualMicSink.__new__(audio._VirtualMicSink)
    sink._device_rate = audio.SAMPLE_RATE
    sink._jitter_bytes = int(audio.SAMPLE_RATE * 2 * audio._VirtualMicSink.JITTER_MS / 1000)
    sink._idle_reset_bytes = int(
        audio.SAMPLE_RATE * 2 * audio._VirtualMicSink.IDLE_RESET_MS / 1000
    )
    sink._fade_samples = max(1, int(audio.SAMPLE_RATE * audio._VirtualMicSink.FADE_MS / 1000))
    sink._max_bytes = audio.SAMPLE_RATE * 2 * 4
    sink._buf = bytearray()
    sink._lock = threading.Lock()
    sink._armed = True
    sink._idle_bytes = 0
    sink._last_sample = 0
    sink._queued_tail_sample = 0
    sink._has_queued_tail = False
    return sink


def test_virtual_mic_does_not_rearm_after_short_underrun():
    sink = _virtual_sink_without_stream()
    frames = audio.FRAME_SAMPLES
    need = frames * 2
    chunk = b"\x11\x22" * frames

    sink._buf.extend(chunk[: need // 2])
    out = bytearray(need)
    sink._callback(out, frames, None, None)

    assert sink._armed is True

    sink.write(chunk)
    out = bytearray(need)
    sink._callback(out, frames, None, None)

    assert bytes(out)


def test_virtual_mic_rearms_after_long_idle():
    sink = _virtual_sink_without_stream()
    frames = audio.FRAME_SAMPLES
    need = frames * 2

    for _ in range(sink._idle_reset_bytes // need):
        sink._callback(bytearray(need), frames, None, None)

    assert sink._armed is False

    sink.write(b"\x11\x22" * frames)
    out = bytearray(need)
    sink._callback(out, frames, None, None)

    assert bytes(out) == b"\x00" * need
