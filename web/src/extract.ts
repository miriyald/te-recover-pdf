import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy, type PDFPageProxy } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { Run } from "./convert";
import { ANU_FONTS, decodeSymbols, fontFamily } from "./profile";

GlobalWorkerOptions.workerSrc = workerUrl;

const BASELINE_TOLERANCE = 2.0;

interface Piece {
  x: number;
  y: number;
  run: Run;
}

export async function openPdf(data: ArrayBuffer): Promise<PDFDocumentProxy> {
  return getDocument({ data: new Uint8Array(data) }).promise;
}

function realFontName(page: PDFPageProxy, loadedName: string): string {
  return page.commonObjs.has(loadedName) ? (page.commonObjs.get(loadedName) as { name?: string }).name ?? "" : "";
}

async function pagePieces(page: PDFPageProxy): Promise<Piece[]> {
  await page.getOperatorList();
  const content = await page.getTextContent({ disableNormalization: true });
  const pieces: Piece[] = [];
  for (const item of content.items) {
    if (!("str" in item) || item.str === "") continue;
    const isAnu = ANU_FONTS.has(fontFamily(realFontName(page, item.fontName)));
    pieces.push({ x: item.transform[4] ?? 0, y: item.transform[5] ?? 0, run: { text: isAnu ? decodeSymbols(item.str) : item.str, isAnu } });
  }
  return pieces;
}

export async function pageLines(page: PDFPageProxy): Promise<Run[][]> {
  const pieces = (await pagePieces(page)).sort((left, right) => right.y - left.y);
  const rows: Piece[][] = [];
  for (const piece of pieces) {
    const row = rows[rows.length - 1];
    if (row !== undefined && (row[0]?.y ?? 0) - piece.y <= BASELINE_TOLERANCE) row.push(piece);
    else rows.push([piece]);
  }
  return rows.map((row) => row.sort((left, right) => left.x - right.x).map((piece) => piece.run));
}
