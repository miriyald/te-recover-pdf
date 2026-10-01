import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

BYTE_ENCODING = "latin-1"


@dataclass(frozen=True)
class FontProfile:
    anu_fonts: frozenset[str]
    ascent: float
    descent: float
    byte_encoding: str = BYTE_ENCODING
    byte_overrides: Mapping[int, str] = field(default_factory=dict)

    def byte_char(self, byte: int) -> str:
        return self.byte_overrides.get(byte) or bytes([byte]).decode(self.byte_encoding)

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
        "AnupamaMedium", "AnupamaBold", "AnupamaExtraBold", "Dharani", "Brahma",
    }),
    ascent=0.75, descent=0.35, byte_encoding="mac_roman", byte_overrides={0xC6: "Δ", 0xD0: "-", 0xDB: "¤"},
)


def load_profile(path: Path) -> FontProfile:
    data = json.loads(path.read_text(encoding="utf-8"))
    overrides = {int(byte, 16): char for byte, char in data.get("byte_overrides", {}).items()}
    return FontProfile(frozenset(data["anu_fonts"]), float(data["ascent"]), float(data["descent"]),
                       data.get("byte_encoding", BYTE_ENCODING), overrides)


def save_profile(path: Path, profile: FontProfile) -> None:
    data = {
        "anu_fonts": sorted(profile.anu_fonts), "ascent": profile.ascent, "descent": profile.descent,
        "byte_encoding": profile.byte_encoding,
        "byte_overrides": {f"{byte:02X}": char for byte, char in sorted(profile.byte_overrides.items())},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
