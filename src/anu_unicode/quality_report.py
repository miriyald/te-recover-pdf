import csv
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from anu_unicode.quality import GroundTruthQuality, PageQuality, combine

TOP_CONFUSIONS = 20
PAGE_COLUMNS = (
    "page", "words", "matched", "unmatched", "disagreements", "agreement_rate", "unresolved",
    "mean_confidence_agreeing", "mean_confidence_disagreeing",
)


@dataclass(frozen=True)
class QualityReport:
    document: str
    document_pages: int
    pages: Sequence[PageQuality]
    ground_truth: Sequence[GroundTruthQuality]


def _page_row(item: PageQuality) -> dict[str, float | int]:
    return {
        "page": item.page, "words": item.words, "matched": item.matched, "unmatched": item.unmatched,
        "disagreements": item.disagreements, "agreement_rate": round(item.agreement_rate, 4), "unresolved": item.unresolved,
        "mean_confidence_agreeing": round(item.mean_confidence_agreeing, 1),
        "mean_confidence_disagreeing": round(item.mean_confidence_disagreeing, 1),
    }


def _write_csv(path: Path, pages: Sequence[PageQuality]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAGE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(_page_row(item) for item in pages)


def _write_json(path: Path, report: QualityReport) -> None:
    total = combine(report.pages)
    payload = {
        "document": report.document,
        "document_pages": report.document_pages,
        "measured_pages": len(report.pages),
        "total": _page_row(total),
        "pages": [_page_row(item) for item in report.pages],
        "confusions": [{"ocr": ocr, "converted": converted, "count": count} for (ocr, converted), count in total.confusions.most_common()],
        "ground_truth": [asdict(item) for item in report.ground_truth],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _percent(value: float) -> str:
    return f"{value:.1%}"


def _headline(report: QualityReport, total: PageQuality) -> list[str]:
    return [
        f"# OCR quality report: {report.document}",
        "",
        (f"**{total.disagreements:,} of {total.matched:,} matched words ({_percent(1 - total.agreement_rate)}) "
         f"were read differently by Tesseract and by the conversion, across {len(report.pages)} of {report.document_pages} pages.** "
         f"{total.unresolved:,} words are still unresolved (`⟦…⟧`)."),
        "",
        "## A. Tesseract vs converted text",
        "",
        ("A disagreement means Tesseract and the conversion produced different text for the same word box. "
         "Either side can be wrong, so this counts where the process changed the OCR reading, not proven corrections. "
         "Section B measures real accuracy."),
        "",
        "| Metric | Value |", "|---|---|",
        f"| Pages measured | {len(report.pages)} of {report.document_pages} |",
        f"| Words in the PDF text layer | {total.words:,} |",
        f"| Words matched to an OCR word | {total.matched:,} |",
        f"| Words with no OCR match (not counted as disagreements) | {total.unmatched:,} |",
        f"| Disagreements | {total.disagreements:,} |",
        f"| Agreement rate | {_percent(total.agreement_rate)} |",
        f"| Unresolved words | {total.unresolved:,} |",
        f"| Mean Tesseract confidence, agreeing words | {total.mean_confidence_agreeing:.1f} |",
        f"| Mean Tesseract confidence, disagreeing words | {total.mean_confidence_disagreeing:.1f} |",
        "",
        "```mermaid",
        "pie showData",
        '    title Matched words',
        f'    "Agree" : {total.agreements}',
        f'    "Disagree" : {total.disagreements}',
        "```",
        "",
    ]


def _confusions(total: PageQuality) -> list[str]:
    lines = ["### Most common character differences", "", "| Tesseract read | Converted to | Count |", "|---|---|---|"]
    lines += [f"| {ocr} | {converted} | {count} |" for (ocr, converted), count in total.confusions.most_common(TOP_CONFUSIONS)]
    return lines + [""]


def _per_page(pages: Sequence[PageQuality]) -> list[str]:
    lines = ["### Per page", "", "| Page | Words | Matched | Disagreements | Agreement | Unresolved |", "|---|---|---|---|---|---|"]
    lines += [
        f"| {item.page} | {item.words} | {item.matched} | {item.disagreements} | {_percent(item.agreement_rate)} | {item.unresolved} |"
        for item in pages
    ]
    return lines + [""]


def _ground_truth(items: Sequence[GroundTruthQuality]) -> list[str]:
    lines = ["## B. Accuracy against verified text", ""]
    if not items:
        return lines + ["No verified pages found.", ""]
    words = sum(item.reference_words for item in items)
    converted = sum(item.converted_word_errors for item in items)
    ocr = sum(item.ocr_word_errors for item in items)
    lines += [
        (f"Sample: {len(items)} verified pages, {words:,} reference words. "
         "Word error rate (WER) and character error rate (CER); lower is better."),
        "",
        (f"**Overall: Tesseract got {ocr:,} words wrong ({_percent(ocr / words)}); "
         f"the conversion got {converted:,} wrong ({_percent(converted / words)}).**"),
        "",
        ("| Page | Reference words | Tesseract word errors | Converted word errors "
         "| Tesseract WER | Converted WER | Tesseract CER | Converted CER |"),
        "|---|---|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {item.page} | {item.reference_words} | {item.ocr_word_errors} | {item.converted_word_errors} | "
        f"{_percent(item.ocr_word_error_rate)} | {_percent(item.converted_word_error_rate)} | "
        f"{_percent(item.ocr_character_error_rate)} | {_percent(item.converted_character_error_rate)} |"
        for item in items
    ]
    return lines + [""]


def write_quality_report(out: Path, report: QualityReport) -> None:
    out.mkdir(parents=True, exist_ok=True)
    total = combine(report.pages)
    lines = _headline(report, total) + _confusions(total) + _per_page(report.pages) + _ground_truth(report.ground_truth)
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    _write_csv(out / "page-metrics.csv", report.pages)
    _write_json(out / "quality.json", report)
