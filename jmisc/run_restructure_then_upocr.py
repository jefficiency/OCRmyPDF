"""Run PDF restructuring then UpOCR in sequence.

This script first moves PDFs under each root into per-file directories named
"pdf_<stem>", then runs the UpOCR CLI on the same roots.

Examples:
    uv run python jmisc/run_restructure_then_upocr.py --roots data/
    uv run python jmisc/run_restructure_then_upocr.py --roots data/ \
        --restructure-dry-run --upocr-dry-run

Notes:
    - Requires UPSTAGE_API_KEY in environment for the OCR step.
    - This is a convenience wrapper around `jmisc/restructure_pdfs.py` and
      `upocr.cli`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List
import importlib.util


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_restructure_module():
    mod_path = Path(__file__).resolve().parent / "restructure_pdfs.py"
    spec = importlib.util.spec_from_file_location("restructure_pdfs", str(mod_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load restructure_pdfs module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


def _import_upocr_cli():
    sys.path.insert(0, str(_project_root() / "src"))
    import upocr.cli as upocr_cli  # type: ignore

    return upocr_cli


def _run_restructure(roots: List[Path], *, dry_run: bool, force: bool, verbose: bool) -> int:
    m = _load_restructure_module()
    argv: List[str] = ["--roots", *[str(r) for r in roots]]
    if dry_run:
        argv.append("--dry-run")
    if force:
        argv.append("--force")
    if verbose:
        argv.append("--verbose")
    return int(m.main(argv))


def _run_upocr(
    roots: List[Path],
    *,
    dry_run: bool,
    force: bool,
    force_ocr: bool,
    max_workers: int,
    rps: float,
    include_toc_files: bool,
    include_already_ocred: bool,
) -> int:
    upocr_cli = _import_upocr_cli()
    argv: List[str] = ["--roots", *[str(r) for r in roots]]
    if dry_run:
        argv.append("--dry-run")
    if force:
        argv.append("--force")
    if force_ocr:
        argv.append("--force-ocr")
    if max_workers != 1:
        argv.extend(["--max-workers", str(max_workers)])
    if rps != 1.0:
        argv.extend(["--rps", str(rps)])
    if include_toc_files:
        argv.append("--include-toc-files")
    if include_already_ocred:
        argv.append("--include-already-ocred")
    return int(upocr_cli.main(argv))


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restructure PDFs then run UpOCR")
    parser.add_argument("--roots", nargs="+", type=Path, required=True)

    parser.add_argument("--restructure-dry-run", action="store_true")
    parser.add_argument("--restructure-force", action="store_true")
    parser.add_argument("--restructure-verbose", action="store_true")

    parser.add_argument("--upocr-dry-run", action="store_true")
    parser.add_argument("--upocr-force", action="store_true")
    parser.add_argument("--upocr-force-ocr", action="store_true")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--rps", type=float, default=1.0)
    parser.add_argument("--include-toc-files", action="store_true")
    parser.add_argument("--include-already-ocred", action="store_true")

    args = parser.parse_args(argv)

    rc1 = _run_restructure(
        args.roots,
        dry_run=args.restructure_dry_run,
        force=args.restructure_force,
        verbose=args.restructure_verbose,
    )
    if rc1 != 0:
        return int(rc1)

    rc2 = _run_upocr(
        args.roots,
        dry_run=args.upocr_dry_run,
        force=args.upocr_force,
        force_ocr=args.upocr_force_ocr,
        max_workers=args.max_workers,
        rps=args.rps,
        include_toc_files=args.include_toc_files,
        include_already_ocred=args.include_already_ocred,
    )
    return int(rc2)


if __name__ == "__main__":
    raise SystemExit(main())


