"""Runner that invokes OCRmyPDF with the Upstage engine per PRD.

Responsibilities:
- For ≤100-page PDFs, run OCR once with Upstage builtin plugin using hOCR path
- For >100 pages, split into chunks (≤100 pages), OCR each sequentially, then merge
- Return (output_path, status) where status in {ok, skipped, failed}
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from dotenv import load_dotenv
from ocrmypdf.api import Verbosity, configure_logging, ocr
from ocrmypdf._plugin_manager import get_plugin_manager
import pikepdf

from .pager import merge_chunks, split_by_constraints, split_fixed_pages


MAX_PAGES_PER_REQUEST = 100


@dataclass(frozen=True)
class OcrResult:
    output_path: Path
    status: str  # ok | skipped | failed
    message: str = ""


def _build_plugin_manager():
    return get_plugin_manager(plugins=[], builtins=True)


def _ensure_env_loaded() -> None:
    # Load .env from project root if present
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(dotenv_path=project_root / '.env')


def _compute_output_path(input_pdf: Path) -> Path:
    return input_pdf.with_name(f"{input_pdf.stem}_upocr.pdf")


def _page_count(path: Path) -> int:
    with pikepdf.open(str(path)) as pdf:
        return len(pdf.pages)


def ocr_single(input_pdf: Path, *, force: bool = False, force_ocr: bool = False) -> Tuple[Path, str]:
    """Run OCR for one PDF (≤100 pages) and return (output_path, status).

    force: overwrite existing output if newer logic would skip
    force_ocr: pass through to OCRmyPDF (force OCR even if text exists)
    """
    input_pdf = Path(input_pdf)
    output_pdf = _compute_output_path(input_pdf)
    if not force and output_pdf.exists() and output_pdf.stat().st_mtime >= input_pdf.stat().st_mtime:
        return output_pdf, "skipped"

    _ensure_env_loaded()
    api_key = os.environ.get('UPSTAGE_API_KEY')
    if not api_key:
        return output_pdf, "failed"

    pm = _build_plugin_manager()
    # Configure default logging similar to CLI (no verbose by default)
    configure_logging(Verbosity.default, plugin_manager=pm)

    exit_code = ocr(
        input_file=input_pdf,
        output_file=output_pdf,
        output_type='pdf',
        pdf_renderer='hocr',
        upstage_api_key=api_key,
        upstage_endpoint='https://api.upstage.ai/v1/document-digitization',
        upstage_model='document-parse',
        upstage_chart_recognition=True,
        upstage_merge_tables=True,
        force_ocr=force_ocr,
        skip_text=not force_ocr,
        progress_bar=False,
        plugin_manager=pm,
    )
    return output_pdf, ("ok" if int(exit_code) == 0 else "failed")


def ocr_document(input_pdf: Path, *, force: bool = False, force_ocr: bool = False) -> Tuple[Path, str]:
    """Orchestrate full flow including chunking if needed (>100 pages)."""
    input_pdf = Path(input_pdf)
    try:
        total_pages = _page_count(input_pdf)
    except Exception:
        return _compute_output_path(input_pdf), "failed"

    if total_pages <= MAX_PAGES_PER_REQUEST:
        return ocr_single(input_pdf, force=force, force_ocr=force_ocr)

    # Chunking path: split with both page and size constraints
    result = split_by_constraints(input_pdf, max_pages_per_chunk=MAX_PAGES_PER_REQUEST, max_megabytes_per_chunk=50.0)
    chunk_outputs: List[Path] = []
    for chunk in result.output_chunks:
        out_path = chunk.with_name(f"{chunk.stem}_upocr.pdf")
        # Process each chunk
        out, status = ocr_single(chunk, force=True, force_ocr=force_ocr)
        if status != "ok":
            return _compute_output_path(input_pdf), "failed"
        # The single call produced chunk_upocr.pdf; ensure path
        if out != out_path:
            out_path = out
        chunk_outputs.append(out_path)

    # For merged multi-chunk outputs, use _upocr_merged suffix
    final_out = input_pdf.with_name(f"{input_pdf.stem}_upocr_merged.pdf")
    merge_chunks(chunk_outputs, final_out)
    return final_out, "ok"


