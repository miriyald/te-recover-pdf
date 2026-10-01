import re
import shutil
from pathlib import Path

PAGE_FILE = re.compile(r"page-(\d+)\.unicode\.txt")


def verified_name(page: int) -> str:
    return f"page-{page:03d}.unicode.txt"


def batch_pages(batch_dir: Path) -> list[int]:
    return sorted(int(match.group(1)) for path in batch_dir.iterdir() if (match := PAGE_FILE.fullmatch(path.name)))


def approve_batch(batch_dir: Path, verified_dir: Path, archive_dir: Path) -> list[int]:
    pages = batch_pages(batch_dir)
    verified_dir.mkdir(parents=True, exist_ok=True)
    for page in pages:
        shutil.copyfile(batch_dir / f"page-{page}.unicode.txt", verified_dir / verified_name(page))
    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(batch_dir, archive_dir / batch_dir.name)
    return pages
