"""Scanner utilities to discover PDF targets per PRD.

Features:
- Recursive directory walk from roots
- Include/Exclude glob filtering
- Idempotent skip: skip when <stem>_upocr.pdf exists and is newer than input (unless force)
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, Iterator, List


def _matches_any(path: Path, patterns: Iterable[str]) -> bool:
    """Return True if any pattern matches the full path or the basename.

    This allows convenient filters like "defi_for_dummies.pdf" (basename) or
    "**/reports/*.pdf" (full path glob).
    """
    s_full = str(path)
    s_name = path.name
    for pat in patterns:
        if fnmatch(s_full, pat) or fnmatch(s_name, pat):
            return True
    return False


def _default_includes() -> List[str]:
    return ["**/*.pdf", "**/*.PDF"]


def _compute_output_path(input_pdf: Path) -> Path:
    return input_pdf.with_name(f"{input_pdf.stem}_upocr.pdf")


@dataclass(frozen=True)
class ScanConfig:
    roots: List[Path]
    include: List[str]
    exclude: List[str]
    force: bool = False


def iter_targets(roots: Iterable[Path], include: Iterable[str] | None = None, exclude: Iterable[str] | None = None, *, force: bool = False) -> Iterator[Path]:
    inc = list(include or _default_includes())
    exc = list(exclude or [])
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        if root.is_file():
            path = root
            if _matches_any(path, inc) and not (exc and _matches_any(path, exc)):
                out = _compute_output_path(path)
                if force or not (out.exists() and out.stat().st_mtime >= path.stat().st_mtime):
                    yield path
            continue
        # Use rglob for recursion; filter with glob patterns
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if not _matches_any(path, inc):
                continue
            if exc and _matches_any(path, exc):
                continue
            # Idempotent skip check
            out = _compute_output_path(path)
            if not force and out.exists() and out.stat().st_mtime >= path.stat().st_mtime:
                continue
            yield path


