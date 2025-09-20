"""Runner that invokes OCRmyPDF with the Upstage engine per PRD.

Responsibilities:
- For ≤100-page PDFs, run OCR once with Upstage builtin plugin using hOCR path
- For >100 pages, split into chunks (≤100 pages), OCR each sequentially, then merge
- Return (output_path, status) where status in {ok, skipped, failed}
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from ocrmypdf.api import Verbosity, configure_logging, ocr
from ocrmypdf._plugin_manager import get_plugin_manager
from ocrmypdf._exec.upstage import UpstageAPIClient
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


def _ensure_dir(path: Path) -> Path:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return path


def _compute_json_output_path(input_pdf: Path) -> Path:
    """Return JSON path under a json/ directory next to the given PDF.

    For a file like /dir/foo.pdf, returns /dir/json/foo_upocr.json
    For a chunk like /dir/chunks/foo_chunk000000.pdf, returns /dir/json/foo_chunk000000_upocr.json
    """
    input_pdf = Path(input_pdf)
    json_dir = _ensure_dir(input_pdf.parent / "json")
    return json_dir / f"{input_pdf.stem}_upocr.json"


def _compute_elements_json_output_path(input_pdf: Path) -> Path:
    """Return merged-elements JSON path under json/ next to the given PDF.

    For a file like /dir/foo.pdf, returns /dir/json/foo_elements_upocr.json
    """
    input_pdf = Path(input_pdf)
    json_dir = _ensure_dir(input_pdf.parent / "json")
    return json_dir / f"{input_pdf.stem}_elements_upocr.json"


def _request_upstage_json(
    document_path: Path,
    *,
    api_key: str,
    endpoint: str,
    model: str = "document-parse",
    chart_recognition: bool = True,
    merge_tables: bool = True,
    timeout: float = 180.0,
) -> Dict[str, Any]:
    """Call Upstage Document Digitization API and return the raw JSON.

    This reuses the existing HTTP client used by the plugin. The API supports
    sending PDFs directly and will return multi-page JSON (≤100 pages per call).
    """
    client = UpstageAPIClient(api_key, endpoint, timeout)
    # The client method name mentions image, but the API accepts PDFs as well.
    return client.ocr_image(
        Path(document_path), model=model, chart_recognition=chart_recognition, merge_tables=merge_tables
    )


def _safe_write_json(data: Any, path: Path) -> None:
    path = Path(path)
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # Do not fail the overall OCR if JSON persistence encounters an I/O issue
        pass

def _merge_chunk_jsons(chunk_json_paths: List[Path]) -> List[Dict[str, Any]]:
    """Append per-chunk element objects without transformation.

    Rules:
    - If a chunk JSON is a list, extend with that list.
    - If a chunk JSON is a dict and contains an 'elements' list, extend with that list.
    - Otherwise, append the whole object as-is (best-effort preservation).
    """
    merged: List[Dict[str, Any]] = []
    for p in chunk_json_paths:
        try:
            obj = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            obj = None

        if isinstance(obj, list):
            for item in obj:
                merged.append(item)  # type: ignore[arg-type]
        elif isinstance(obj, dict) and isinstance(obj.get("elements"), list):
            for item in obj["elements"]:
                merged.append(item)  # type: ignore[arg-type]
        elif obj is not None:
            merged.append(obj)  # type: ignore[arg-type]
    return merged


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
    status = "ok" if int(exit_code) == 0 else "failed"

    # Best-effort: persist full-document JSON next to the PDF
    if status == "ok":
        try:
            endpoint = 'https://api.upstage.ai/v1/document-digitization'
            response = _request_upstage_json(
                input_pdf,
                api_key=api_key,
                endpoint=endpoint,
                model='document-parse',
                chart_recognition=True,
                merge_tables=True,
            )
            json_out = _compute_json_output_path(input_pdf)
            _safe_write_json(response, json_out)
        except Exception:
            # Do not fail the OCR on JSON persistence failures
            pass

    return output_pdf, status


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
    chunk_jsons: List[Path] = []
    for chunk in result.output_chunks:
        # Chunk outputs go under chunks/; ensure directory exists
        chunk_dir = _ensure_dir(input_pdf.parent / "chunks")
        out_path = chunk_dir / f"{Path(chunk).stem}_upocr.pdf"
        # Process each chunk (also persists per-chunk JSON via ocr_single)
        out, status = ocr_single(chunk, force=True, force_ocr=force_ocr)
        if status != "ok":
            return _compute_output_path(input_pdf), "failed"
        # Move/rename if OCR layer wrote next to chunk; prefer chunks/ path
        try:
            if Path(out) != out_path:
                Path(out).replace(out_path)
        except Exception:
            out_path = Path(out)
        chunk_outputs.append(out_path)
        chunk_jsons.append(_compute_json_output_path(chunk))

    # Merge chunk PDFs
    final_out = input_pdf.with_name(f"{input_pdf.stem}_upocr_merged.pdf")
    merge_chunks(chunk_outputs, final_out)

    # Merge JSONs into one file under json/, named with elements_upocr
    try:
        merged_json = _merge_chunk_jsons(chunk_jsons)
        merged_json_path = _compute_elements_json_output_path(input_pdf)
        # Wrap in an object so the result is a JSON object, not a bare array
        _safe_write_json({"merged": merged_json}, merged_json_path)
    except Exception:
        # Non-fatal if JSON merge fails
        pass

    return final_out, "ok"


