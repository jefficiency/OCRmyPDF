import shutil
from pathlib import Path

import pikepdf

from upocr.pager import merge_chunks, split_fixed_pages


def test_split_and_merge_three_page_chunks(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sample_pdf = repo_root / "img_stock_report.pdf"
    assert sample_pdf.exists(), "Expected sample input PDF to exist"

    # Work on a copy in tmp_path
    work_pdf = tmp_path / sample_pdf.name
    shutil.copy2(sample_pdf, work_pdf)

    # Read original page count
    with pikepdf.open(str(work_pdf)) as src:
        original_pages = len(src.pages)

    # Split into 3-page chunks
    result = split_fixed_pages(work_pdf, pages_per_chunk=3)
    chunk_paths = result.output_chunks

    # Basic sanity: at least one chunk produced and all files exist
    assert len(chunk_paths) >= 1
    for c in chunk_paths:
        assert c.exists(), f"Missing chunk file: {c}"

    # Merge chunks back
    merged_pdf = tmp_path / "merged_3pp.pdf"
    out_path = merge_chunks(chunk_paths, merged_pdf)
    assert out_path.exists()

    # Validate page count equality
    with pikepdf.open(str(out_path)) as merged:
        merged_pages = len(merged.pages)
    assert merged_pages == original_pages


