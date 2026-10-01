from anu_unicode.solve import gap_candidates, solve_confirmed

KNOWN: list[tuple[str, str | None]] = []


def test_single_gap_resolved_through_subscript_reorder_elsewhere_in_word() -> None:
    segments = [("=∂", "మా"), ("O", "ం"), ("_»", "డ"), ('"À', None), ("º", "్య"), ("áê", "పా"), ("MÏº", "ఖ్యా"), ("#", "న"), ("=Ú", "ము")]

    assert solve_confirmed(segments, "మాండవ్యోపాఖ్యానము") == {'"À': "వో"}


def test_pre_base_ra_gap_resolves_to_placeholder() -> None:
    segments = [("âß", "శా"), ("¢", None), ("ã≤Î", "స్తి")]

    assert solve_confirmed(segments, "శాస్త్రి") == {"¢": "◌్ర"}


def test_length_mark_gap_resolves_through_canonical_composition() -> None:
    segments = [("K≥", "చె"), ("·", None), ("„`«", "త్ర"), ("~°", "ర"), ("^äŒ", "థ")]

    assert solve_confirmed(segments, "చైత్రరథ") == {"·": "ౖ"}


def test_silent_pre_base_piece_widens_to_the_following_letter() -> None:
    segments = [("Ñ¨Ù", "పు"), ("„`«∞", "త్రు"), ("x", "ని"), ("Ô", None), ("H·", "కై")]

    assert solve_confirmed(segments, "పుత్రునికై") == {"ÔH·": "కై"}


def test_gap_that_alters_previous_letter_widens_left() -> None:
    segments = [("Hõ", "క"), ("i", "రి"), ("î", None), ("<À", "నో")]

    assert solve_confirmed(segments, "కఠినో") == {"iî": "ఠి"}


def test_two_gaps_solved_together() -> None:
    segments = [("ã¨", "స"), ("O", "ం"), ("H", None), ("Δ", "్ష"), ("À", None), ("Éèí", "భ"), ("=Ú", "ము")]

    assert solve_confirmed(segments, "సంక్షోభము") == {"H": "క", "À": "ో"}


def test_silent_gap_never_widens_into_previous_letter() -> None:
    segments = [("ÖÏ", "లా"), ("#", "న"), ("=Ú", "ము"), (":", None)]

    assert solve_confirmed(segments, "లానము") is None


def test_widening_never_absorbs_punctuation() -> None:
    segments = [("á⁄", "పొ"), ("O", "ం"), ("^≥", None), ("#∞", "ను"), (".", ".")]

    assert solve_confirmed(segments, "పొందెను") is None
    assert solve_confirmed(segments, "పొందెను.") == {"^≥": "దె"}


def test_second_gap_widens_in_multi_gap_word() -> None:
    segments = [("ÃÇ", None), ("·", "ౖ"), ("Ï", "ా"), ("^Œ", "ద"), ("~å", "రా"), ("ÉÏ", "బా"), ("^£", None)]

    assert solve_confirmed(segments, "హైదరాబాద్") == {"ÃÇ·Ï": "హై", "^£": "ద్"}


def test_equivalent_orders_count_as_one_solution() -> None:
    segments = [('"Õ∞', "మే"), ("¡", "్ల"), ("K«∞Û", "చ్చు"), ("ù", None), ("Å∞", "లు"), (",", ",")]

    assert solve_confirmed(segments, "మ్లేచ్ఛులు,") == {"K«∞Ûù": "చ్ఛు"}


def test_unsolvable_confirmation_returns_none() -> None:
    segments = [("Hõ", "క"), ("ﬁ", None)]

    assert solve_confirmed(segments, "పణ్వ") is None


def test_learner_candidates_stay_single_gap_and_unwidened() -> None:
    assert gap_candidates([("x", "ని"), ("Ô", None), ("H·", "కై")], "నికై") == set()
    assert gap_candidates([("Hõ", "క"), ("¯", None), ("}", "ణ"), ("ﬁ", None)], "క్కణ్వ") == set()
