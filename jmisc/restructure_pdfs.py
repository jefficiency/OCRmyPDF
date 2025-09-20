"""Restructure PDFs into per-file directories.

Given one or more roots, recursively find *.pdf files and move each file
into a sibling directory named after the file's stem.

Example:
    foo/bar/textbook1.pdf  ->  foo/bar/pdf_textbook1/textbook1.pdf

Usage:
    uv run python jmisc/restructure_pdfs.py --roots data/
    uv run python jmisc/restructure_pdfs.py --roots data/ ~/Downloads --dry-run

Notes:
    - Skips files already placed in a matching directory (i.e., parent name matches
      either the file's stem or "pdf_" + stem)
    - Skips if destination file already exists (unless --force)
    - Uses shutil.move (works across filesystems)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import shutil


def find_pdfs(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() == ".pdf" else []
    # Include lowercase and uppercase extensions commonly encountered
    results = list(root.rglob("*.pdf"))
    results += list(root.rglob("*.PDF"))
    return results


def plan_move(pdf_path: Path) -> tuple[Path, Path] | None:
    stem = pdf_path.stem
    parent = pdf_path.parent
    target_dir_name = f"pdf_{stem}"
    # If already in either the stem directory or the prefixed stem directory, skip
    if parent.name == stem or parent.name == target_dir_name:
        return None
    target_dir = parent / target_dir_name
    target_path = target_dir / pdf_path.name
    return target_dir, target_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Move PDFs into per-file directories")
    parser.add_argument("--roots", nargs="+", type=Path, required=True, help="Root directories or PDF files")
    parser.add_argument("--dry-run", action="store_true", help="Show planned moves without changing files")
    parser.add_argument("--force", action="store_true", help="Overwrite if destination file exists")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args(argv)

    moves: list[tuple[Path, Path, Path]] = []  # (src, target_dir, target_path)

    for root in args.roots:
        root = Path(root)
        if not root.exists():
            print(f"skip missing root: {root}", file=sys.stderr)
            continue
        for pdf in find_pdfs(root):
            plan = plan_move(pdf)
            if not plan:
                if args.verbose:
                    print(f"ok (already placed): {pdf}")
                continue
            target_dir, target_path = plan
            if target_path.exists() and not args.force:
                print(f"skip (exists): {target_path}")
                continue
            moves.append((pdf, target_dir, target_path))

    if args.dry_run:
        for src, target_dir, target_path in moves:
            print(f"mv '{src}' '{target_path}'  # mkdir -p '{target_dir}'")
        print(f"Planned moves: {len(moves)}")
        return 0

    moved = 0
    for src, target_dir, target_path in moves:
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            if target_path.exists() and args.force:
                target_path.unlink()
            shutil.move(str(src), str(target_path))
            print(f"moved: {src} -> {target_path}")
            moved += 1
        except Exception as e:  # noqa: BLE001
            print(f"error moving {src} -> {target_path}: {e}", file=sys.stderr)

    print(f"Done. Moved {moved} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


