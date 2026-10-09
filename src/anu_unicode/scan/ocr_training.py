import random
import subprocess
from collections import Counter
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from anu_unicode.scan.conversion import PLACEHOLDER, Choice, ScanText
from anu_unicode.scan.word_ocr import OCR_WORKERS, WordKey

CONFIRMED = frozenset({Choice.AGREED, Choice.REVIEWED, Choice.CORRECTED})
EVALUATION_SHARE = 10
MIN_LINES = 20
MIN_LETTER_LINES = 3
NORM_MODE = "2"
BASE_PREFIX = "base."
SPECIAL_ENTRIES = frozenset({"NULL", "Joined", "|Broken|0|1"})
DICTIONARIES = (("word", "--words"), ("punc", "--puncs"), ("number", "--numbers"))
RADICAL_STROKE = "radical-stroke.txt"
LANGDATA_URL = "https://github.com/tesseract-ocr/langdata_lstm"
SPLIT_SEED = 7


@dataclass(frozen=True)
class TrainingLine:
    keys: tuple[WordKey, ...]
    text: str


def confirmed_lines(page: ScanText) -> list[TrainingLine]:
    return [TrainingLine(word.keys, word.text) for line in page.written for word in line
            if set(word.choices) <= CONFIRMED and word.text.strip() and PLACEHOLDER not in word.text]


def added_letters(texts: Iterable[str], known: set[str]) -> set[str]:
    lines_with = Counter(letter for text in texts for letter in set(text) - known)
    return {letter for letter, count in lines_with.items() if count >= MIN_LETTER_LINES}


def trainable(text: str, known: set[str], added: set[str]) -> bool:
    return set(text) - known <= added


def box_text(text: str, width: int, height: int) -> str:
    return f"WordStr 0 0 {width} {height} 0 #{text}\n\t {width} 0 {width + 1} 1 0\n"


def split(names: Sequence[str], seed: int) -> tuple[list[str], list[str]]:
    shuffled = list(names)
    random.Random(seed).shuffle(shuffled)
    cut = len(shuffled) // EVALUATION_SHARE
    return shuffled[cut:], shuffled[:cut]


@dataclass(frozen=True)
class Tools:
    tesseract: Path

    def path(self, name: str) -> str:
        sibling = self.tesseract.with_name(name + self.tesseract.suffix)
        return sibling.as_posix() if sibling.is_file() else name

    def run(self, name: str, *arguments: str, log: Path | None = None) -> None:
        if log is None:
            result = subprocess.run([self.path(name), *arguments], capture_output=True, check=False)
            output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        else:
            with log.open("wb") as stream:
                result = subprocess.run([self.path(name), *arguments], stdout=stream, stderr=subprocess.STDOUT, check=False)
            output = log.read_text(encoding="utf-8", errors="replace")
        if result.returncode:
            raise RuntimeError(f"{name} failed ({result.returncode}): {output[-400:]}")


@dataclass(frozen=True)
class Training:
    tools: Tools
    base: Path
    folder: Path


def base_part(training: Training, component: str) -> Path:
    return training.folder / f"{BASE_PREFIX}{component}"


def unpack(training: Training) -> None:
    training.tools.run("combine_tessdata", "-u", training.base.as_posix(), (training.folder / BASE_PREFIX).as_posix())


def known_letters(training: Training) -> set[str]:
    lines = base_part(training, "lstm-unicharset").read_text(encoding="utf-8").splitlines()[1:]
    entries = [line.split(" ")[0] for line in lines]
    return {" "} | {letter for entry in entries if entry not in SPECIAL_ENTRIES for letter in entry}


def _word_lists(training: Training) -> list[str]:
    arguments = []
    for kind, option in DICTIONARIES:
        dawg, words = base_part(training, f"lstm-{kind}-dawg"), base_part(training, kind)
        if dawg.is_file():
            training.tools.run("dawg2wordlist", base_part(training, "lstm-unicharset").as_posix(), dawg.as_posix(), words.as_posix())
            arguments += [option, words.as_posix()]
    return arguments


def starter_model(training: Training, texts: Sequence[str], name: str, langdata: Path) -> Path:
    tools, folder = training.tools, training.folder
    corpus, extracted, merged = folder / "lines.txt", folder / "lines.unicharset", folder / "merged.unicharset"
    corpus.write_text("\n".join(texts) + "\n", encoding="utf-8", newline="\n")
    tools.run("unicharset_extractor", "--norm_mode", NORM_MODE, "--output_unicharset", extracted.as_posix(), corpus.as_posix())
    tools.run("merge_unicharsets", base_part(training, "lstm-unicharset").as_posix(), extracted.as_posix(), merged.as_posix())
    starter = folder / "starter"
    (starter / name).mkdir(parents=True, exist_ok=True)
    tools.run("combine_lang_model", "--input_unicharset", merged.as_posix(), "--script_dir", langdata.as_posix(), *_word_lists(training),
              "--pass_through_recoder", "--output_dir", starter.as_posix(), "--lang", name)
    return starter / name / f"{name}.traineddata"


def write_lines(folder: Path, lines: Sequence[tuple[str, Image.Image, str]]) -> list[Path]:
    images = []
    for name, image, text in lines:
        path = folder / f"{name}.png"
        image.save(path)
        path.with_suffix(".gt.txt").write_text(text + "\n", encoding="utf-8", newline="\n")
        path.with_suffix(".box").write_text(box_text(text, *image.size), encoding="utf-8", newline="\n")
        images.append(path)
    return images


def make_lstmf(training: Training, images: Sequence[Path]) -> list[Path]:
    def one(image: Path) -> Path:
        training.tools.run("tesseract", image.as_posix(), image.with_suffix("").as_posix(), "--tessdata-dir",
                           training.base.parent.as_posix(), "-l", training.base.stem, "--psm", "13", "lstm.train")
        return image.with_suffix(".lstmf")
    with ThreadPoolExecutor(OCR_WORKERS) as pool:
        return [path for path in pool.map(one, images) if path.is_file()]


def best_checkpoint(prefix: Path) -> Path:
    scored = []
    for path in prefix.parent.glob(f"{prefix.name}_*.checkpoint"):
        error = path.name[len(prefix.name) + 1:].split("_")[0]
        if error.replace(".", "", 1).isdigit():
            scored.append((float(error), path))
    return min(scored)[1] if scored else prefix.with_name(f"{prefix.name}_checkpoint")


def train(training: Training, starter: Path, lstmf: Sequence[Path], output: Path, iterations: int) -> Path:
    tools, base, folder = training.tools, training.base, training.folder
    if len(lstmf) < MIN_LINES:
        raise ValueError(f"only {len(lstmf)} training lines; at least {MIN_LINES} are needed")
    if output.resolve() == base.resolve():
        raise ValueError(f"{output} would overwrite its base model")
    train_lines, evaluation_lines = split([path.resolve().as_posix() for path in lstmf], seed=SPLIT_SEED)
    (folder / "train.txt").write_text("\n".join(train_lines) + "\n", encoding="utf-8", newline="\n")
    (folder / "eval.txt").write_text("\n".join(evaluation_lines) + "\n", encoding="utf-8", newline="\n")
    network = base_part(training, "lstm")
    checkpoints = folder / "checkpoints" / output.stem
    checkpoints.parent.mkdir(parents=True, exist_ok=True)
    tools.run("lstmtraining", "--continue_from", network.as_posix(), "--old_traineddata", base.as_posix(),
              "--traineddata", starter.as_posix(), "--model_output", checkpoints.as_posix(),
              "--train_listfile", (folder / "train.txt").as_posix(), "--eval_listfile", (folder / "eval.txt").as_posix(),
              "--max_iterations", str(iterations), log=folder / "training.log")
    tools.run("lstmtraining", "--stop_training", "--continue_from", best_checkpoint(checkpoints).as_posix(),
              "--traineddata", starter.as_posix(), "--model_output", output.as_posix())
    return output
