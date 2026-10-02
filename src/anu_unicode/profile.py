import json
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from anu_unicode.mapping import read_rows

BYTE_ENCODING = "latin-1"


@dataclass(frozen=True)
class FontProfile:
    anu_fonts: frozenset[str]
    ascent: float
    descent: float
    byte_encoding: str = BYTE_ENCODING
    byte_overrides: Mapping[int, str] = field(default_factory=dict)
    type1_layout_file: str = ""
    type1_codes: Mapping[str, int] = field(default_factory=dict)
    type1_plain_pages: frozenset[int] = frozenset()

    def byte_char(self, byte: int) -> str:
        return self.byte_overrides.get(byte) or bytes([byte]).decode(self.byte_encoding)

    def canonical(self, char: str) -> str:
        char = unicodedata.normalize("NFC", char)
        byte = self.char_byte(char)
        return char if byte is None else self.byte_char(byte)

    def char_byte(self, char: str) -> int | None:
        overridden = next((byte for byte, override in self.byte_overrides.items() if override == char), None)
        if overridden is not None:
            return overridden
        try:
            encoded = char.encode(self.byte_encoding)
        except UnicodeEncodeError:
            return None
        return encoded[0] if len(encoded) == 1 else None


DEFAULT_PROFILE = FontProfile(
    frozenset({
        "Priyaanka", "PriyaankaBold", "PallaviBold", "Pragathi", "Prabhava", "Kranthi",
        "GowthamiThin", "GowthamiMedium", "GowthamiBold", "GowthamiBlack", "GowthamiExtraBold",
        "AnupamaThin", "AnupamaMedium", "AnupamaBold", "AnupamaExtraBold", "GowthamiNarrow", "PallaviMedium", "Dharani", "Brahma",
    }),
    ascent=0.75, descent=0.35, byte_encoding="mac_roman", byte_overrides={0xC6: "Δ", 0xD0: "-", 0xDB: "¤"},
)


def load_type1_codes(path: Path) -> dict[str, int]:
    return {row["char"]: int(byte, 16) for row in read_rows(path) if (byte := row.get("confirmed") or row.get("byte"))}


def load_profile(path: Path) -> FontProfile:
    data = json.loads(path.read_text(encoding="utf-8"))
    overrides = {int(byte, 16): char for byte, char in data.get("byte_overrides", {}).items()}
    layout_file = data.get("type1_layout", "")
    return FontProfile(frozenset(data["anu_fonts"]), float(data["ascent"]), float(data["descent"]),
                       data.get("byte_encoding", BYTE_ENCODING), overrides, layout_file,
                       load_type1_codes(Path(layout_file)) if layout_file else {}, frozenset(data.get("type1_plain_pages", [])))


def save_profile(path: Path, profile: FontProfile) -> None:
    data = {
        "anu_fonts": sorted(profile.anu_fonts), "ascent": profile.ascent, "descent": profile.descent,
        "byte_encoding": profile.byte_encoding,
        "byte_overrides": {f"{byte:02X}": char for byte, char in sorted(profile.byte_overrides.items())},
    }
    if profile.type1_layout_file:
        data["type1_layout"] = profile.type1_layout_file
    if profile.type1_plain_pages:
        data["type1_plain_pages"] = sorted(profile.type1_plain_pages)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
