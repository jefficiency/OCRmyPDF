#!/usr/bin/env python3
"""
Unified Upstage tests aligned with run_upstage_api.py.

Modes:
  - direct:  Call Upstage engine directly to generate hOCR + text sidecar
  - analyze: Generate hOCR then analyze structure/quality
  - run:     Full OCRmyPDF pipeline to produce an OCR'd PDF (like the runner)

Defaults:
  - Model: document-parse
  - Coordinates enabled via exec client; chart recognition and merge tables on
  - pdf_renderer: hocr
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

from ocrmypdf.api import ocr, configure_logging, Verbosity
from ocrmypdf._plugin_manager import get_plugin_manager
from ocrmypdf.builtin_plugins.upstage_ocr import (
    UpstageDocumentOcrEngine,
    check_options,
)


def build_plugin_manager():
    """Create a plugin manager that loads all builtins (Upstage included).

    Note: Builtins are registered in sorted order, and hooks are called in
    last-registered-first order, so the Upstage engine (module name sorts
    after Tesseract) is called before Tesseract for the firstresult hook.
    This keeps Tesseract's CLI options available while selecting Upstage.
    """
    return get_plugin_manager(plugins=[], builtins=True)


def make_options(model: str = "document-parse") -> argparse.Namespace:
    """Create an options namespace consistent with the builtin plugin."""
    options = argparse.Namespace()
    options.upstage_api_key = None
    options.upstage_endpoint = "https://api.upstage.ai/v1/document-digitization"
    options.upstage_timeout = 180.0
    options.upstage_model = model
    options.upstage_confidence_threshold = 0.0
    options.upstage_chart_recognition = True
    options.upstage_merge_tables = True
    options.pdf_renderer = "hocr"
    # Let plugin resolve env and validate
    check_options(options)
    return options


def analyze_hocr_structure(hocr_file: Path) -> Dict[str, Any]:
    """Analyze hOCR structure with basic stats and coordinate sanity."""
    from xml.etree import ElementTree as ET

    content = hocr_file.read_text(encoding="utf-8")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        return {"error": f"Invalid XML: {e}"}

    namespaces = {"html": "http://www.w3.org/1999/xhtml"} if "xmlns" in content else {}

    def find(xpath: str):
        if namespaces:
            xpath_ns = xpath.replace("//", ".//html:")
            try:
                return root.findall(xpath_ns, namespaces)
            except Exception:
                pass
        return root.findall(xpath)

    stats: Dict[str, Any] = {
        "total_size_bytes": len(content),
        "pages": len(find(".//div[@class='ocr_page']")),
        "blocks": len(find(".//div[@class='ocr_carea']")),
        "paragraphs": len(find(".//p")),
        "lines": len(find(".//span[@class='ocr_line']")),
        "words": len(find(".//span[@class='ocrx_word']")),
        "headers": len(find(".//p[@class='ocr_header']")),
        "captions": len(find(".//p[@class='ocr_caption']")),
        "textfloats": len(find(".//p[@class='ocr_textfloat']")),
    }

    bbox_elements = find(".//*[@title]") if namespaces else root.findall(".//*[@title]")
    bbox_count = 0
    valid_bbox_count = 0
    for elem in bbox_elements:
        title = elem.get("title", "")
        if "bbox" in title:
            bbox_count += 1
            try:
                bbox_part = title.split("bbox")[1].split(";")[0].strip()
                coords = bbox_part.split()
                if len(coords) == 4 and all(c.isdigit() for c in coords):
                    valid_bbox_count += 1
            except Exception:
                pass
    stats["bbox_elements"] = bbox_count
    stats["valid_bboxes"] = valid_bbox_count
    stats["bbox_quality"] = (valid_bbox_count / bbox_count * 100) if bbox_count else 0

    word_elements = find(".//span[@class='ocrx_word']")
    non_empty_words = sum(1 for e in word_elements if e.text and e.text.strip())
    stats["non_empty_words"] = non_empty_words
    stats["text_coverage"] = (non_empty_words / len(word_elements) * 100) if word_elements else 0
    return stats


def mode_direct(input_path: Path) -> int:
    print("🧪 Direct Upstage Engine → hOCR test")
    if not input_path.exists():
        print(f"❌ Input not found: {input_path}")
        return 1

    options = make_options(model="document-parse")
    engine = UpstageDocumentOcrEngine()

    with tempfile.TemporaryDirectory() as td:
        out_hocr = Path(td) / "direct.hocr"
        out_txt = Path(td) / "direct.txt"
        engine.generate_hocr(
            input_file=input_path,
            output_hocr=out_hocr,
            output_text=out_txt,
            options=options,
        )
        if not out_hocr.exists():
            print("❌ hOCR was not generated")
            return 1
        print(f"✅ hOCR generated: {out_hocr} ({out_hocr.stat().st_size} bytes)")
        print(f"✅ Text generated: {out_txt} ({out_txt.stat().st_size} bytes)")
        preview = "\n".join(out_hocr.read_text(encoding="utf-8").splitlines()[:8])
        print("📄 hOCR preview:\n" + preview)
    print("🎉 Direct test completed")
    return 0


def mode_analyze(input_path: Path) -> int:
    print("🔍 Analyze Upstage hOCR quality")
    if not input_path.exists():
        print(f"❌ Input not found: {input_path}")
        return 1

    options = make_options(model="document-parse")
    engine = UpstageDocumentOcrEngine()

    with tempfile.TemporaryDirectory() as td:
        out_hocr = Path(td) / "analysis.hocr"
        out_txt = Path(td) / "analysis.txt"
        engine.generate_hocr(
            input_file=input_path,
            output_hocr=out_hocr,
            output_text=out_txt,
            options=options,
        )
        if not out_hocr.exists():
            print("❌ hOCR was not generated")
            return 1
        stats = analyze_hocr_structure(out_hocr)
        if "error" in stats:
            print(f"❌ Analysis error: {stats['error']}")
            return 1

        print("📋 hOCR Quality Report:")
        print(f"  - File size: {stats['total_size_bytes']:,} bytes")
        print(f"  - Pages: {stats['pages']}")
        print(f"  - Blocks: {stats['blocks']}")
        print(f"  - Paragraphs: {stats['paragraphs']}")
        print(f"  - Lines: {stats['lines']}")
        print(f"  - Words: {stats['words']}")
        print(f"  - Headers: {stats['headers']}")
        print(f"  - Captions: {stats['captions']}")
        print(f"  - Text floats: {stats['textfloats']}")
        print(f"  - Bbox elements: {stats['bbox_elements']}")
        print(f"  - Valid bboxes: {stats['valid_bboxes']}")
        print(f"  - Bbox quality: {stats['bbox_quality']:.1f}%")
        print(f"  - Non-empty words: {stats['non_empty_words']}")
        print(f"  - Text coverage: {stats['text_coverage']:.1f}%")
    print("🎉 Analysis completed")
    return 0


def mode_run(input_path: Path, output_path: Path, verbose: bool) -> int:
    print("🚀 Full pipeline via OCRmyPDF API → OCR'd PDF")
    if not input_path.exists():
        print(f"❌ Input not found: {input_path}")
        return 1

    # Load env; runner will enforce presence of API key
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
    if not os.environ.get("UPSTAGE_API_KEY"):
        print("❌ UPSTAGE_API_KEY is not set (env or .env)")
        return 1

    pm = build_plugin_manager()
    configure_logging(Verbosity.debug if verbose else Verbosity.default, plugin_manager=pm)

    exit_code = ocr(
        input_file=input_path,
        output_file=output_path,
        pdf_renderer="hocr",
        upstage_api_key=os.environ.get("UPSTAGE_API_KEY"),
        upstage_endpoint="https://api.upstage.ai/v1/document-digitization",
        upstage_model="document-parse",
        upstage_chart_recognition=True,
        upstage_merge_tables=True,
        force_ocr=True,
        skip_text=False,
        progress_bar=True,
        plugin_manager=pm,
    )
    print(f"Done. Exit code: {exit_code}")
    print(f"Output: {output_path.resolve()}")
    return int(exit_code)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Unified Upstage tests aligned with runner")
    p.add_argument("--mode", choices=["direct", "analyze", "run"], default="direct")
    p.add_argument("--input", "-i", help="Input file path")
    p.add_argument("--output", "-o", help="Output file path (run mode)")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # Defaults per mode
    if args.mode in {"direct", "analyze"}:
        input_path = Path(args.input or "test_page1.pdf")
        if args.mode == "direct":
            return mode_direct(input_path)
        return mode_analyze(input_path)

    # run mode
    input_path = Path(args.input or "img_stock_report.pdf")
    output_path = Path(args.output or "output_upstage.pdf")
    return mode_run(input_path, output_path, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())


