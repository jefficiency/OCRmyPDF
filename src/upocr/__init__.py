"""UpOCR: Upstage-powered PDF OCR batch runner (module scaffold).

This package is intentionally independent of OCRmyPDF internals. It will
orchestrate scanning local storage directories for PDF targets and invoke the
existing runner path to generate OCR'd PDFs with the `_upocr` suffix, placed
next to the original files.

Planned entry points (to be implemented):
- upocr.cli: CLI for directory scanning and execution policies
- upocr.scanner: Walk directories, filter PDF targets
- upocr.runner: Thin wrapper calling OCRmyPDF with the Upstage engine

See jdocs/UP_OCR_PRD.md and jdocs/UP_OCR_ARCHITECTURE.md for details.
"""

__all__ = []


