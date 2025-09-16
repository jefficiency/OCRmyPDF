## UpOCR – Architecture

### Overview

UpOCR is a thin orchestration module that scans directories and invokes OCRmyPDF with the Upstage engine. It deliberately avoids coupling to OCRmyPDF internals: interaction is via the public API and plugin system.

The Upstage synchronous API has a hard limit of 100 pages per request (see `jdocs/upstage_reference.md`). Therefore, documents over 100 pages must be split into ≤100-page chunks, each chunk processed independently, and then merged back into a single output PDF while preserving page order.

### Components

1) Scanner (`upocr.scanner`)

- Responsibility: recursively walk root directories and yield candidate PDFs.
- Inputs: `roots: list[Path]`, include/exclude globs, ignore patterns.
- Outputs: iterator of `Path` for input files, skipping any file that already has a corresponding `_upocr.pdf` unless `--force`.
- Notes: use `pathlib.Path.rglob` + fnmatch filtering; ensure `_upocr` suffix rule is consistent.

2) Runner (`upocr.runner`)

- Responsibility: invoke OCRmyPDF with curated plugin manager (builtins=True) and Upstage options.
- Behavior: similar to `run_upstage_api.py` with `pdf_renderer='hocr'`, model `document-parse`, chart/table options enabled.
- Rate limiting: rely on existing Upstage exec client per-request throttle (≈1 RPS) and also bound concurrency.
- Error handling: non-fatal per-file; return a result object with status and error message if any.

3) Paginator/Merger (`upocr.pager`)

- Responsibility: handle the 100-page limit by splitting large PDFs into chunks of ≤100 pages and merging chunk outputs back into a single result.
- Inputs: input PDF path, `max_pages_per_chunk=100`.
- Outputs: list of chunk paths for processing; merged final output path.
- Notes: page order must be preserved; outlines/metadata preservation is a best-effort in a later iteration.

4) Metadata Preserver (`upocr.meta`)

- Responsibility: preserve source document metadata when producing the final output.
- Scope: document info (Title, Author, Subject, Keywords, Creator, Producer, CreationDate, ModDate), XMP `/Metadata` stream, page labels (`/PageLabels`), tagged PDF flag (`/MarkInfo/Marked`), AcroForm presence/signature flags (do not copy actual signatures), and outlines/bookmarks (`/Outlines`).
- Approach: read from the source PDF and apply to the final merged output using pikepdf. Outlines must be remapped to new page objects by page index. Reference info available via `pdfinfo.PdfInfo` for capabilities like tagged flag, forms/signatures, page count; for DocInfo/XMP/Outlines use pikepdf directly.

5) CLI (`upocr.cli`)

- Responsibility: user interface, argument parsing, concurrency control, progress and summary.
- Concurrency: `concurrent.futures.ThreadPoolExecutor` or `ProcessPoolExecutor` with `--max-workers`.
- Logging: structured per-file events; final summary.

### Data Flow

```mermaid
flowchart TD
    A[Start CLI] --> B[Scanner: iterate PDFs]
    B --> C{Count pages ≤ 100?}
    C -- Yes --> D[Runner: OCR once (hOCR path)]
    D --> E[Metadata Preserver: copy DocInfo/XMP/PageLabels/Flags/Outlines]
    E --> F[Write final <stem>_upocr.pdf]
    C -- No (>100) --> G[Paginator: split into ≤100 page chunks]
    G --> H[For each chunk in order: OCR chunk]
    H --> I[Merger: combine chunk outputs preserving order]
    I --> E
    F --> J[Summary & Exit]
```

### Key Design Choices

- Independence: keep `upocr` decoupled; do not import OCRmyPDF private modules.
- Predictable outputs: same-directory `_upocr.pdf` suffix; idempotent skips by default.
- Scaling: conservative default workers; rely on exec client throttling; optional `--max-workers`.
- Compliance: honor Upstage sync API 100-page constraint with chunking/merging.
- Metadata fidelity: preserve source DocInfo/XMP, page labels, tagged flag, and outlines; do not copy digital signatures.

### Public API (internal to this repo)

```python
# upocr.runner
def ocr_single(input_pdf: Path, *, force: bool = False) -> tuple[Path, str]:
    """Run OCR for one PDF (≤100 pages) and return (output_path, status). Status in {ok, skipped, failed}."""

def ocr_document(input_pdf: Path, *, force: bool = False) -> tuple[Path, str]:
    """Orchestrate full flow: paginate if needed (>100 pages), OCR chunks sequentially, merge, and return (final_output_path, status)."""

# upocr.scanner
def iter_targets(roots: list[Path], include: list[str], exclude: list[str], force: bool) -> iterator[Path]:
    """Yield input PDFs to process, honoring include/exclude and skip rules."""

# upocr.pager
def split_into_chunks(input_pdf: Path, max_pages: int = 100) -> list[Path]:
    """Split input into ≤100-page chunks. Returns list of temporary chunk PDFs."""

def merge_chunk_outputs(chunk_outputs: list[Path], final_output: Path) -> None:
    """Merge per-chunk outputs into a single final PDF, preserving page order."""

# upocr.meta
def read_source_metadata(input_pdf: Path) -> dict:
    """Extract source DocInfo, XMP, PageLabels, outlines, and relevant catalog flags for preservation."""

def apply_metadata(final_pdf: Path, metadata: dict, page_index_map: list[int]) -> None:
    """Apply preserved metadata to final PDF. Remap outlines/destinations to new page objects via page_index_map."""
```

### Configuration

- Environment: `UPSTAGE_API_KEY` required; `.env` loaded if present.
- CLI: `--roots`, `--include`, `--exclude`, `--max-workers`, `--force`, `--dry-run`, `--verbose`.
- Limits: `max_pages_per_chunk=100` (from Upstage sync API). Optional future flag to pin a different value if API changes.
- Metadata: outlines and doc info not exposed by `pdfinfo` API are read/applied with pikepdf; `pdfinfo.PdfInfo` can inform capabilities like tagged/AcroForm/signature flags.

### Logging and Telemetry

- Per-file: start, success (size), skip reason, failure (reason).
- Batch summary: totals, duration, throughput.
- Chunking: log split counts, per-chunk OCR status, and final merge outcome.
- Metadata: log preservation steps (DocInfo/XMP copied, outlines remapped count, page labels copied).

### Testing Strategy

- Unit tests for scanner filtering and output path resolution.
- Unit tests for chunk split size calculation and merge reassembly order.
- Smoke test that runs on a small sample tree (network-dependent; can be optional).
- Unit tests for metadata read/apply on small synthetic PDFs (DocInfo, XMP stub, page labels, simple outlines).
