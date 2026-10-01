import pytest

from anu_unicode.telugu import aksharas, denormalise, is_telugu_word, normalise


def test_aksharas_keep_conjuncts_and_split_modifiers() -> None:
    assert aksharas("క్షిప్తం") == ["క్షి", "ప్త", "ం"]


def test_is_telugu_word_rejects_digits_and_latin() -> None:
    assert is_telugu_word("మహాభారతము")
    assert not is_telugu_word("29")
    assert not is_telugu_word("abc")


@pytest.mark.parametrize(
    ("anu_order", "unicode_order"),
    [
        ("జరతా్కరుని", "జరత్కారుని"),
        ("కచే్ఛదము", "కచ్ఛేదము"),
        ("కణ్వ", "కణ్వ"),
        ("సు్ట్ర", "స్ట్రు"),
        ("విస్త ృతము", "విస్తృతము"),
        ("రాక 29", "రాక 29"),
        ("◌్రతెంపు", "త్రెంపు"),
        ("శత◌్రభాతల", "శతభ్రాతల"),
        ("◌్రస్త", "స్త్ర"),
        ("క్రమ", "క్రమ"),
        ("ఉచై్ఛశ్రవము", "ఉచ్ఛైశ్రవము"),
    ],
)
def test_normalise_restores_unicode_order(anu_order: str, unicode_order: str) -> None:
    assert normalise(anu_order) == unicode_order


@pytest.mark.parametrize(("unicode_order", "anu_order"), [("త్కా", "తా్క"), ("చ్ఛే", "చే్ఛ"), ("ణ్వ", "ణ్వ")])
def test_denormalise_is_inverse_of_subscript_reorder(unicode_order: str, anu_order: str) -> None:
    assert denormalise(unicode_order) == anu_order
    assert normalise(denormalise(unicode_order)) == unicode_order
