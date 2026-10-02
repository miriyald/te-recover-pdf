import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { convertLine, coverageRatio, newCoverage, type Run } from "../src/convert";
import { parseMapping } from "../src/mapping";

const mapping = parseMapping(readFileSync(new URL("../../fonts/anu/ocr-learning/mapping.tsv", import.meta.url), "utf-8"));
const golden = JSON.parse(readFileSync(new URL("./golden.json", import.meta.url), "utf-8")) as { runs: Run[]; expected: string }[];

describe("convertLine", () => {
  it("matches the Python converter on real lines", () => {
    const mismatches = golden.filter(({ runs, expected }) => convertLine(runs, mapping, newCoverage()) !== expected);
    expect(mismatches).toEqual([]);
  });

  it("marks unmapped glyphs and lowers coverage", () => {
    const coverage = newCoverage();
    const converted = convertLine([{ text: "\u0001", isAnu: true }], new Map(), coverage);
    expect(converted).toBe("⟦\u0001⟧");
    expect(coverageRatio(coverage)).toBe(0);
  });

  it("leaves non-Anu runs untouched", () => {
    expect(convertLine([{ text: "29", isAnu: false }], mapping, newCoverage())).toBe("29");
  });
});
