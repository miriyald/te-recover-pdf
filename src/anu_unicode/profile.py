import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FontProfile:
    anu_fonts: frozenset[str]
    ascent: float
    descent: float


DEFAULT_PROFILE = FontProfile(
    frozenset({"Priyaanka", "PriyaankaBold", "PallaviBold", "Pragathi", "Prabhava", "Kranthi"}), ascent=0.75, descent=0.35
)


def load_profile(path: Path) -> FontProfile:
    data = json.loads(path.read_text(encoding="utf-8"))
    return FontProfile(frozenset(data["anu_fonts"]), float(data["ascent"]), float(data["descent"]))


def save_profile(path: Path, profile: FontProfile) -> None:
    data = {"anu_fonts": sorted(profile.anu_fonts), "ascent": profile.ascent, "descent": profile.descent}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
