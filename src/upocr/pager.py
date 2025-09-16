"""PDF pagination utilities for UpOCR.

This module provides helpers to split PDFs into fixed-size page chunks and
merge them back in order.

CLI usage example:
    uv run python -m upocr.pager --input img_stock_report.pdf --pages-per-chunk 2

This will produce files like split_12.pdf, split_34.pdf, ... in the same
directory as the input file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import pikepdf


@dataclass(frozen=True)
class SplitResult:
    input_pdf: Path
    output_chunks: List[Path]


def _format_chunk_name(stem: str, start_page_index: int, end_page_index: int) -> str:
    # human-readable 1-based page numbering concatenated, e.g., 1 and 2 -> split_12.pdf
    if start_page_index == end_page_index:
        return f"split_{start_page_index}.pdf"
    return f"split_{start_page_index}{end_page_index}.pdf"


def split_fixed_pages(input_pdf: Path, pages_per_chunk: int = 2) -> SplitResult:
    """Split the input PDF into fixed-size chunks.

    Args:
        input_pdf: Path to the source PDF.
        pages_per_chunk: Number of pages per chunk (default 2).

    Returns:
        SplitResult containing list of written chunk paths.
    """
    input_pdf = Path(input_pdf)
    if pages_per_chunk <= 0:
        raise ValueError("pages_per_chunk must be >= 1")

    output_chunks: List[Path] = []
    with pikepdf.open(str(input_pdf)) as src:
        total_pages = len(src.pages)
        # Use 1-based page numbers for naming
        for start_page in range(1, total_pages + 1, pages_per_chunk):
            end_page = min(start_page + pages_per_chunk - 1, total_pages)
            out_name = _format_chunk_name(input_pdf.stem, start_page, end_page)
            out_path = input_pdf.with_name(out_name)

            with pikepdf.Pdf.new() as out_pdf:
                page_numbers = range(start_page - 1, end_page)  # 0-based indexes
                for page_index in page_numbers:
                    out_pdf.pages.append(src.pages[page_index])
                out_pdf.save(str(out_path))

            output_chunks.append(out_path)

    return SplitResult(input_pdf=input_pdf, output_chunks=output_chunks)


def merge_chunks(chunk_paths: Iterable[Path], output_pdf: Path) -> Path:
    """Merge chunk PDFs in the given order into a single output file.

    Args:
        chunk_paths: Paths to chunk PDFs in the desired order.
        output_pdf: Destination file path.

    Returns:
        Path to the merged output PDF.
    """
    output_pdf = Path(output_pdf)
    with pikepdf.Pdf.new() as merged:
        for chunk in chunk_paths:
            with pikepdf.open(str(chunk)) as src:
                for page in src.pages:
                    merged.pages.append(page)
        merged.save(str(output_pdf))
    return output_pdf


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Split and merge PDF page chunks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    split_p = subparsers.add_parser("split", help="Split a PDF into fixed-size chunks")
    split_p.add_argument("--input", required=True, type=Path, help="Path to input PDF")
    split_p.add_argument(
        "--pages-per-chunk",
        type=int,
        default=2,
        help="Number of pages per output chunk (default: 2)",
    )

    merge_p = subparsers.add_parser("merge", help="Merge chunk PDFs into one PDF")
    merge_p.add_argument(
        "--chunks",
        nargs="+",
        required=True,
        type=Path,
        help="Chunk PDF paths in merge order",
    )
    merge_p.add_argument("--output", required=True, type=Path, help="Output merged PDF path")

    args = parser.parse_args()

    if args.command == "split":
        result = split_fixed_pages(args.input, args.pages_per_chunk)
        for path in result.output_chunks:
            print(path)
    elif args.command == "merge":
        out = merge_chunks(args.chunks, args.output)
        print(out)


if __name__ == "__main__":
    _main()


