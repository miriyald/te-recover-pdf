import pytest

from anu_unicode.telugu import aksharas, comparable, denormalise, finish, is_telugu_word, mark_visible_virama, normalise


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
        ("◌ేకరు", "కేరు"),
        ("◌ేస్న", "స్నే"),
        ("◌్ర◌ేప", "ప్రే"),
        ("◌ెపౖ", "పై"),
        ("◌్రషు్ట", "ష్ట్రు"),
        ("◌్రసీ్త", "స్త్రీ"),
        ("దారిద్ర్యము", "దారిద్ర్యము"),
        ("◌్రత్యధిక", "త్ర్యధిక"),
        ("క్య్ర్వ", "క్వ్ర్య"),
        ("క్వ్య్ర", "క్వ్ర్య"),
        ("క్ర్వ్య", "క్వ్ర్య"),
        ("పబ్లికేషన్‌్స", "పబ్లికేషన్స్‌"),
        ("ఉచై్ఛశ్రవము", "ఉచ్ఛైశ్రవము"),
    ],
)
def test_normalise_restores_unicode_order(anu_order: str, unicode_order: str) -> None:
    assert normalise(anu_order) == unicode_order


@pytest.mark.parametrize(("unicode_order", "anu_order"), [("త్కా", "తా్క"), ("చ్ఛే", "చే్ఛ"), ("ణ్వ", "ణ్వ")])
def test_denormalise_is_inverse_of_subscript_reorder(unicode_order: str, anu_order: str) -> None:
    assert denormalise(unicode_order) == anu_order
    assert normalise(denormalise(unicode_order)) == unicode_order


@pytest.mark.parametrize(
    ("text", "marked"),
    [
        ("మరుక్", "మరుక్‌"),
        ("మహాన్,", "మహాన్‌,"),
        ("ఋక్-యజుర్వేద", "ఋక్‌-యజుర్వేద"),
        ("షట్‌చత్వారింశ", "షట్‌చత్వారింశ"),
        ("క్షేమము", "క్షేమము"),
    ],
)
def test_virama_not_followed_by_a_consonant_keeps_its_visible_form(text: str, marked: str) -> None:
    assert mark_visible_virama(text) == marked


@pytest.mark.parametrize(
    ("text", "finished"),
    [("◌్ర", "్ర"), ("◌్ర.", "్ర."), ("◌్రప", "ప్ర"), ("◌ెక", "కె"), ("మరుక్", "మరుక్‌")],
)
def test_finish_drops_the_placeholder_of_a_subscript_with_no_letter_to_join(text: str, finished: str) -> None:
    assert finish(text) == finished


def test_comparable_ignores_zwnj_and_curly_double_quotes() -> None:
    assert comparable("“మరుక్‌”") == comparable("‘‘మరుక్’’")
