## Upstage OCR Runner and Pipeline (Current Status)

This document describes the current, working integration that converts a PDF to an OCR’d PDF using the Upstage Document Parsing API through OCRmyPDF. It reflects the behavior of `run_upstage_api.py` and the built-in Upstage plugin.

- Runner: `run_upstage_api.py`
- Plugin: `src/ocrmypdf/builtin_plugins/upstage_ocr.py`
- Exec client and hOCR/PDF generation: `src/ocrmypdf/_exec/upstage.py`
- Reference: `jdocs/upstage_reference.md`

### Quick start

```bash
uv run python run_upstage_api.py \
  --input img_stock_report.pdf \
  --output output_upstage.pdf
```

Requirements:
- Set `UPSTAGE_API_KEY` in your environment or create a `.env` at the repo root. The runner and plugin will load it via `python-dotenv` if available.
- Internet connectivity to call the Upstage API.

### What the runner does

`run_upstage_api.py` uses OCRmyPDF’s public API and a curated plugin manager that loads all built-ins (`builtins=True`). With pluggy’s “last-registered-first” behavior, the Upstage engine is selected for the `firstresult` hook while keeping Tesseract CLI options available.

Key behaviors:
- Loads `.env` explicitly; fails fast if `UPSTAGE_API_KEY` is missing.
- Forces `pdf_renderer='hocr'` (invisible text layer via hOCR path).
- Passes Upstage options to OCRmyPDF: `upstage_model` (default: `document-parse`), `upstage_chart_recognition`, `upstage_merge_tables`.
- Enables `force_ocr` and `skip_text=False` when requested.

Minimal example invocation inside the runner:

```python
exit_code = ocr(
    input_file=input_pdf,
    output_file=output_pdf,
    pdf_renderer='hocr',
    upstage_api_key=os.environ['UPSTAGE_API_KEY'],
    upstage_endpoint='https://api.upstage.ai/v1/document-digitization',
    upstage_model='document-parse',
    upstage_chart_recognition=True,
    upstage_merge_tables=True,
    force_ocr=args.force_ocr,
    skip_text=False,
    plugin_manager=pm,
)
```

### How the conversion works (pipeline)

1) Plugin loading and option resolution (built-in plugin)
- File: `src/ocrmypdf/builtin_plugins/upstage_ocr.py`
- Hooks implemented: `add_options`, `check_options`, `validate`, `filter_ocr_image`, `get_ocr_engine`.
- `check_options()` resolves API key from CLI or `UPSTAGE_API_KEY`, validates endpoint/timeout/model, and supports `--upstage-chart-recognition` and `--upstage-merge-tables` (both default to true).
- `filter_ocr_image()` enforces Upstage input constraints (downscale above 200M pixels; upscale to minimum 640 px width when needed).

2) API request (exec client)
- File: `src/ocrmypdf/_exec/upstage.py`
- `UpstageAPIClient.ocr_image()` sends a multipart POST to the Upstage endpoint with:
  - `model='document-parse'` (runner default; you can pin a version alias)
  - `coordinates=True` (required for positioning the text layer)
  - `ocr='auto'`
  - `chart_recognition` and `merge_multipage_tables` from options
  - `output_formats="['markdown']"` (clean text for sidecar output)
  - No `base64_encoding` requested (we do not need element crops)

3) hOCR generation (exec client)
- File: `src/ocrmypdf/_exec/upstage.py`
- `generate_hocr()` calls `generate_hocr_from_upstage()` on the Upstage response.
- The Document Parse response’s `elements` array is used. For each element:
  - Text is taken from `content.markdown`.
  - Coordinates are relative (
    0.0–1.0); we convert them to an internal hOCR pixel space using a nominal page size (e.g., 1000×1000). OCRmyPDF later scales this to real PDF dimensions during grafting.
  - Category → hOCR class mapping uses an evidence-based map aligned with Tesseract’s hOCR:

| Upstage category | hOCR class |
|---|---|
| `header` | `ocr_header` |
| `caption` | `ocr_caption` |
| `figure`, `chart` | `ocr_textfloat` |
| `paragraph`, `heading1/2/3`, `list`, `equation`, `table`, `footer` | `ocr_par` |

- hOCR structure emitted: `ocr_page` → `ocr_carea` → `ocr_par` → `ocr_line` → `ocrx_word` with `bbox` and `x_wconf`.
- A plain-text sidecar is built by joining extracted element texts.

4) Grafting text into the PDF (OCRmyPDF core)
- With `pdf_renderer='hocr'`, OCRmyPDF consumes the hOCR and grafts an invisible text layer onto the original PDF page.
- The internal hOCR pixel space is scaled to the actual PDF page mediabox. Final text selection/search matches the visual layout.

5) Alternative: direct text-only PDF path (not used by runner)
- `generate_pdf_from_upstage()` supports creating a minimal text-only PDF when `pages[].words` are available (from the OCR model). The runner uses the hOCR path instead.

### Configuration and usage

- Environment:
  - `UPSTAGE_API_KEY` (required)
  - Optional overrides: `UPSTAGE_ENDPOINT`, `UPSTAGE_TIMEOUT`
- Runner flags:
  - `--model` (default `document-parse`), `--no-chart-recognition`, `--no-merge-tables`, `--force-ocr`, `--verbose`
- Plugin options (available when using OCRmyPDF CLI directly):
  - `--upstage-api-key`, `--upstage-endpoint`, `--upstage-timeout`, `--upstage-confidence-threshold`, `--upstage-model`, `--[no-]upstage-chart-recognition`, `--[no-]upstage-merge-tables`

### Notes and limitations

- Network access is required; API failures fall back to emitting an empty hOCR file (graceful degrade).
- Synchronous API limits: up to 100 pages per file; page pixels ≤ 200,000,000; file size ≤ 50 MB. See `jdocs/upstage_reference.md`.
- The runner relies on builtin plugin registration order (last-registered-first for `firstresult`). If upstream changes this policy, selection logic may need adjustment.
- We intentionally avoid `base64_encoding` crops in requests; chart recognition and multipage table merging are supported and enabled by default.

### References

- Runner: `run_upstage_api.py`
- Plugin: `src/ocrmypdf/builtin_plugins/upstage_ocr.py`
- Exec client and hOCR/PDF generation: `src/ocrmypdf/_exec/upstage.py`
- API details: `jdocs/upstage_reference.md`


