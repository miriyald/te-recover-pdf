export type Mapping = ReadonlyMap<string, string>;

export function parseMapping(tsv: string): Map<string, string> {
  const [header, ...lines] = tsv.split(/\r?\n/);
  const columns = (header ?? "").split("\t");
  const glyphsIndex = columns.indexOf("glyphs");
  const unicodeIndex = columns.indexOf("unicode");
  if (glyphsIndex < 0 || unicodeIndex < 0) {
    throw new Error("Mapping needs a header with 'glyphs' and 'unicode' columns");
  }
  const mapping = new Map<string, string>();
  for (const line of lines) {
    if (line.trim() === "") continue;
    const cells = line.split("\t");
    mapping.set(cells[glyphsIndex] ?? "", cells[unicodeIndex] ?? "");
  }
  return mapping;
}
