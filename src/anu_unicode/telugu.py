import re
import unicodedata

CONSONANT = "[క-హౘ-ౚ]"
VIRAMA = "్"
VOWEL_SIGN = "[ా-ౌౕౖౢౣ]"
VOWEL = "[అ-ఔౠౡ]"
SUBSCRIPTS = f"(?:{VIRAMA}{CONSONANT})+"
AKSHARA = re.compile(f"{CONSONANT}(?:{VIRAMA}{CONSONANT})*(?:{VOWEL_SIGN}|{VIRAMA})?|{VOWEL}|.")
TELUGU_WORD = re.compile(r"[ఀ-౿.,;:!?()'\"-]+")
SIGN_BEFORE_SUBSCRIPT = re.compile(f"((?:{VOWEL_SIGN})+)({SUBSCRIPTS})")
SUBSCRIPT_BEFORE_SIGN = re.compile(f"({SUBSCRIPTS})({VOWEL_SIGN})")
SPACE_BEFORE_MARK = re.compile(f" +(?={VOWEL_SIGN}|{VIRAMA})")
PRE_BASE = "◌"
PRE_BASE_BEFORE_CLUSTER = re.compile(f"{PRE_BASE}((?:{VIRAMA}{CONSONANT})+)({CONSONANT}(?:{VIRAMA}{CONSONANT})*)")
RA_AFTER_CLUSTER = re.compile(f"({CONSONANT}(?:{VIRAMA}(?!ర){CONSONANT})*)({VIRAMA}ర)")


def aksharas(text: str) -> list[str]:
    return AKSHARA.findall(text)


def is_telugu_word(text: str) -> bool:
    return TELUGU_WORD.fullmatch(text) is not None


def normalise(text: str) -> str:
    text = PRE_BASE_BEFORE_CLUSTER.sub(r"\2\1", SPACE_BEFORE_MARK.sub("", text))
    return unicodedata.normalize("NFC", SIGN_BEFORE_SUBSCRIPT.sub(r"\2\1", text))


def denormalise(text: str) -> str:
    return SUBSCRIPT_BEFORE_SIGN.sub(r"\2\1", text)


def anu_orders(text: str) -> set[str]:
    decomposed = {text, unicodedata.normalize("NFD", text)}
    pre_based = decomposed | {RA_AFTER_CLUSTER.sub(rf"{PRE_BASE}\2\1", variant) for variant in decomposed}
    return pre_based | {denormalise(variant) for variant in pre_based}
