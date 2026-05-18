import pytest

from meetdub.languages import BY_CODE, BY_HOTKEY, LANGUAGES, resolve


def test_resolve_known_code():
    lang = resolve("ja")
    assert lang.code == "ja"
    assert lang.name == "Japanese"


def test_resolve_is_case_insensitive():
    assert resolve("JA").code == "ja"
    assert resolve("  EN  ").code == "en"


def test_resolve_unknown_raises():
    with pytest.raises(ValueError, match="Unsupported language"):
        resolve("klingon")


def test_every_language_has_unique_code():
    codes = [lang.code for lang in LANGUAGES]
    assert len(codes) == len(set(codes))


def test_hotkeys_unique_and_function_keys():
    hotkeys = [lang.hotkey for lang in LANGUAGES if lang.hotkey]
    assert len(hotkeys) == len(set(hotkeys))
    for hk in hotkeys:
        assert hk.startswith("F") and 2 <= int(hk[1:]) <= 12


def test_indexes_consistent():
    for code, lang in BY_CODE.items():
        assert lang.code == code
    for hotkey, lang in BY_HOTKEY.items():
        assert lang.hotkey == hotkey
