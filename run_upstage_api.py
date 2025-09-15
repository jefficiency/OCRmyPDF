#!/usr/bin/env python3
"""
Run OCRmyPDF using the Upstage OCR engine via the public API.

This script forces the Upstage engine by constructing a curated plugin manager
that excludes Tesseract and includes necessary non-engine builtins.

Usage:
  uv run python run_upstage_api.py \
    --input img_stock_report.pdf \
    --output output_upstage.pdf

Requirements:
  - UPSTAGE_API_KEY must be available in the environment (the builtin plugin
    will also attempt to load .env at the project root).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from ocrmypdf.api import ocr, configure_logging, Verbosity
from ocrmypdf._plugin_manager import get_plugin_manager
from dotenv import load_dotenv


def build_plugin_manager():
    """Create a plugin manager that loads all builtins (Upstage included).

    Note: Builtins are registered in sorted order, and hooks are called in
    last-registered-first order, so the Upstage engine (module name sorts
    after Tesseract) is called before Tesseract for the firstresult hook.
    This keeps Tesseract's CLI options available while selecting Upstage.
    """
    return get_plugin_manager(plugins=[], builtins=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run OCR with Upstage via OCRmyPDF API')
    parser.add_argument('--input', '-i', default='img_stock_report.pdf', help='Input PDF path')
    parser.add_argument('--output', '-o', default='output_upstage.pdf', help='Output PDF path')
    parser.add_argument('--model', default='document-parse', help='Upstage model alias or version')
    parser.add_argument('--no-chart-recognition', action='store_true', help='Disable chart-to-table conversion')
    parser.add_argument('--no-merge-tables', action='store_true', help='Disable merging multipage tables')
    parser.add_argument('--force-ocr', action='store_true', help='Force OCR even if text is detected')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_file = Path(args.input)
    output_file = Path(args.output)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Load .env from project root explicitly
    load_dotenv(dotenv_path=Path(__file__).parent / '.env')

    # Friendly pre-check; the plugin will enforce this too during check_options
    if not os.environ.get('UPSTAGE_API_KEY'):
        raise RuntimeError(
            'UPSTAGE_API_KEY is not set. Export it or create a .env at project root.'
        )

    pm = build_plugin_manager()
    configure_logging(Verbosity.debug if args.verbose else Verbosity.default, plugin_manager=pm)

    exit_code = ocr(
        input_file=input_file,
        output_file=output_file,
        pdf_renderer='hocr',

        # Upstage-specific options (read by builtin plugin)
        upstage_api_key=os.environ.get('UPSTAGE_API_KEY'),
        upstage_endpoint='https://api.upstage.ai/v1/document-digitization',
        upstage_model=args.model,
        upstage_chart_recognition=not args.no_chart_recognition,
        upstage_merge_tables=not args.no_merge_tables,

        # Pipeline behavior
        force_ocr=args.force_ocr,
        skip_text=False,
        progress_bar=True,

        # Ensure our curated plugin selection is used
        plugin_manager=pm,
    )

    print(f"Done. Exit code: {exit_code}")
    print(f"Output: {output_file.resolve()}")
    return int(exit_code)


if __name__ == '__main__':
    raise SystemExit(main())


