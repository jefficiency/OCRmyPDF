#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Your Name
# SPDX-License-Identifier: MPL-2.0
"""
Example plugin script for Upstage Document Parse Engine.

This demonstrates how to use the Upstage OCR engine as an external plugin.

Usage:
    ocrmypdf --plugin misc/upstage_plugin_example.py \
             --upstage-api-key YOUR_API_KEY \
             input.pdf output.pdf

This plugin can also be used as a template for creating a standalone
Upstage OCR plugin package.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Set

from ocrmypdf import hookimpl
from ocrmypdf._jobcontext import PageContext
from ocrmypdf.pluginspec import OcrEngine, OrientationConfidence

log = logging.getLogger(__name__)


@hookimpl
def add_options(parser: argparse.ArgumentParser) -> None:
    """Add Upstage-specific command line options."""
    upstage = parser.add_argument_group(
        "Upstage Document Parse", "Upstage Document Parse Engine Options"
    )
    upstage.add_argument(
        '--upstage-api-key',
        metavar='KEY',
        default=os.environ.get('UPSTAGE_API_KEY'),
        help="Upstage API key (or set UPSTAGE_API_KEY environment variable)",
    )
    upstage.add_argument(
        '--upstage-endpoint',
        metavar='URL',
        default='https://api.upstage.ai/v1/document-ai/ocr',
        help="Upstage API endpoint URL",
    )
    upstage.add_argument(
        '--upstage-timeout',
        type=float,
        default=180.0,
        metavar='SECONDS',
        help="Timeout for Upstage API requests",
    )


@hookimpl
def check_options(options: argparse.Namespace) -> None:
    """Validate Upstage options."""
    if not hasattr(options, 'upstage_api_key') or not options.upstage_api_key:
        raise ValueError(
            "Upstage API key is required. Use --upstage-api-key or set UPSTAGE_API_KEY environment variable."
        )


class UpstageOcrEngine(OcrEngine):
    """Upstage Document Parse Engine implementation."""

    @staticmethod
    def version() -> str:
        return "1.0.0"

    @staticmethod
    def creator_tag(options: argparse.Namespace) -> str:
        tag = '-PDF' if getattr(options, 'pdf_renderer', 'hocr') == 'sandwich' else '-hOCR'
        return f"Upstage{tag} {UpstageOcrEngine.version()}"

    def __str__(self) -> str:
        return f"Upstage Document Parse Engine {self.version()}"

    @staticmethod
    def languages(options: argparse.Namespace) -> Set[str]:
        # Return languages supported by Upstage
        return {
            'eng', 'kor', 'jpn', 'chi_sim', 'chi_tra', 'spa', 'fra', 'deu'
        }

    @staticmethod
    def get_orientation(input_file: Path, options: argparse.Namespace) -> OrientationConfidence:
        # TODO: Implement actual Upstage API call for orientation
        log.info(f"Getting orientation for {input_file} using Upstage API")
        return OrientationConfidence(angle=0, confidence=0.0)

    @staticmethod
    def get_deskew(input_file: Path, options: argparse.Namespace) -> float:
        # TODO: Implement actual Upstage API call for deskew
        log.info(f"Getting deskew angle for {input_file} using Upstage API")
        return 0.0

    @staticmethod
    def generate_hocr(
        input_file: Path, 
        output_hocr: Path, 
        output_text: Path, 
        options: argparse.Namespace
    ) -> None:
        """Generate hOCR using Upstage Document Parse API."""
        log.info(f"Generating hOCR for {input_file} using Upstage API")
        
        # TODO: Implement actual API integration
        # 1. Read image file
        # 2. Send to Upstage API
        # 3. Parse response
        # 4. Convert to hOCR format
        # 5. Write hOCR and text files
        
        # Placeholder: Create minimal valid hOCR
        hocr_content = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
    <title></title>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <meta name='ocr-system' content='Upstage Document Parse Engine 1.0.0' />
    <meta name='ocr-capabilities' content='ocr_page ocr_carea ocr_par ocr_line ocrx_word'/>
</head>
<body>
    <div class='ocr_page' id='page_1' title='image ""; bbox 0 0 1000 1000; ppageno 0'>
        <div class='ocr_carea' id='block_1_1' title="bbox 0 0 1000 1000">
            <p class='ocr_par' dir='ltr' id='par_1' title="bbox 0 0 1000 1000">
                <span class='ocr_line' id='line_1' title="bbox 0 0 1000 1000">
                    <span class='ocrx_word' id='word_1' title="bbox 0 0 1000 1000">PLACEHOLDER</span>
                </span>
            </p>
        </div>
    </div>
</body>
</html>'''
        
        output_hocr.write_text(hocr_content, encoding='utf-8')
        output_text.write_text('PLACEHOLDER', encoding='utf-8')

    @staticmethod
    def generate_pdf(
        input_file: Path, 
        output_pdf: Path, 
        output_text: Path, 
        options: argparse.Namespace
    ) -> None:
        """Generate text-only PDF using Upstage Document Parse API."""
        log.info(f"Generating text-only PDF for {input_file} using Upstage API")
        
        # TODO: Implement actual API integration
        # 1. Read image file
        # 2. Send to Upstage API  
        # 3. Parse response with text and coordinates
        # 4. Create text-only PDF with invisible text
        # 5. Write PDF and text files
        
        # Placeholder: Create empty PDF
        output_pdf.write_bytes(b'')
        output_text.write_text('PLACEHOLDER', encoding='utf-8')


@hookimpl
def get_ocr_engine() -> UpstageOcrEngine:
    """Return the Upstage OCR engine."""
    return UpstageOcrEngine()


if __name__ == "__main__":
    print("This is an OCRmyPDF plugin for Upstage Document Parse Engine.")
    print("Use it with: ocrmypdf --plugin upstage_plugin_example.py input.pdf output.pdf")
