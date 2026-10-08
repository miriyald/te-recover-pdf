import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from anu_unicode.scan.conversion import Choice, ScanText, Written
from anu_unicode.scan.ocr_training import Tools, Training, best_checkpoint, box_text, confirmed_lines, encodable, split, train, write_lines

ENTRIES = {"క", "ా", "మ", "ు", "్ర", "ప"}


def _page(*words: tuple[str, tuple[Choice, ...]]) -> ScanText:
    return ScanText([[Written(((7, 1, number),), text, choices) for number, (text, choices) in enumerate(words, 1)]])


def test_only_agreed_or_reviewed_readings_without_gaps_become_training_lines() -> None:
    page = _page(("కా", (Choice.AGREED,)), ("ము", (Choice.REVIEWED,)), ("మా", (Choice.WORD_OCR,)), ("క□", (Choice.GAP,)),
                 ("కాము", (Choice.AGREED, Choice.WORD_OCR)))

    lines = confirmed_lines(page, ENTRIES)

    assert [(line.keys, line.text) for line in lines] == [(((7, 1, 1),), "కా"), (((7, 1, 2),), "ము")]


def test_text_the_model_cannot_encode_is_left_out() -> None:
    assert [line.text for line in confirmed_lines(_page(("కాఁ", (Choice.AGREED,)), ("ప్ర", (Choice.AGREED,))), ENTRIES)] == ["ప్ర"]


def test_encoding_takes_the_longest_entry_first() -> None:
    assert encodable("ప్రకా", ENTRIES) and not encodable("పఁ", ENTRIES)


def test_encoding_tries_every_way_to_split_the_text() -> None:
    assert encodable("abc", {"ab", "bc", "a"})


def test_the_box_file_spans_the_whole_line_image() -> None:
    assert box_text("కా ము", 120, 60) == "WordStr 0 0 120 60 0 #కా ము\n\t 120 0 121 1 0\n"


def test_the_split_is_seeded_and_keeps_a_tenth_for_evaluation() -> None:
    names = [f"line-{number}" for number in range(30)]

    training, evaluation = split(names, seed=7)

    assert (len(training), len(evaluation)) == (27, 3)
    assert set(training) | set(evaluation) == set(names)
    assert split(names, seed=7) == (training, evaluation)


def test_tools_sit_next_to_tesseract_and_a_failing_tool_raises(tmp_path: Path) -> None:
    (tmp_path / "tesseract.exe").write_bytes(b"")
    (tmp_path / "lstmtraining.exe").write_bytes(b"")
    tools = Tools(tmp_path / "tesseract.exe")
    failed = subprocess.CompletedProcess([], 1, stdout="", stderr="bad list")

    with patch("anu_unicode.scan.ocr_training.subprocess.run", return_value=failed), pytest.raises(RuntimeError, match="bad list"):
        tools.run("lstmtraining", "--version")

    assert tools.path("lstmtraining") == (tmp_path / "lstmtraining.exe").as_posix()
    assert tools.path("combine_tessdata") == "combine_tessdata"


def test_each_training_line_is_an_image_with_its_text_and_box(tmp_path: Path) -> None:
    images = write_lines(tmp_path, [("p7-01-01", Image.new("L", (40, 20), 255), "కా")])

    assert images == [tmp_path / "p7-01-01.png"]
    assert (tmp_path / "p7-01-01.gt.txt").read_text(encoding="utf-8") == "కా\n"
    assert (tmp_path / "p7-01-01.box").read_text(encoding="utf-8").startswith("WordStr 0 0 40 20 0 #కా")
    assert b"\r" not in (tmp_path / "p7-01-01.box").read_bytes() + (tmp_path / "p7-01-01.gt.txt").read_bytes()


def test_the_lowest_error_checkpoint_is_chosen(tmp_path: Path) -> None:
    for name in ("tel_x_1.257_533_6000.checkpoint", "tel_x_1.134_527_5800.checkpoint", "tel_x_2.0_100_900.checkpoint", "tel_x_checkpoint"):
        (tmp_path / name).write_bytes(b"")

    assert best_checkpoint(tmp_path / "tel_x") == tmp_path / "tel_x_1.134_527_5800.checkpoint"


def test_training_refuses_too_few_lines_and_an_output_that_is_its_own_base(tmp_path: Path) -> None:
    training = Training(Tools(tmp_path / "tesseract.exe"), tmp_path / "tel.traineddata", tmp_path)

    with pytest.raises(ValueError, match="only 3 training lines"):
        train(training, [tmp_path / f"{number}.lstmf" for number in range(3)], tmp_path / "out.traineddata", 10)
    with pytest.raises(ValueError, match="would overwrite its base"):
        train(training, [tmp_path / f"{number}.lstmf" for number in range(30)], tmp_path / "tel.traineddata", 10)


def test_training_runs_the_tools_in_order_and_publishes_the_best_checkpoint(tmp_path: Path) -> None:
    training = Training(Tools(tmp_path / "tesseract.exe"), tmp_path / "tel.traineddata", tmp_path)
    calls: list[tuple[str, ...]] = []

    def run(name: str, *arguments: str, **_options: Path) -> None:
        calls.append((name, *arguments))
        if "--max_iterations" in arguments:
            (tmp_path / "checkpoints" / "out_0.9_10_100.checkpoint").write_bytes(b"")

    with patch.object(Tools, "run", side_effect=run):
        train(training, [tmp_path / f"{number}.lstmf" for number in range(30)], tmp_path / "out.traineddata", 100)

    assert [call[0] for call in calls] == ["combine_tessdata", "lstmtraining", "lstmtraining"]
    assert calls[2][calls[2].index("--continue_from") + 1] == (tmp_path / "checkpoints" / "out_0.9_10_100.checkpoint").as_posix()
    assert len((tmp_path / "eval.txt").read_text(encoding="utf-8").split()) == 3
