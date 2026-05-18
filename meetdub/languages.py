"""Supported output languages for gpt-realtime-translate.

The model accepts 70+ input languages with auto-detection and outputs
to the 13 languages listed below.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    native: str
    hotkey: str


LANGUAGES: tuple[Language, ...] = (
    Language("en", "English", "English", "F2"),
    Language("ja", "Japanese", "日本語", "F3"),
    Language("es", "Spanish", "Español", "F4"),
    Language("fr", "French", "Français", "F5"),
    Language("de", "German", "Deutsch", "F6"),
    Language("zh", "Chinese", "中文", "F7"),
    Language("ko", "Korean", "한국어", "F8"),
    Language("pt", "Portuguese", "Português", "F9"),
    Language("it", "Italian", "Italiano", "F10"),
    Language("hi", "Hindi", "हिन्दी", "F11"),
    Language("ru", "Russian", "Русский", "F12"),
    Language("id", "Indonesian", "Bahasa Indonesia", ""),
    Language("vi", "Vietnamese", "Tiếng Việt", ""),
)

BY_CODE: dict[str, Language] = {lang.code: lang for lang in LANGUAGES}
BY_HOTKEY: dict[str, Language] = {lang.hotkey: lang for lang in LANGUAGES if lang.hotkey}


def resolve(code: str) -> Language:
    code = code.lower().strip()
    if code not in BY_CODE:
        valid = ", ".join(sorted(BY_CODE))
        raise ValueError(f"Unsupported language '{code}'. Supported: {valid}")
    return BY_CODE[code]
