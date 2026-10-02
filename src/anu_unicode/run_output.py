import hashlib
import json
import logging
import shutil
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

MANIFEST = "manifest.json"
STAMP = "%Y%m%dT%H%M%SZ"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Manifest:
    book: str
    source: str
    pdf_sha256: str
    method: str
    mapping_sources: Mapping[str, str]
    pages: int
    coverage: float
    unmapped_sequences: int
    created: str
    tool_version: str = version("anu-unicode")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now_stamp() -> str:
    return datetime.now(UTC).strftime(STAMP)


def write_manifest(directory: Path, manifest: Manifest) -> None:
    text = json.dumps(asdict(manifest), indent=2, ensure_ascii=False) + "\n"
    (directory / MANIFEST).write_text(text, encoding="utf-8", newline="\n")


def read_manifest(directory: Path) -> dict[str, Any] | None:
    path = directory / MANIFEST
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def archive_previous(output: Path, archived: Callable[[str], Path], pdf_sha256: str) -> Path | None:
    if not output.exists():
        return None
    manifest = read_manifest(output)
    stamp = manifest["created"] if manifest else datetime.fromtimestamp(output.stat().st_mtime, UTC).strftime(STAMP)
    if manifest and manifest["pdf_sha256"] != pdf_sha256:
        logger.warning("source PDF changed since the previous run", extra={"previous": manifest["pdf_sha256"], "current": pdf_sha256})
    target = archived(stamp)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(output, target)
    logger.info("previous output archived", extra={"path": str(target)})
    return target
