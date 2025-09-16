import shutil
from pathlib import Path

import pytest
import pikepdf

from upocr.pager import merge_chunks, split_fixed_pages


@pytest.fixture
def work_pdf(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    sample_pdf = repo_root / "img_stock_report.pdf"
    assert sample_pdf.exists(), "Expected sample input PDF to exist"
    dest = tmp_path / sample_pdf.name
    shutil.copy2(sample_pdf, dest)
    return dest


@pytest.fixture
def original_pages(work_pdf: Path) -> int:
    with pikepdf.open(str(work_pdf)) as src:
        return len(src.pages)


@pytest.fixture
def chunks(work_pdf: Path) -> list[Path]:
    result = split_fixed_pages(work_pdf, pages_per_chunk=3)
    return result.output_chunks


@pytest.fixture
def merged_pdf(tmp_path: Path, chunks: list[Path]) -> Path:
    out = tmp_path / "merged_3pp.pdf"
    merge_chunks(chunks, out)
    return out


def test_split_produces_chunks(chunks: list[Path]) -> None:
    assert len(chunks) >= 1


def test_all_chunk_files_exist(chunks: list[Path]) -> None:
    for c in chunks:
        assert c.exists(), f"Missing chunk file: {c}"


def test_merge_creates_output(merged_pdf: Path) -> None:
    assert merged_pdf.exists()


def test_merged_page_count_matches(work_pdf: Path, original_pages: int, merged_pdf: Path) -> None:
    with pikepdf.open(str(merged_pdf)) as merged:
        merged_pages = len(merged.pages)
    assert merged_pages == original_pages


