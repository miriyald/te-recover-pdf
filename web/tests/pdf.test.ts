import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";

vi.mock("pdfjs-dist", () => import("pdfjs-dist/legacy/build/pdf.mjs"));
vi.mock("pdfjs-dist/build/pdf.worker.min.mjs?url", () => ({ default: new URL("../node_modules/pdfjs-dist/legacy/build/pdf.worker.mjs", import.meta.url).href }));

import { convertLine, newCoverage } from "../src/convert";
import { pageLines, openPdf } from "../src/extract";
import { parseMapping } from "../src/mapping";

const pdfUrl = new URL("../../files/mahabharatamu/input/Mahabharatamu.pdf", import.meta.url);
const mapping = parseMapping(readFileSync(new URL("../../fonts/anu/ocr-learning/mapping.tsv", import.meta.url), "utf-8"));
const expected = readFileSync(new URL("../../tests/fixtures/page-6.golden.txt", import.meta.url), "utf-8").trimEnd();

describe.skipIf(!existsSync(pdfUrl))("PDF extraction", () => {
  it("converts page 6 like the Python CLI", async () => {
    const buffer = readFileSync(pdfUrl);
    const pdf = await openPdf(buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength) as ArrayBuffer);
    const lines = await pageLines(await pdf.getPage(6));
    const actual = lines.map((line) => convertLine(line, mapping, newCoverage())).join("\n");
    expect(actual).toBe(expected);
  }, 60_000);
});
