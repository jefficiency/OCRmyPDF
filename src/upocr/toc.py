"""List PDF bookmarks (table of contents) using pikepdf.

Usage:
    uv run python -m upocr.toc FILE [FILE ...]

Prints whether each file has bookmarks and, if so, lists them hierarchically.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator, Tuple

from pikepdf import Pdf


def _has_bookmarks(pdf: Pdf) -> bool:
    catalog = pdf.trailer.get("/Root", None)
    if catalog is None:
        return False
    outlines = catalog.get("/Outlines", None)
    if outlines is None:
        return False
    # If /First exists there's at least one top-level item
    if outlines.get("/First", None) is not None:
        return True
    # Otherwise rely on /Count if present (absolute value > 0 indicates descendants)
    try:
        return abs(int(outlines.get("/Count", 0))) > 0
    except Exception:
        return False


def _iter_outline_titles(pdf: Pdf) -> Iterator[Tuple[int, str]]:
    """Yield (depth, title) for all bookmarks.

    Traverses the linked-list style outline tree via /First, /Next, /Last.
    """
    catalog = pdf.trailer.get("/Root", None)
    if catalog is None:
        return
    outlines = catalog.get("/Outlines", None)
    if outlines is None:
        return

    def walk(node, depth: int) -> Iterator[Tuple[int, str]]:
        item = node.get("/First", None)
        while item is not None:
            title = item.get("/Title", "")
            # pikepdf decodes strings to Python str already
            yield depth, str(title)
            child = item.get("/First", None)
            if child is not None:
                yield from walk(item, depth + 1)
            item = item.get("/Next", None)

    yield from walk(outlines, 0)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Print PDF bookmarks (table of contents)")
    parser.add_argument("files", nargs="+", type=Path, help="PDF files to inspect")
    args = parser.parse_args(argv)

    exit_code = 0
    for path in args.files:
        try:
            with Pdf.open(str(path)) as pdf:
                if not _has_bookmarks(pdf):
                    print(f"{path}: no bookmarks")
                    continue
                print(f"{path}: bookmarks")
                for depth, title in _iter_outline_titles(pdf):
                    indent = "  " * depth
                    print(f"{indent}- {title}")
        except Exception as e:  # noqa: BLE001
            print(f"{path}: error reading bookmarks: {e}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


