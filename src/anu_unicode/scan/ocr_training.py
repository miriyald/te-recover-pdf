import random
import subprocess
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from anu_unicode.scan.conversion import PLACEHOLDER, Choice, ScanText
from anu_unicode.scan.word_ocr import OCR_WORKERS, WordKey

CONFIRMED = frozenset({Choice.AGREED, Choice.REVIEWED})
EVALUATION_SHARE = 10
MIN_LINES = 20
SPLIT_SEED = 7


@dataclass(frozen=True)
class TrainingLine:
    keys: tuple[WordKey, ...]
    text: str


def encodable(text: str, entries: set[str]) -> bool:
    longest = max((len(entry) for entry in entries), default=0)
    reachable = [True] + [False] * len(text)
    for end in range(1, len(text) + 1):
        reachable[end] = any(reachable[end - size] and text[end - size:end] in entries for size in range(1, min(longest, end) + 1))
    return reachable[-1]


def confirmed_lines(page: ScanText, entries: set[str]) -> list[TrainingLine]:
    return [TrainingLine(word.keys, word.text) for line in page.written for word in line
            if set(word.choices) <= CONFIRMED and word.text.strip() and PLACEHOLDER not in word.text
            and encodable(word.text.replace(" ", ""), entries)]


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
            result = subprocess.run([self.path(name), *arguments], capture_output=True, text=True, check=False)
            output = result.stdout + result.stderr
        else:
            with log.open("w", encoding="utf-8") as stream:
                result = subprocess.run([self.path(name), *arguments], stdout=stream, stderr=subprocess.STDOUT, text=True, check=False)
            output = log.read_text(encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"{name} failed ({result.returncode}): {output[-400:]}")


@dataclass(frozen=True)
class Training:
    tools: Tools
    base: Path
    folder: Path


def model_entries(training: Training) -> set[str]:
    unicharset = training.folder / "base.lstm-unicharset"
    training.tools.run("combine_tessdata", "-e", training.base.as_posix(), unicharset.as_posix())
    return {line.split(" ")[0] for line in unicharset.read_text(encoding="utf-8").splitlines()[1:]}


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


def train(training: Training, lstmf: Sequence[Path], output: Path, iterations: int) -> Path:
    tools, base, folder = training.tools, training.base, training.folder
    if len(lstmf) < MIN_LINES:
        raise ValueError(f"only {len(lstmf)} training lines; at least {MIN_LINES} are needed")
    if output.resolve() == base.resolve():
        raise ValueError(f"{output} would overwrite its base model")
    train_lines, evaluation_lines = split([path.resolve().as_posix() for path in lstmf], seed=SPLIT_SEED)
    (folder / "train.txt").write_text("\n".join(train_lines) + "\n", encoding="utf-8", newline="\n")
    (folder / "eval.txt").write_text("\n".join(evaluation_lines) + "\n", encoding="utf-8", newline="\n")
    network = folder / "base.lstm"
    tools.run("combine_tessdata", "-e", base.as_posix(), network.as_posix())
    checkpoints = folder / "checkpoints" / output.stem
    checkpoints.parent.mkdir(parents=True, exist_ok=True)
    tools.run("lstmtraining", "--continue_from", network.as_posix(), "--traineddata", base.as_posix(),
              "--model_output", checkpoints.as_posix(), "--train_listfile", (folder / "train.txt").as_posix(),
              "--eval_listfile", (folder / "eval.txt").as_posix(), "--max_iterations", str(iterations), log=folder / "training.log")
    tools.run("lstmtraining", "--stop_training", "--continue_from", best_checkpoint(checkpoints).as_posix(),
              "--traineddata", base.as_posix(), "--model_output", output.as_posix())
    return output
