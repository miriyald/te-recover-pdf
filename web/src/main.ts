import type { PDFDocumentProxy } from "pdfjs-dist";
import { convertAnu, convertLine, coverageRatio, newCoverage, type Coverage } from "./convert";
import { pageLines, openPdf } from "./extract";
import { parseMapping, type Mapping } from "./mapping";
import { bundledMappings, type NamedMapping } from "./mappings";
import { decodeSymbols } from "./profile";

function element<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (found === null) throw new Error(`Missing #${id}`);
  return found as T;
}

const mappingSelect = element<HTMLSelectElement>("mapping");
const customMapping = element<HTMLInputElement>("custom-mapping");
const pdfInput = element<HTMLInputElement>("pdf");
const samplePage = element<HTMLInputElement>("sample-page");
const sample = element("sample");
const coverageLabel = element("coverage");
const convertButton = element<HTMLButtonElement>("convert");
const progress = element<HTMLProgressElement>("progress");
const pasted = element<HTMLTextAreaElement>("pasted");
const pastedOutput = element<HTMLTextAreaElement>("pasted-output");
const errorLabel = element("error");

const options: NamedMapping[] = bundledMappings();
let customMappingOption: NamedMapping | null = null;
let pdf: PDFDocumentProxy | null = null;

function currentMapping(): Mapping | null {
  const index = Number(mappingSelect.value);
  return customMappingOption?.mapping ?? options[index]?.mapping ?? null;
}

async function convertPage(document: PDFDocumentProxy, number: number, mapping: Mapping, coverage: Coverage): Promise<string> {
  const lines = await pageLines(await document.getPage(number));
  return lines.map((line) => convertLine(line, mapping, coverage)).join("\n");
}

async function showSample(): Promise<void> {
  const mapping = currentMapping();
  if (pdf === null || mapping === null) return;
  const coverage = newCoverage();
  const number = Math.min(Math.max(1, samplePage.valueAsNumber || 1), pdf.numPages);
  sample.textContent = await convertPage(pdf, number, mapping, coverage);
  coverageLabel.textContent = `Page ${number} of ${pdf.numPages}: ${(coverageRatio(coverage) * 100).toFixed(1)}% of glyphs mapped`;
}

function showPasted(): void {
  const mapping = currentMapping();
  pastedOutput.value = mapping === null ? "" : convertAnu(decodeSymbols(pasted.value), mapping, newCoverage());
}

function download(text: string, name: string): void {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  link.download = name;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function convertAll(): Promise<void> {
  const mapping = currentMapping();
  if (pdf === null || mapping === null) return;
  const pages: string[] = [];
  progress.hidden = false;
  progress.max = pdf.numPages;
  for (let number = 1; number <= pdf.numPages; number++) {
    pages.push(await convertPage(pdf, number, mapping, newCoverage()));
    progress.value = number;
  }
  progress.hidden = true;
  const baseName = pdfInput.files?.[0]?.name.replace(/\.pdf$/i, "") ?? "converted";
  download(pages.join("\n\n"), `${baseName}.unicode.txt`);
}

function guarded(action: () => Promise<void> | void): () => Promise<void> {
  return async () => {
    errorLabel.textContent = "";
    try {
      await action();
    } catch (error) {
      errorLabel.textContent = error instanceof Error ? error.message : String(error);
    }
  };
}

options.forEach(({ label }, index) => mappingSelect.add(new Option(label, String(index))));

mappingSelect.addEventListener("change", guarded(() => {
  customMappingOption = null;
  return Promise.all([showSample(), showPasted()]).then(() => undefined);
}));
customMapping.addEventListener("change", guarded(async () => {
  const file = customMapping.files?.[0];
  if (file === undefined) return;
  customMappingOption = { label: file.name, mapping: parseMapping(await file.text()) };
  await showSample();
  showPasted();
}));
pdfInput.addEventListener("change", guarded(async () => {
  const file = pdfInput.files?.[0];
  if (file === undefined) return;
  pdf = await openPdf(await file.arrayBuffer());
  samplePage.max = String(pdf.numPages);
  convertButton.disabled = false;
  await showSample();
}));
samplePage.addEventListener("change", guarded(showSample));
convertButton.addEventListener("click", guarded(convertAll));
pasted.addEventListener("input", showPasted);
