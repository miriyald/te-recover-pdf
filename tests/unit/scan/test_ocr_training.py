import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from anu_unicode.scan.conversion import Choice, ScanText, Written
from anu_unicode.scan.ocr_training import (
    Tools,
    Training,
    added_letters,
    base_part,
    best_checkpoint,
    box_text,
    confirmed_lines,
    known_letters,
    split,
    starter_model,
    train,
    trainable,
    write_lines,
)

KNOWN = set("కామునడవాఇంద్రరపయి ")


def _page(*words: tuple[str, tuple[Choice, ...]]) -> ScanText:
    return ScanText([[Written(((7, 1, number),), text, choices) for number, (text, choices) in enumerate(words, 1)]])


def test_only_agreed_reviewed_or_corrected_readings_without_gaps_become_training_lines() -> None:
    page = _page(("కా", (Choice.AGREED,)), ("ము", (Choice.REVIEWED,)), ("మా", (Choice.WORD_OCR,)), ("క□", (Choice.GAP,)),
                 ("కాము", (Choice.AGREED, Choice.WORD_OCR)), ("వాఁడు", (Choice.CORRECTED,)))

    lines = confirmed_lines(page)

    assert [(line.keys, line.text) for line in lines] == [(((7, 1, 1),), "కా"), (((7, 1, 2),), "ము"), (((7, 1, 6),), "వాఁడు")]


def test_a_letter_the_base_lacks_is_added_once_enough_lines_need_it() -> None:
    texts = ["వాఁడు", "ఇంద్రుఁడా", "కాఁక", "ఱంపము", "ఱాయి"]

    assert added_letters(texts, KNOWN) == {"ఁ"}


def test_a_line_with_a_letter_that_was_not_added_is_left_out() -> None:
    assert trainable("వాఁడు", KNOWN, {"ఁ"}) and not trainable("ఱంపము", KNOWN, {"ఁ"})


def test_known_letters_are_the_code_points_of_the_base_entries_plus_space(tmp_path: Path) -> None:
    training = Training(Tools(tmp_path / "tesseract.exe"), tmp_path / "tel.traineddata", tmp_path)
    base_part(training, "lstm-unicharset").write_text("5\nNULL 0 Common 0\nJoined 7 0\n|Broken|0|1 f 0\n్ర 0 Telugu 1\nక 1 Telugu 2\n",
                                                      encoding="utf-8")

    assert known_letters(training) == {" ", "్", "ర", "క"}


def test_the_starter_model_merges_the_base_letters_with_those_the_lines_need_and_keeps_its_dictionaries(tmp_path: Path) -> None:
    training = Training(Tools(tmp_path / "tesseract.exe"), tmp_path / "tel.traineddata", tmp_path)
    for kind in ("word", "punc"):
        base_part(training, f"lstm-{kind}-dawg").write_bytes(b"")
    calls: list[tuple[str, ...]] = []

    with patch.object(Tools, "run", side_effect=lambda name, *arguments, **_options: calls.append((name, *arguments))):
        starter = starter_model(training, ["వాఁడు"], "tel_x", tmp_path / "langdata")

    tools = ["unicharset_extractor", "merge_unicharsets", "dawg2wordlist", "dawg2wordlist", "combine_lang_model"]
    assert [call[0] for call in calls] == tools
    assert calls[0][1:3] == ("--norm_mode", "2")
    assert calls[-1][calls[-1].index("--words") + 1] == base_part(training, "word").as_posix()
    assert "--numbers" not in calls[-1]
    assert starter == tmp_path / "starter" / "tel_x" / "tel_x.traineddata"
    assert (tmp_path / "lines.txt").read_text(encoding="utf-8") == "వాఁడు\n"


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
    failed = subprocess.CompletedProcess([], 1, stdout="ఁ in ".encode(), stderr=b"bad list")

    with patch("anu_unicode.scan.ocr_training.subprocess.run", return_value=failed), pytest.raises(RuntimeError, match="ఁ in bad list"):
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
    starter = tmp_path / "starter.traineddata"

    def lines(count: int) -> list[Path]:
        return [tmp_path / f"{number}.lstmf" for number in range(count)]

    with pytest.raises(ValueError, match="only 3 training lines"):
        train(training, starter, lines(3), tmp_path / "out.traineddata", 10)
    with pytest.raises(ValueError, match="would overwrite its base"):
        train(training, starter, lines(30), tmp_path / "tel.traineddata", 10)


def test_training_runs_the_tools_in_order_and_publishes_the_best_checkpoint(tmp_path: Path) -> None:
    training = Training(Tools(tmp_path / "tesseract.exe"), tmp_path / "tel.traineddata", tmp_path)
    calls: list[tuple[str, ...]] = []

    def run(name: str, *arguments: str, **_options: Path) -> None:
        calls.append((name, *arguments))
        if "--max_iterations" in arguments:
            (tmp_path / "checkpoints" / "out_0.9_10_100.checkpoint").write_bytes(b"")

    starter = tmp_path / "starter.traineddata"
    with patch.object(Tools, "run", side_effect=run):
        train(training, starter, [tmp_path / f"{number}.lstmf" for number in range(30)], tmp_path / "out.traineddata", 100)

    assert [call[0] for call in calls] == ["lstmtraining", "lstmtraining"]
    assert calls[0][calls[0].index("--old_traineddata") + 1] == (tmp_path / "tel.traineddata").as_posix()
    assert calls[0][calls[0].index("--traineddata") + 1] == calls[1][calls[1].index("--traineddata") + 1] == starter.as_posix()
    assert calls[1][calls[1].index("--continue_from") + 1] == (tmp_path / "checkpoints" / "out_0.9_10_100.checkpoint").as_posix()
    assert len((tmp_path / "eval.txt").read_text(encoding="utf-8").split()) == 3
