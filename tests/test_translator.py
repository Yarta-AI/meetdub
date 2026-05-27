import asyncio

from meetdub.backend import Backend
from meetdub.translator import RealtimeTranslator, TranslatorEvents


def _translator(input_events: list[tuple[str, bool]], output_events: list[tuple[str, bool]]):
    events = TranslatorEvents(
        on_audio=lambda _: None,
        on_input_text=lambda text, done: input_events.append((text, done)),
        on_output_text=lambda text, done: output_events.append((text, done)),
        on_status=lambda _: None,
        on_error=lambda _: None,
    )
    return RealtimeTranslator(Backend("test", "wss://example.test", {}), "ja", events)


def test_translation_session_input_transcript_delta_reaches_source_caption():
    input_events: list[tuple[str, bool]] = []
    output_events: list[tuple[str, bool]] = []
    translator = _translator(input_events, output_events)

    asyncio.run(
        translator._dispatch(
            {
                "type": "session.input_transcript.delta",
                "item_id": "item_1",
                "delta": "Hello",
            }
        )
    )
    asyncio.run(
        translator._dispatch(
            {
                "type": "session.input_transcript.done",
                "item_id": "item_1",
                "transcript": "Hello",
            }
        )
    )

    assert input_events == [("Hello", False), ("", True)]
    assert output_events == []


def test_translation_session_input_audio_transcription_delta_reaches_source_caption():
    input_events: list[tuple[str, bool]] = []
    output_events: list[tuple[str, bool]] = []
    translator = _translator(input_events, output_events)

    asyncio.run(
        translator._dispatch(
            {
                "type": "session.input_audio_transcription.delta",
                "item_id": "item_1",
                "delta": "Source",
            }
        )
    )
    asyncio.run(
        translator._dispatch(
            {
                "type": "session.input_audio_transcription.completed",
                "item_id": "item_1",
                "transcript": "Source",
            }
        )
    )

    assert input_events == [("Source", False), ("", True)]
    assert output_events == []


def test_translation_session_input_transcript_completed_without_delta_is_displayed():
    input_events: list[tuple[str, bool]] = []
    output_events: list[tuple[str, bool]] = []
    translator = _translator(input_events, output_events)

    asyncio.run(
        translator._dispatch(
            {
                "type": "session.input_transcript.completed",
                "item_id": "item_1",
                "transcript": "こんにちは",
            }
        )
    )

    assert input_events == [("こんにちは", False), ("", True)]
    assert output_events == []


def test_realtime_input_audio_transcription_completed_without_delta_is_displayed():
    input_events: list[tuple[str, bool]] = []
    output_events: list[tuple[str, bool]] = []
    translator = _translator(input_events, output_events)

    asyncio.run(
        translator._dispatch(
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "item_id": "item_1",
                "transcript": "Testing source captions",
            }
        )
    )

    assert input_events == [("Testing source captions", False), ("", True)]
    assert output_events == []
