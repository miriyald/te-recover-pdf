import { parseMapping, type Mapping } from "./mapping";

const sources = import.meta.glob("../../fonts/*/*/mapping.tsv", { query: "?raw", import: "default", eager: true }) as Record<string, string>;

export interface NamedMapping {
  label: string;
  mapping: Mapping;
}

export function bundledMappings(): NamedMapping[] {
  return Object.entries(sources).map(([path, tsv]) => {
    const [font, approach] = path.split("/").slice(-3, -1);
    return { label: `${font} / ${approach}`, mapping: parseMapping(tsv) };
  });
}
