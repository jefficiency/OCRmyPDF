"""Scanner utilities to discover PDF targets per PRD.

Features:
- Recursive directory walk from roots
- Include/Exclude glob filtering
- Idempotent skip: skip when <stem>_upocr.pdf exists and is newer than input (unless force)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List

from .skip_rules import (
    ExcludeGlobRule,
    IncludeGlobRule,
    OutputIsNewerRule,
    SkipDecider,
    TocSkipRule,
)


def _default_includes() -> List[str]:
    return ["**/*.pdf", "**/*.PDF"]


def iter_targets(roots: Iterable[Path], include: Iterable[str] | None = None, exclude: Iterable[str] | None = None, *, force: bool = False, exclude_toc_files: bool = False) -> Iterator[Path]:
    inc = list(include or _default_includes())
    exc = list(exclude or [])
    decider = SkipDecider(
        rules=[
            IncludeGlobRule(inc),
            ExcludeGlobRule(exc),
            TocSkipRule(enabled=exclude_toc_files),
            OutputIsNewerRule(force=force),
        ]
    )
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        if root.is_file():
            path = root
            if not decider.should_skip(path):
                yield path
            continue
        # Use rglob for recursion; filter with glob patterns
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if not decider.should_skip(path):
                yield path


