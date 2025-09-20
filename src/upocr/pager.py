"""PDF pagination utilities for UpOCR.

This module provides helpers to split PDFs into fixed-size page chunks and
merge them back in order. Merging defaults to writing an output with a
"_merged" suffix and does not delete chunk files. It also supports splitting
with constraints (max pages and max file size per chunk).

CLI usage example:
    uv run python -m upocr.pager --input img_stock_report.pdf --pages-per-chunk 2

This will produce files like split_12.pdf, split_34.pdf, ... in the same
directory as the input file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import pikepdf


@dataclass(frozen=True)
class SplitResult:
    input_pdf: Path
    output_chunks: List[Path]


@dataclass(frozen=True)
class ChunkIndex:
    level1: int  # 0-based, two digits
    level2: int  # 0-based for "unsplit" (00); 1.. for splits, two digits
    level3: int  # 0-based for "unsplit" (00); 1.. for deeper splits, two digits


def _format_chunk_suffix(idx: ChunkIndex) -> str:
    return f"_chunk{idx.level1:02d}{idx.level2:02d}{idx.level3:02d}"


def _format_chunk_name(stem: str, suffix: str) -> str:
    return f"{stem}{suffix}.pdf"


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
        # Use index-based suffixes level1, with level2/3 = 0 for fixed split
        chunk_idx = 0
        chunk_dir = input_pdf.parent / "chunks"
        try:
            chunk_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            chunk_dir = input_pdf.parent
        for start_page in range(1, total_pages + 1, pages_per_chunk):
            end_page = min(start_page + pages_per_chunk - 1, total_pages)
            idx = ChunkIndex(level1=chunk_idx, level2=0, level3=0)
            out_name = _format_chunk_name(input_pdf.stem, _format_chunk_suffix(idx))
            out_path = chunk_dir / out_name

            with pikepdf.Pdf.new() as out_pdf:
                page_numbers = range(start_page - 1, end_page)  # 0-based indexes
                for page_index in page_numbers:
                    out_pdf.pages.append(src.pages[page_index])
                out_pdf.save(str(out_path))

            output_chunks.append(out_path)
            chunk_idx += 1

    return SplitResult(input_pdf=input_pdf, output_chunks=output_chunks)


def _filesize_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def _write_range(src: pikepdf.Pdf, input_pdf: Path, start_page: int, end_page: int, idx: ChunkIndex) -> Path:
    out_name = _format_chunk_name(input_pdf.stem, _format_chunk_suffix(idx))
    chunk_dir = input_pdf.parent / "chunks"
    try:
        chunk_dir.mkdir(parents=True, exist_ok=True)
        out_path = chunk_dir / out_name
    except Exception:
        out_path = input_pdf.with_name(out_name)
    with pikepdf.Pdf.new() as out_pdf:
        page_numbers = range(start_page - 1, end_page)
        for page_index in page_numbers:
            out_pdf.pages.append(src.pages[page_index])
        out_pdf.save(str(out_path))
    return out_path


def split_by_constraints(
    input_pdf: Path,
    max_pages_per_chunk: int = 100,
    max_megabytes_per_chunk: float = 50.0,
) -> SplitResult:
    """Split input into chunks that respect page and size limits.

    Strategy:
    - Segment document into ranges of ≤ max_pages_per_chunk
    - For each range, write a chunk and measure size
      - If size > max_megabytes_per_chunk and pages > 1, split the range in half and retry
      - Stop when size ≤ limit or the range is a single page
    """
    input_pdf = Path(input_pdf)
    output_chunks: List[Path] = []

    with pikepdf.open(str(input_pdf)) as src:
        total_pages = len(src.pages)

        def process_range(start_page: int, end_page: int, idx: ChunkIndex) -> None:
            pages_in_range = end_page - start_page + 1
            if pages_in_range > max_pages_per_chunk:
                # split into consecutive windows of max_pages_per_chunk
                current = start_page
                l1 = idx.level1
                l2_counter = 1
                while current <= end_page:
                    sub_end = min(current + max_pages_per_chunk - 1, end_page)
                    process_range(current, sub_end, ChunkIndex(level1=l1, level2=l2_counter, level3=0))
                    current = sub_end + 1
                    l2_counter += 1
                return

            out_path = _write_range(src, input_pdf, start_page, end_page, idx)
            size_mb = _filesize_mb(out_path)
            if size_mb <= max_megabytes_per_chunk or pages_in_range == 1:
                output_chunks.append(out_path)
                return
            # too big and more than one page: split in half and retry
            out_path.unlink(missing_ok=True)
            mid = start_page + (pages_in_range // 2) - 1
            # Assign indices according to hierarchy:
            # - If we are at base (level2==0), assign level2=01,02 and keep level3=00
            # - Otherwise, we are within a level2 segment; assign level3=01,02 (and grow if split further)
            if idx.level2 == 0:
                left_idx = ChunkIndex(level1=idx.level1, level2=1, level3=0)
                right_idx = ChunkIndex(level1=idx.level1, level2=2, level3=0)
            else:
                # Grow level3 digits; keep monotonic growth within this branch
                base = idx.level3 if idx.level3 else 0
                left_idx = ChunkIndex(level1=idx.level1, level2=idx.level2, level3=base + 1)
                right_idx = ChunkIndex(level1=idx.level1, level2=idx.level2, level3=base + 2)
            process_range(start_page, mid, left_idx)
            process_range(mid + 1, end_page, right_idx)

        if total_pages == 0:
            return SplitResult(input_pdf=input_pdf, output_chunks=[])

        # Initial pass: level1 increments per 100-page window, level2/3 start at 0
        l1 = 0
        current = 1
        while current <= total_pages:
            end = min(current + max_pages_per_chunk - 1, total_pages)
            process_range(current, end, ChunkIndex(level1=l1, level2=0, level3=0))
            current = end + 1
            l1 += 1

    return SplitResult(input_pdf=input_pdf, output_chunks=output_chunks)


def _default_merged_output_path(chunk_paths: Iterable[Path], base_input: Optional[Path] = None) -> Path:
    # Determine default merged output path ending with _merged.pdf
    if base_input is not None:
        return base_input.with_name(f"{base_input.stem}_merged.pdf")
    # Fallback to the first chunk's stem if base input is not provided
    chunks_list = list(chunk_paths)
    if not chunks_list:
        raise ValueError("At least one chunk is required to determine output path")
    first = Path(chunks_list[0])
    return first.with_name(f"{first.stem}_merged.pdf")


def merge_chunks(chunk_paths: Iterable[Path], output_pdf: Optional[Path] = None) -> Path:
    """Merge chunk PDFs in the given order into a single output file.

    Args:
        chunk_paths: Paths to chunk PDFs in the desired order.
        output_pdf: Destination file path. If not provided, a default path with
            a "_merged" suffix will be chosen.

    Returns:
        Path to the merged output PDF.
    """
    chunks_list = list(chunk_paths)
    if output_pdf is None:
        output_pdf = _default_merged_output_path(chunks_list)
    else:
        output_pdf = Path(output_pdf)
    with pikepdf.Pdf.new() as merged:
        for chunk in chunks_list:
            with pikepdf.open(str(chunk)) as src:
                for page in src.pages:
                    merged.pages.append(page)
        merged.save(str(output_pdf))
    return output_pdf


def merge_from_split_result(result: SplitResult, output_pdf: Optional[Path] = None) -> Path:
    """Merge using a SplitResult, defaulting to <input_stem>_merged.pdf.

    Args:
        result: SplitResult returned by split_fixed_pages.
        output_pdf: Optional explicit output path.

    Returns:
        Path to merged output.
    """
    if output_pdf is None:
        output_pdf = result.input_pdf.with_name(f"{result.input_pdf.stem}_merged.pdf")
    return merge_chunks(result.output_chunks, output_pdf)


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
    merge_p.add_argument(
        "--output",
        required=False,
        type=Path,
        help="Output merged PDF path (defaults to *_merged.pdf)",
    )

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


