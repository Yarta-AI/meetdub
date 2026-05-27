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
        self._input_transcript_items: set[str] = set()
        self._output_transcript_items: set[str] = set()

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
                    "output": {"language": target_language},
                },
            },
        }
        await self._ws.send(json.dumps(payload))

    async def switch_language(self, target_language: str) -> None:
        async with self._send_lock:
            self._target_language = target_language
            await self._clear_input_audio_buffer()
            await self._configure_session(target_language)
            self._events.on_status(f"language → {target_language}")

    async def _clear_input_audio_buffer(self) -> None:
        if self._ws is None:
            return
        await self._ws.send(json.dumps({"type": "session.input_audio_buffer.clear"}))

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
        if "transcript" in etype or "transcription" in etype:
            log.debug("transcript event: %s", evt)
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
        elif self._is_output_transcript_delta(etype):
            delta = _event_text(evt)
            if delta:
                _remember_item(self._output_transcript_items, evt)
                self._events.on_output_text(delta, False)
        elif self._is_output_transcript_done(etype):
            text = _event_text(evt)
            if text and not _item_was_seen(self._output_transcript_items, evt):
                self._events.on_output_text(text, False)
            _forget_item(self._output_transcript_items, evt)
            self._events.on_output_text("", True)
        elif self._is_input_transcript_delta(etype):
            delta = _event_text(evt)
            if delta:
                _remember_item(self._input_transcript_items, evt)
                self._events.on_input_text(delta, False)
        elif self._is_input_transcript_done(etype):
            text = _event_text(evt)
            if text and not _item_was_seen(self._input_transcript_items, evt):
                self._events.on_input_text(text, False)
            _forget_item(self._input_transcript_items, evt)
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

    @staticmethod
    def _is_input_transcript_delta(etype: str) -> bool:
        return etype in {
            "session.input_audio_transcription.delta",
            "session.input_transcript.delta",
            "conversation.item.input_audio_transcription.delta",
        } or etype.endswith((".input_transcript.delta", ".input_audio_transcription.delta"))

    @staticmethod
    def _is_input_transcript_done(etype: str) -> bool:
        return etype in {
            "session.input_audio_transcription.done",
            "session.input_audio_transcription.completed",
            "session.input_transcript.done",
            "session.input_transcript.completed",
            "conversation.item.input_audio_transcription.completed",
        } or etype.endswith(
            (
                ".input_transcript.done",
                ".input_transcript.completed",
                ".input_audio_transcription.done",
                ".input_audio_transcription.completed",
            )
        )

    @staticmethod
    def _is_output_transcript_delta(etype: str) -> bool:
        return etype in {
            "session.output_transcript.delta",
            "response.audio_transcript.delta",
            "response.output_audio_transcript.delta",
        } or etype.endswith(".output_transcript.delta")

    @staticmethod
    def _is_output_transcript_done(etype: str) -> bool:
        return etype in {
            "session.output_transcript.done",
            "session.output_transcript.completed",
            "response.audio_transcript.done",
            "response.output_audio_transcript.done",
        } or etype.endswith((".output_transcript.done", ".output_transcript.completed"))


def _event_text(evt: dict) -> str:
    return evt.get("delta") or evt.get("transcript") or evt.get("text") or ""


def _item_key(evt: dict) -> str | None:
    item_id = evt.get("item_id") or evt.get("response_id") or evt.get("event_id")
    return str(item_id) if item_id else None


def _remember_item(items: set[str], evt: dict) -> None:
    item_id = _item_key(evt)
    if item_id:
        items.add(item_id)


def _item_was_seen(items: set[str], evt: dict) -> bool:
    item_id = _item_key(evt)
    return bool(item_id and item_id in items)


def _forget_item(items: set[str], evt: dict) -> None:
    item_id = _item_key(evt)
    if item_id:
        items.discard(item_id)


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
