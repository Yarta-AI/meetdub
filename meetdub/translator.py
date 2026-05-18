"""WebSocket client for gpt-realtime-translate (OpenAI direct or Azure OpenAI).

Wire protocol (same for both backends — only URL + auth header differ):
  send:       session.update                  (configure target language + noise reduction)
              session.input_audio_buffer.append  (base64 PCM16 @ 24kHz)
  receive:    session.output_audio.delta      (base64 PCM16 chunk, ~200ms)
              session.output_transcript.delta (translated text)
              session.input_transcript.delta  (source text, original language)
              error                           (anything went wrong)

Voice adaptation is dynamic: the model preserves the source speaker's tone,
pitch, and speaking style — there is no `voice` parameter to set.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

import websockets

from meetdub.backend import Backend

TRANSCRIBE_MODEL = "gpt-realtime-whisper"

# May 2026 pricing — keep in sync with https://openai.com/api/pricing/
USD_PER_MINUTE = 0.034

log = logging.getLogger(__name__)


@dataclass
class TranslatorEvents:
    on_audio: Callable[[bytes], None]
    on_input_text: Callable[[str, bool], None]
    on_output_text: Callable[[str, bool], None]
    on_status: Callable[[str], None]
    on_error: Callable[[str], None]


class RealtimeTranslator:
    def __init__(
        self,
        backend: Backend,
        target_language: str,
        events: TranslatorEvents,
        noise_reduction: str = "near_field",
    ) -> None:
        self._backend = backend
        self._target_language = target_language
        self._events = events
        self._noise_reduction = noise_reduction
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._send_lock = asyncio.Lock()
        self._connected = asyncio.Event()
        self._audio_seconds_sent = 0.0

    @property
    def cost_usd(self) -> float:
        return (self._audio_seconds_sent / 60.0) * USD_PER_MINUTE

    async def __aenter__(self) -> RealtimeTranslator:
        self._ws = await websockets.connect(
            self._backend.ws_url,
            additional_headers=self._backend.headers,
            max_size=None,
            ping_interval=20,
        )
        await self._configure_session(self._target_language)
        self._connected.set()
        self._events.on_status(
            f"connected · {self._backend.describe()} · target={self._target_language}"
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._ws is not None:
            await self._ws.close()

    async def _configure_session(self, target_language: str) -> None:
        assert self._ws is not None
        payload = {
            "type": "session.update",
            "session": {
                "audio": {
                    "input": {
                        "transcription": {"model": TRANSCRIBE_MODEL},
                        "noise_reduction": {"type": self._noise_reduction},
                    },
                    "output": {"language": target_language},
                },
            },
        }
        await self._ws.send(json.dumps(payload))

    async def switch_language(self, target_language: str) -> None:
        async with self._send_lock:
            self._target_language = target_language
            await self._configure_session(target_language)
            self._events.on_status(f"language → {target_language}")

    async def send_audio(self, pcm16: bytes) -> None:
        if self._ws is None:
            return
        b64 = base64.b64encode(pcm16).decode("ascii")
        payload = {"type": "session.input_audio_buffer.append", "audio": b64}
        async with self._send_lock:
            await self._ws.send(json.dumps(payload))
        # 24kHz PCM16 = 48000 bytes/sec
        self._audio_seconds_sent += len(pcm16) / 48_000.0

    async def receive_loop(self) -> None:
        assert self._ws is not None
        async for raw in self._ws:
            try:
                evt = json.loads(raw)
            except json.JSONDecodeError:
                continue
            await self._dispatch(evt)

    async def _dispatch(self, evt: dict) -> None:
        etype = evt.get("type", "")
        log.debug("event: %s", etype)
        # Audio chunk — match both /translations (session.output_audio.delta)
        # and /realtime (response.audio.delta) shapes.
        if (
            etype.endswith("output_audio.delta")
            or etype.endswith("audio.delta")
            or etype == "response.audio.delta"
        ):
            audio_b64 = evt.get("delta") or evt.get("audio") or ""
            if audio_b64:
                self._events.on_audio(base64.b64decode(audio_b64))
        elif (
            etype.endswith("output_transcript.delta") or etype == "response.audio_transcript.delta"
        ):
            delta = evt.get("delta", "")
            if delta:
                self._events.on_output_text(delta, False)
        elif etype.endswith("output_transcript.done") or etype == "response.audio_transcript.done":
            self._events.on_output_text("", True)
        elif (
            etype.endswith("input_transcript.delta")
            or etype == "conversation.item.input_audio_transcription.delta"
        ):
            delta = evt.get("delta", "")
            if delta:
                self._events.on_input_text(delta, False)
        elif (
            etype.endswith("input_transcript.done")
            or etype == "conversation.item.input_audio_transcription.completed"
        ):
            text = evt.get("transcript", "")
            if text:
                self._events.on_input_text(text, False)
            self._events.on_input_text("", True)
        elif etype == "error":
            err = evt.get("error") or {}
            msg = err.get("message") or str(evt)
            self._events.on_error(f"session error: {msg}")
        elif etype.endswith(".failed"):
            # Per-utterance failure — common when VAD chops too aggressively
            # or speech is too quiet. Session stays alive; just log it.
            err = evt.get("error") or {}
            msg = err.get("message") or "(no message)"
            log.warning("%s · %s", etype, msg)
        elif etype == "session.created" or etype == "session.updated":
            self._events.on_status(f"session ready · {etype}")
        elif etype == "input_audio_buffer.speech_started" or etype.endswith("speech_started"):
            self._events.on_status("listening…")
        else:
            log.info("unhandled event: %s · keys=%s", etype, list(evt.keys()))


async def stream_translation(
    backend: Backend,
    target_language: str,
    audio_source: AsyncIterator[bytes],
    events: TranslatorEvents,
    noise_reduction: str = "near_field",
) -> RealtimeTranslator:
    """Convenience runner: pipes audio_source → translator and dispatches events.

    Returns the translator so the caller can call switch_language() at runtime.
    """
    translator = RealtimeTranslator(backend, target_language, events, noise_reduction)
    await translator.__aenter__()

    async def pump() -> None:
        async for chunk in audio_source:
            await translator.send_audio(chunk)

    asyncio.create_task(translator.receive_loop())
    asyncio.create_task(pump())
    return translator
