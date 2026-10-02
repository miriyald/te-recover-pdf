from dataclasses import dataclass
from pathlib import Path

FILES = Path("files")
ARCHIVE = Path("archive")
OCR_LEARNING = "ocr-learning"
SHAPE_NAMING = "shape-naming"
METHODS = (SHAPE_NAMING, OCR_LEARNING)


class LayoutError(Exception):
    pass


@dataclass(frozen=True)
class BookLayout:
    slug: str
    files: Path = FILES
    archive: Path = ARCHIVE

    @property
    def root(self) -> Path:
        return self.files / self.slug

    @property
    def input(self) -> Path:
        return self.root / "input"

    @property
    def state(self) -> Path:
        return self.root / "state"

    @property
    def intermediate_root(self) -> Path:
        return self.root / "output" / "intermediate"

    @property
    def batches(self) -> Path:
        return self.archive / self.slug / "batches"

    def input_pdf(self) -> Path:
        pdfs = sorted(self.input.glob("*.pdf"))
        if len(pdfs) != 1:
            raise LayoutError(f"expected exactly one PDF in {self.input}, found {len(pdfs)}")
        return pdfs[0]

    def output(self, method: str) -> Path:
        return self.root / "output" / method

    def intermediate(self, *parts: str) -> Path:
        return self.intermediate_root.joinpath(*parts)

    def archived_output(self, method: str, stamp: str) -> Path:
        return self.archive / self.slug / method / stamp


def books(files: Path = FILES) -> list[BookLayout]:
    return [BookLayout(path.name, files) for path in sorted(files.iterdir()) if (path / "input").is_dir()]
