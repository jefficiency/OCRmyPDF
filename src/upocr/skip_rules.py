"""Composable skip rules for selecting PDF targets.

Each rule implements `should_skip(Path) -> bool`.
`SkipDecider` evaluates rules in order and short-circuits on first skip.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List, Protocol

import pikepdf


class SkipRule(Protocol):
    def should_skip(self, path: Path) -> bool:  # pragma: no cover - protocol
        ...


def _matches_any(path: Path, patterns: Iterable[str]) -> bool:
    s_full = str(path)
    s_name = path.name
    for pat in patterns:
        if fnmatch(s_full, pat) or fnmatch(s_name, pat):
            return True
    return False


@dataclass
class IncludeGlobRule:
    patterns: List[str]

    def should_skip(self, path: Path) -> bool:
        # Skip if it does not match include patterns
        return not _matches_any(path, self.patterns)


@dataclass
class ExcludeGlobRule:
    patterns: List[str]

    def should_skip(self, path: Path) -> bool:
        return _matches_any(path, self.patterns)


@dataclass
class OutputIsNewerRule:
    force: bool = False

    def _compute_output_path(self, input_pdf: Path) -> Path:
        return input_pdf.with_name(f"{input_pdf.stem}_upocr.pdf")

    def should_skip(self, path: Path) -> bool:
        if self.force:
            return False
        out = self._compute_output_path(path)
        try:
            return out.exists() and out.stat().st_mtime >= path.stat().st_mtime
        except FileNotFoundError:
            return False


@dataclass
class TocSkipRule:
    enabled: bool = False

    def should_skip(self, path: Path) -> bool:
        if not self.enabled:
            return False
        try:
            with pikepdf.Pdf.open(str(path)) as pdf:
                catalog = pdf.trailer.get("/Root", None)
                if catalog is None:
                    return False
                outlines = catalog.get("/Outlines", None)
                if outlines is None:
                    return False
                if outlines.get("/First", None) is not None:
                    return True
                try:
                    return abs(int(outlines.get("/Count", 0))) > 0
                except Exception:
                    return False
        except Exception:
            return False


@dataclass
class SkipDecider:
    rules: List[SkipRule]

    def should_skip(self, path: Path) -> bool:
        for rule in self.rules:
            if rule.should_skip(path):
                return True
        return False


@dataclass
class UpocrMergedExistsRule:
    """Skip if a final merged OCR output exists next to the input.

    Looks for <stem>_upocr_merged.pdf in the same directory as the candidate
    PDF. If present, we consider the file already OCR'd and skip it.
    """
    enabled: bool = False

    def should_skip(self, path: Path) -> bool:
        if not self.enabled:
            return False
        try:
            stem = path.stem
            parent = path.parent

            candidates = [
                parent / f"{stem}_upocr_merged.pdf",
                parent / f"{stem}_upocr_merged.PDF",
            ]

            # If input resides under pdf_<stem>/, also look one level up
            # for both legacy location and the restructure location:
            #   <base>/<stem>_upocr_merged.pdf
            #   <base>/pdf_<stem>_upocr_merged/<stem>_upocr_merged.pdf
            if parent.name == f"pdf_{stem}":
                base = parent.parent
                candidates.extend(
                    [
                        base / f"{stem}_upocr_merged.pdf",
                        base / f"{stem}_upocr_merged.PDF",
                        base / f"pdf_{stem}_upocr_merged" / f"{stem}_upocr_merged.pdf",
                        base / f"pdf_{stem}_upocr_merged" / f"{stem}_upocr_merged.PDF",
                    ]
                )

            for c in candidates:
                try:
                    if c.exists():
                        return True
                except Exception:
                    # Ignore filesystem errors for individual candidates
                    continue
            return False
        except Exception:
            return False


