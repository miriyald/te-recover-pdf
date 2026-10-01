from anu_unicode.confirm import Confirmation, apply_confirmations, parse_confirmations
from anu_unicode.glyphs import Glyph, Word
from anu_unicode.learn import LearningState
from anu_unicode.mapping import MappingEntry, Proposal


def _word(text: str) -> Word:
    return Word(tuple(Glyph(char, (index, 0, index + 1, 1), index, True) for index, char in enumerate(text)))


def _state(seed: dict[str, str], pending: list[Proposal] | None = None) -> LearningState:
    return LearningState({glyphs: MappingEntry(glyphs, unicode) for glyphs, unicode in seed.items()}, pending or [])


def test_parse_accepts_tab_equals_and_stray_whitespace() -> None:
    text = "శా⟦¢⟧స్తి\tశాస్త్రి\n\tదీర⟦…⟧తముడను   = \tదీర్ఘతముడను\n⟦‰õ⟧ర్ణుడు=కర్ణుడు\n\nnot a pair\n"

    confirmations = parse_confirmations(text)

    assert confirmations == [
        Confirmation("శా⟦¢⟧స్తి", "శాస్త్రి"),
        Confirmation("దీర⟦…⟧తముడను", "దీర్ఘతముడను"),
        Confirmation("⟦‰õ⟧ర్ణుడు", "కర్ణుడు"),
    ]


def test_parse_keeps_equals_glyph_inside_gap() -> None:
    assert parse_confirmations("క⟦=∞⟧ = కమ") == [Confirmation("క⟦=∞⟧", "కమ")]


def test_confirmation_adds_entry_with_audit_and_clears_pending() -> None:
    state = _state({"âß": "శా", "ã≤Î": "స్తి"}, [Proposal("¢", "(", 1, 4, "(స్తి", {"శా|స్తి"})])

    results = apply_confirmations([Confirmation("శా⟦¢⟧స్తి", "శాస్త్రి")], [(4, _word("âß¢ã≤Î"))], state)

    assert results[0].status == "added"
    assert state.entries["¢"] == MappingEntry("¢", "◌్ర", 4, "శాస్త్రి")
    assert not state.pending


def test_earlier_confirmation_makes_later_one_already_correct() -> None:
    state = _state({"âß": "శా", "ã≤Î": "స్తి", "ã‘Î": "స్తీ"})
    words = [(4, _word("âß¢ã≤Î")), (11, _word("¢ã‘Î"))]

    results = apply_confirmations([Confirmation("⟦¢⟧స్తీ", "స్త్రీ"), Confirmation("శా⟦¢⟧స్తి", "శాస్త్రి")], words, state)

    assert {result.status for result in results} == {"added", "already correct"}


def test_only_the_word_matching_the_shown_text_is_solved() -> None:
    state = _state({"Ñ¨": "ప", "á⁄": "పొ", "O": "ం", "=Ú": "ము", "_ç": "డి", "k": "ది"})
    words = [(42, _word("Ñ¨O^≥=Ú")), (42, _word("á⁄O^≥_çk"))]

    results = apply_confirmations([Confirmation("పొం⟦^≥⟧డిది", "పొందెడిది")], words, state)

    assert results[0].status == "added"
    assert state.entries["^≥"].unicode == "దె"


def test_widened_confirmation_reports_overridden_letters() -> None:
    state = _state({"Ñ¶¨": "ఫ", "i‚": "ర్ణి", "Hõ": "క"})

    results = apply_confirmations([Confirmation("ఫ⟦¸⟧ర్ణిక", "ఘూర్జిక")], [(74, _word("Ñ¶¨¸i‚Hõ"))], state)

    assert results[0].overrides == "ఫ ర్ణి"


def test_missing_word_is_reported_not_found() -> None:
    results = apply_confirmations([Confirmation("⟦Z⟧", "ఎ")], [(1, _word("Hõ"))], _state({"Hõ": "క"}))

    assert results[0].status == "not found"
