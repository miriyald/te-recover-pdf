import type { Mapping } from "./mapping";
import { markVisibleVirama, normalise } from "./telugu";

export const UNMAPPED_OPEN = "⟦";
export const UNMAPPED_CLOSE = "⟧";

export type Segment = readonly [glyphs: string, unicode: string | null];
export interface Run {
  text: string;
  isAnu: boolean;
}
export interface Coverage {
  glyphs: number;
  unmapped: Map<string, number>;
}

export function newCoverage(): Coverage {
  return { glyphs: 0, unmapped: new Map() };
}

export function coverageRatio(coverage: Coverage): number {
  let unmappedGlyphs = 0;
  for (const [glyphs, count] of coverage.unmapped) unmappedGlyphs += glyphs.length * count;
  return coverage.glyphs === 0 ? 1 : 1 - unmappedGlyphs / coverage.glyphs;
}

function longestKey(text: string, position: number, table: Mapping, longest: number): string | null {
  for (let end = Math.min(text.length, position + longest); end > position; end--) {
    const key = text.slice(position, end);
    if (table.has(key)) return key;
  }
  return null;
}

export function convertSegments(text: string, mapping: Mapping): Segment[] {
  const table = new Map(mapping).set(" ", " ");
  const longest = Math.max(...Array.from(table.keys(), (key) => key.length));
  const segments: Segment[] = [];
  let position = 0;
  while (position < text.length) {
    const key = longestKey(text, position, table, longest);
    const last = segments[segments.length - 1];
    if (key !== null) {
      segments.push([key, table.get(key) ?? ""]);
      position += key.length;
    } else if (last !== undefined && last[1] === null) {
      segments[segments.length - 1] = [last[0] + text[position], null];
      position += 1;
    } else {
      segments.push([text[position] ?? "", null]);
      position += 1;
    }
  }
  return segments;
}

export function render(segments: readonly Segment[], coverage: Coverage): string {
  for (const [glyphs, unicode] of segments) {
    if (glyphs !== " ") coverage.glyphs += glyphs.length;
    if (unicode === null) coverage.unmapped.set(glyphs, (coverage.unmapped.get(glyphs) ?? 0) + 1);
  }
  const text = segments.map(([glyphs, unicode]) => (unicode === null ? UNMAPPED_OPEN + glyphs + UNMAPPED_CLOSE : unicode)).join("");
  return markVisibleVirama(normalise(text));
}

export function convertAnu(text: string, mapping: Mapping, coverage: Coverage): string {
  return render(convertSegments(text, mapping), coverage);
}

export function convertLine(runs: readonly Run[], mapping: Mapping, coverage: Coverage): string {
  const merged: Run[] = [];
  for (const run of runs) {
    const last = merged[merged.length - 1];
    if (last !== undefined && last.isAnu === run.isAnu) last.text += run.text;
    else merged.push({ ...run });
  }
  return merged.map((run) => (run.isAnu ? convertAnu(run.text, mapping, coverage) : run.text)).join("");
}
