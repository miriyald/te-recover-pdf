from pathlib import Path

from anu_unicode.scan.corrections import NO_PATTERN, PER_PATTERN, Disagreement, pattern_of, ranked, read_corrections, write_disagreements

BOX = (10, 20, 90, 60)


def test_corrections_are_read_by_page_and_word_box(tmp_path: Path) -> None:
    path = tmp_path / "corrections.tsv"
    path.write_text("page\tleft\ttop\tright\tbottom\ttext\n12\t10\t20\t90\t60\tవాఁడు\n", encoding="utf-8")

    assert read_corrections(path) == {(12, BOX): "వాఁడు"}
    assert read_corrections(tmp_path / "missing.tsv") == {}


def test_a_correction_row_without_text_is_skipped(tmp_path: Path) -> None:
    path = tmp_path / "corrections.tsv"
    path.write_text("page\tleft\ttop\tright\tbottom\ttext\n12\t10\t20\t90\t60\n", encoding="utf-8")

    assert not read_corrections(path)


def test_the_pattern_names_what_ocr_read_and_what_we_read_including_letters_tesseract_cannot_read() -> None:
    assert pattern_of("సమము", "పమము") == "ప→స"
    assert pattern_of("ఱంపము", "రంపము") == "ర→ఱ"
    assert pattern_of("కమ ల", "కమల") == NO_PATTERN


def test_frequent_patterns_come_first_with_a_few_words_each_and_noise_last() -> None:
    common = [((1, 1, word), "సమము", "పమము") for word in range(1, PER_PATTERN + 3)]
    rare = [((2, 1, 1), "కా", "కి")]
    noise = [((3, 1, 1), "కమ ల", "కమల")]
    boxes = {key: BOX for key, _, _ in common + rare + noise}

    rows = ranked(common + noise + rare, boxes, top=100)

    assert [(word.pattern, count) for word, count in rows] == [("ప→స", PER_PATTERN + 2)] * PER_PATTERN + [("ి→ా", 1), (NO_PATTERN, 1)]
    assert rows[0][0].place == (1, BOX)
    assert len(ranked(common + noise + rare, boxes, top=2)) == 2


def test_the_sheet_offers_both_readings_and_keeps_earlier_corrections(tmp_path: Path) -> None:
    word = Disagreement((5, 2, 7), BOX, "సమము", "పమము", "ప→స")

    write_disagreements(tmp_path / "sheet.html", [(word, 3)], {(1, (0, 0, 9, 9)): "కా"}, "words")

    sheet = (tmp_path / "sheet.html").read_text(encoding="utf-8")
    assert "data-key=5-10-20-90-60" in sheet and "src='words/5-10-20-90-60.png'" in sheet and "p5 l2 w7" in sheet
    assert "fill(this,&quot;సమము&quot;)" in sheet and "fill(this,&quot;పమము&quot;)" in sheet
    assert '"1-0-0-9-9": "కా"' in sheet and '"page\\tleft\\ttop\\tright\\tbottom\\ttext"' in sheet
