# SPDX-FileCopyrightText: 2025 Your Name
# SPDX-License-Identifier: MPL-2.0
"""Built-in plugin to implement OCR using Upstage Document OCR API."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Set

from PIL import Image

try:
    from dotenv import load_dotenv
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False

from ocrmypdf import hookimpl
from ocrmypdf._exec import upstage
from ocrmypdf._jobcontext import PageContext
from ocrmypdf.cli import numeric
from ocrmypdf.exceptions import BadArgsError, MissingDependencyError
from ocrmypdf.pluginspec import OcrEngine, OrientationConfidence

log = logging.getLogger(__name__)


def _load_env_vars() -> None:
    """Load environment variables from .env file if available."""
    if _DOTENV_AVAILABLE:
        # Look for .env file in project root (parent of src/)
        project_root = Path(__file__).parent.parent.parent.parent
        env_file = project_root / '.env'
        if env_file.exists():
            load_dotenv(env_file)
            log.debug(f"Loaded environment variables from {env_file}")
        else:
            log.debug(f"No .env file found at {env_file}")
    else:
        log.debug("python-dotenv not available, skipping .env file loading")


@hookimpl
def add_options(parser: argparse.ArgumentParser) -> None:
    """Add Upstage-specific command line options."""
    upstage = parser.add_argument_group(
        "Upstage OCR", "Advanced control of Upstage Document OCR API"
    )
    upstage.add_argument(
        '--upstage-api-key',
        metavar='KEY',
        help="Upstage API key (or set UPSTAGE_API_KEY environment variable)",
    )
    upstage.add_argument(
        '--upstage-endpoint',
        metavar='URL',
        default='https://api.upstage.ai/v1/document-digitization',
        help="Upstage API endpoint URL (default: %(default)s)",
    )
    upstage.add_argument(
        '--upstage-timeout',
        type=numeric(float, 0),
        default=180.0,
        metavar='SECONDS',
        help="Timeout for Upstage API requests (default: %(default)s)",
    )
    upstage.add_argument(
        '--upstage-confidence-threshold',
        type=numeric(float, 0.0, 1.0),
        default=0.0,
        metavar='THRESHOLD',
        help="Minimum confidence threshold for OCR results (0.0-1.0, default: %(default)s)",
    )
    upstage.add_argument(
        '--upstage-model',
        default='document-parse',
        metavar='MODEL',
        help="Upstage model to use (default: %(default)s)",
    )
    upstage.add_argument(
        '--upstage-chart-recognition',
        action='store_true',
        default=True,
        help="Enable chart-to-table conversion (default: %(default)s)",
    )
    upstage.add_argument(
        '--no-upstage-chart-recognition',
        action='store_false',
        dest='upstage_chart_recognition',
        help="Disable chart-to-table conversion",
    )
    upstage.add_argument(
        '--upstage-merge-tables',
        action='store_true', 
        default=True,
        help="Merge tables that span multiple pages (default: %(default)s)",
    )
    upstage.add_argument(
        '--no-upstage-merge-tables',
        action='store_false',
        dest='upstage_merge_tables',
        help="Disable multipage table merging",
    )


@hookimpl
def check_options(options: argparse.Namespace) -> None:
    """Validate Upstage-specific options."""
    # Load environment variables from .env file first
    _load_env_vars()
    
    # Get API key from options or environment
    api_key = getattr(options, 'upstage_api_key', None) or os.environ.get('UPSTAGE_API_KEY')
    if not api_key:
        raise MissingDependencyError(
            "Upstage API key is required. Use --upstage-api-key or set UPSTAGE_API_KEY environment variable.\n"
            "You can create a .env file in the project root with: UPSTAGE_API_KEY=your_key_here"
        )
    
    # Store resolved API key back to options for use by the engine
    options.upstage_api_key = api_key
    
    # Get endpoint from options or environment
    endpoint = (
        getattr(options, 'upstage_endpoint', None) 
        or os.environ.get('UPSTAGE_ENDPOINT')
        or 'https://api.upstage.ai/v1/document-digitization'
    )
    options.upstage_endpoint = endpoint
    
    # Validate endpoint URL
    if not endpoint.startswith(('http://', 'https://')):
        raise BadArgsError("Upstage endpoint must be a valid HTTP/HTTPS URL")
    
    # Get timeout from options or environment
    timeout_str = (
        str(getattr(options, 'upstage_timeout', None)) if getattr(options, 'upstage_timeout', None) is not None
        else os.environ.get('UPSTAGE_TIMEOUT', '180.0')
    )
    try:
        timeout = float(timeout_str)
        if timeout <= 0:
            raise BadArgsError(f"Upstage timeout must be positive: {timeout}")
        options.upstage_timeout = timeout
    except ValueError:
        raise BadArgsError(f"Invalid Upstage timeout value: {timeout_str}")
    
    # Validate model name
    valid_models = {'ocr', 'ocr-250904', 'document-parse', 'document-parse-250618'}  # Add more as available
    if options.upstage_model not in valid_models:
        log.warning(f"Unknown Upstage model '{options.upstage_model}'. Valid models: {valid_models}")
    
    log.debug(f"Upstage OCR configured: model={options.upstage_model}, endpoint={endpoint}")
    log.debug(f"Environment variables loaded from .env: {'Yes' if _DOTENV_AVAILABLE else 'No (python-dotenv not installed)'}")


@hookimpl
def validate(pdfinfo, options: argparse.Namespace) -> None:
    """Validate Upstage engine configuration for the specific PDF."""
    # Check page count limits (Upstage OCR API supports max 100 pages synchronously)
    page_count = len(pdfinfo)
    if page_count > 100:
        log.warning(
            f"PDF has {page_count} pages, but Upstage OCR API supports max 100 pages. "
            f"Only first 100 pages will be processed."
        )
    
    # Note: File size validation is handled per-page during processing
    # since OCRmyPDF processes individual page images, not the full PDF
    
    log.debug(f"Upstage OCR validation complete: {page_count} pages")


@hookimpl
def filter_ocr_image(page: PageContext, image: Image.Image) -> Image.Image:
    """Filter the image before OCR if needed for Upstage engine."""
    # Upstage API constraints:
    # - Max 200,000,000 pixels per page
    # - Supported formats: JPEG, PNG, BMP, TIFF, HEIC
    # - Optimal: minimum page width of 640px, text height ≥ 2.5% of image height
    
    width, height = image.size
    total_pixels = width * height
    
    # Check pixel limit (200M pixels)
    if total_pixels > 200_000_000:
        # Calculate downscale factor
        scale_factor = (200_000_000 / total_pixels) ** 0.5
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        
        log.info(f"Downscaling image from {width}x{height} to {new_width}x{new_height} for Upstage API")
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Ensure minimum width for good OCR quality
    if image.size[0] < 640:
        scale_factor = 640 / image.size[0]
        new_width = 640
        new_height = int(image.size[1] * scale_factor)
        
        log.info(f"Upscaling image from {image.size[0]}x{image.size[1]} to {new_width}x{new_height} for better OCR")
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    return image


class UpstageDocumentOcrEngine(OcrEngine):
    """Implements OCR using Upstage Document OCR API."""

    @staticmethod
    def version() -> str:
        """Returns the version of the Upstage OCR engine."""
        return str(upstage.version())

    @staticmethod
    def creator_tag(options: argparse.Namespace) -> str:
        """Returns the creator tag to identify this software's role in creating the PDF."""
        tag = '-PDF' if options.pdf_renderer == 'sandwich' else '-hOCR'
        return f"Upstage OCR{tag} {UpstageDocumentOcrEngine.version()}"

    def __str__(self) -> str:
        """Returns name of OCR engine and version."""
        return f"Upstage Document OCR {UpstageDocumentOcrEngine.version()}"

    @staticmethod
    def languages(options: argparse.Namespace) -> Set[str]:
        """Returns the set of all languages supported by Upstage engine."""
        return upstage.get_languages()

    @staticmethod
    def get_orientation(input_file: Path, options: argparse.Namespace) -> OrientationConfidence:
        """Returns the orientation of the image."""
        # Upstage OCR API doesn't provide orientation detection
        return upstage.get_orientation(
            input_file,
            options.upstage_api_key,
            options.upstage_endpoint,
            options.upstage_timeout,
        )

    @staticmethod
    def get_deskew(input_file: Path, options: argparse.Namespace) -> float:
        """Returns the deskew angle of the image, in degrees."""
        # Upstage OCR API doesn't provide deskew detection
        return upstage.get_deskew(
            input_file,
            options.upstage_api_key,
            options.upstage_endpoint,
            options.upstage_timeout,
        )

    @staticmethod
    def generate_hocr(
        input_file: Path, 
        output_hocr: Path, 
        output_text: Path, 
        options: argparse.Namespace
    ) -> None:
        """Called to produce a hOCR file from a page image and sidecar text file."""
        upstage.generate_hocr(
            input_file=input_file,
            output_hocr=output_hocr,
            output_text=output_text,
            api_key=options.upstage_api_key,
            endpoint=options.upstage_endpoint,
            timeout=options.upstage_timeout,
            model=options.upstage_model,
            confidence_threshold=options.upstage_confidence_threshold,
            chart_recognition=getattr(options, 'upstage_chart_recognition', True),
            merge_tables=getattr(options, 'upstage_merge_tables', True),
        )

    @staticmethod
    def generate_pdf(
        input_file: Path, 
        output_pdf: Path, 
        output_text: Path, 
        options: argparse.Namespace
    ) -> None:
        """Called to produce a text-only PDF from a page image."""
        upstage.generate_pdf(
            input_file=input_file,
            output_pdf=output_pdf,
            output_text=output_text,
            api_key=options.upstage_api_key,
            endpoint=options.upstage_endpoint,
            timeout=options.upstage_timeout,
            model=options.upstage_model,
            confidence_threshold=options.upstage_confidence_threshold,
        )


@hookimpl
def get_ocr_engine() -> UpstageDocumentOcrEngine:
    """Returns the Upstage OCR engine instance."""
    return UpstageDocumentOcrEngine()
