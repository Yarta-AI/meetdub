import numpy as np

from meetdub.vad import VAD


def _silence_frame(samples: int = 480) -> bytes:
    return np.zeros(samples, dtype=np.int16).tobytes()


def _tone_frame(samples: int = 480, amplitude: float = 0.5) -> bytes:
    t = np.arange(samples) / 24_000
    wave = (np.sin(2 * np.pi * 440 * t) * amplitude * 32767).astype(np.int16)
    return wave.tobytes()


def test_silence_not_speech_after_hangover_drains():
    vad = VAD(threshold_dbfs=-45.0, hangover_frames=3)
    # Fill the hangover with silence
    for _ in range(5):
        assert not vad.is_speech(_silence_frame())


def test_tone_above_threshold_is_speech():
    vad = VAD(threshold_dbfs=-45.0, hangover_frames=3)
    assert vad.is_speech(_tone_frame(amplitude=0.5))


def test_hangover_keeps_speech_true_briefly():
    vad = VAD(threshold_dbfs=-45.0, hangover_frames=5)
    assert vad.is_speech(_tone_frame())  # speech detected
    # Following silence frames are within hangover window — still speech
    for _ in range(4):
        assert vad.is_speech(_silence_frame())
    # After hangover drains, silence should register as non-speech
    for _ in range(5):
        vad.is_speech(_silence_frame())
    assert not vad.is_speech(_silence_frame())


def test_empty_buffer_is_not_speech():
    vad = VAD()
    assert vad.is_speech(b"") is False
