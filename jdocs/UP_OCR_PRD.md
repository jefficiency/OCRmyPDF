## UpOCR – Product Requirements Document (PRD)

### 1. Goal and Outcome
Build a small, independent module that scans configured local directories for PDF files and converts each to an OCR’d PDF using the Upstage-powered OCRmyPDF pipeline. Outputs are written alongside inputs using the `_upocr.pdf` suffix, e.g. `foo/bar/egg.pdf` → `foo/bar/egg_upocr.pdf`.

### 2. Users and Use Cases
- Individual analysts who have folders of reports needing searchability.
- Back-office batch tasks where OCR is applied periodically to a content tree.
- Power users who want a CLI to enforce consistent naming and placement.

### 3. Scope
- In-scope:
  - Recursive directory scan for `*.pdf` (configurable include/exclude globs)
  - Idempotent conversion: skip when output exists and is newer than input (unless `--force`)
  - File-by-file invocation of OCRmyPDF API path with Upstage engine
  - `.env` loading for `UPSTAGE_API_KEY`
  - Basic logging and summary report
  - Dry-run mode
  - Concurrency control (bounded parallelism) with safe rate-limiting
  - Handling PDFs over 100 pages by splitting into ≤100-page chunks, processing each chunk via the synchronous Upstage API, and merging results back into a single output file (see `jdocs/upstage_reference.md` — sync limit: 100 pages)
- Out-of-scope (initial version):
  - Network retries/backoff policy customization (use reasonable defaults)
  - Async Upstage API path
  - Distributed execution or queue-based scheduling

### 4. Functional Requirements
- FR1: Accept one or more root directories; recursively find PDFs.
- FR2: For each PDF, compute destination path `<stem>_upocr.pdf` in the same directory.
- FR3: Invoke OCR with `pdf_renderer='hocr'`, `upstage_model='document-parse'`, `upstage_chart_recognition=True`, `upstage_merge_tables=True`.
- FR4: Respect `--force` to overwrite existing outputs; otherwise skip when output exists and is newer than input.
- FR5: Provide `--include`/`--exclude` glob patterns to filter candidates.
- FR6: Provide `--max-workers` to bound concurrency; throttle to ≤ 1 RPS per process.
- FR7: Produce a final summary: totals, successes, failures, skipped.
- FR8: For inputs with more than 100 pages, automatically split into chunks of ≤100 pages, run OCR on each chunk, and merge chunk outputs into a single `<stem>_upocr.pdf` while preserving page order (exact merge strategy and metadata preservation details TBD).

### 5. Non-Functional Requirements
- NFR1: Safe and predictable I/O; never move or delete user files.
- NFR2: Observable: structured log lines per file and per batch.
- NFR3: Reasonable performance on large trees (streamed walk, bounded concurrency).

### 6. CLI Sketch (to be refined)
```
uv run python -m upocr.cli \
  --roots ~/Docs ~/Downloads \
  --include "**/*.pdf" --exclude "**/*_upocr.pdf" \
  --max-workers 2 --force --dry-run
```

### 7. Dependencies and Integration
- Uses OCRmyPDF public API (`ocr()`), curated plugin manager, and the Upstage builtin plugin.
- Loads `.env` with `python-dotenv` to obtain `UPSTAGE_API_KEY`.
- Respects Upstage synchronous API constraints (100 pages per request). Large documents are chunked and merged; refer to `jdocs/upstage_reference.md`.

### 8. Risks and Mitigations
- Rate limits: bound concurrency; internal 1 RPS throttle per process.
- Large trees: streaming walk and skip logic reduce unnecessary work.
- Upstream changes: encapsulate OCR call behind `upocr.runner` so changes are localized.
- Chunking/merging for large PDFs: merging may affect outlines/metadata; initial version focuses on content correctness and page order, with enhanced metadata preservation deferred.

### 9. Deliverables
- `src/upocr/cli.py`, `src/upocr/scanner.py`, `src/upocr/runner.py`
- Documentation: this PRD and Architecture doc
- Example usage and small smoke test script


