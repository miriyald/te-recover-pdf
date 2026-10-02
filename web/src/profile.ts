const SYMBOL_BASE = 0xf000;
const SYMBOL_FIRST = 0xf020;
const SYMBOL_LAST = 0xf0ff;
const BYTE_OVERRIDES = new Map([[0xc6, "Δ"], [0xd0, "-"], [0xdb, "¤"]]);
const MAC_ROMAN = new TextDecoder("macintosh");

export const ANU_FONTS: ReadonlySet<string> = new Set([
  "Priyaanka", "PriyaankaBold", "PallaviBold", "Pragathi", "Prabhava", "Kranthi",
  "GowthamiThin", "GowthamiMedium", "GowthamiBold", "GowthamiBlack", "GowthamiExtraBold",
  "AnupamaMedium", "AnupamaBold", "AnupamaExtraBold", "Dharani", "Brahma",
]);

export function fontFamily(fontName: string): string {
  return (fontName.split("+").pop() ?? "").split(",")[0] ?? "";
}

function byteChar(byte: number): string {
  return BYTE_OVERRIDES.get(byte) ?? MAC_ROMAN.decode(Uint8Array.of(byte));
}

export function decodeSymbols(text: string): string {
  return Array.from(text, (char) => {
    const code = char.codePointAt(0) ?? 0;
    return code >= SYMBOL_FIRST && code <= SYMBOL_LAST ? byteChar(code - SYMBOL_BASE) : char;
  }).join("");
}
