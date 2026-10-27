import pytest

from texts import TEXTS

LANGUAGES = ["en", "he"]


@pytest.mark.parametrize("key", list(TEXTS))
def test_every_text_exists_in_every_language(key):
    for language in LANGUAGES:
        assert TEXTS[key].get(language), f"{key!r} has no {language} text"


@pytest.mark.parametrize("key", list(TEXTS))
def test_both_languages_use_the_same_placeholders(key):
    import string

    def names(text: str) -> set[str]:
        return {field for _, field, _, _ in string.Formatter().parse(text) if field}

    assert names(TEXTS[key]["en"]) == names(TEXTS[key]["he"]), key
