"""UpOCR CLI per PRD.

Usage example:
    uv run python -m upocr.cli \
      --roots ~/Docs ~/Downloads \
      --include "**/*.pdf" --exclude "**/*_upocr.pdf" \
      --max-workers 2 --force
"""

from __future__ import annotations

import concurrent.futures as futures
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

from dotenv import load_dotenv

from .runner import ocr_document
from .scanner import iter_targets


@dataclass
class Summary:
    total: int = 0
    ok: int = 0
    skipped: int = 0
    failed: int = 0
    duration_s: float = 0.0


def _rate_limited_submit(executor, fn, args, *, rps: float) -> futures.Future:
    # naive RPS limiter: sleep between submissions
    time.sleep(1.0 / max(0.01, rps))
    return executor.submit(fn, *args)


def _process_one(path: Path, force: bool) -> Tuple[Path, str]:
    return ocr_document(path, force=force)


def main(argv: List[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="UpOCR directory runner")
    parser.add_argument("--roots", nargs="+", type=Path, required=True)
    parser.add_argument("--include", nargs="*", default=["**/*.pdf"]) 
    parser.add_argument("--exclude", nargs="*", default=["**/*_upocr.pdf"]) 
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rps", type=float, default=1.0, help="Requests per second throttle")
    parser.add_argument(
        "--confirm-each",
        action="store_true",
        help="Ask y/n before processing each file (disables concurrency)",
    )
    args = parser.parse_args(argv)

    # Load .env early
    load_dotenv()
    if not os.environ.get("UPSTAGE_API_KEY"):
        print("UPSTAGE_API_KEY not set (set env or .env)", file=sys.stderr)
        return 2

    start = time.time()
    targets = list(iter_targets(args.roots, args.include, args.exclude, force=args.force))
    summary = Summary(total=len(targets))

    if args.dry_run:
        for t in targets:
            print(t)
        return 0

    if args.confirm_each:
        def prompt_yes_no(prompt: str) -> bool:
            if not sys.stdin.isatty():
                print("Non-interactive stdin; treating as 'n' for safety", file=sys.stderr)
                return False
            while True:
                resp = input(f"{prompt} [y/n]: ").strip().lower()
                if resp in ("y", "yes"):
                    return True
                if resp in ("n", "no"):
                    return False
                print("Please answer 'y' or 'n'.")

        for t in targets:
            if prompt_yes_no(f"OCR {t}"):
                time.sleep(1.0 / max(0.01, args.rps))
                out_path, status = _process_one(t, args.force)
                if status == "ok":
                    summary.ok += 1
                elif status == "skipped":
                    summary.skipped += 1
                else:
                    summary.failed += 1
                print(f"{status}: {out_path}")
            else:
                summary.skipped += 1
                print(f"skipped: {t} (user)")
    else:
        with futures.ThreadPoolExecutor(max_workers=args.max_workers) as ex:
            futs: List[futures.Future] = []
            for t in targets:
                futs.append(_rate_limited_submit(ex, _process_one, (t, args.force), rps=args.rps))
            for fut in futures.as_completed(futs):
                out_path, status = fut.result()
                if status == "ok":
                    summary.ok += 1
                elif status == "skipped":
                    summary.skipped += 1
                else:
                    summary.failed += 1
                print(f"{status}: {out_path}")

    summary.duration_s = time.time() - start
    print(
        f"Done total={summary.total} ok={summary.ok} skipped={summary.skipped} "
        f"failed={summary.failed} duration_s={summary.duration_s:.2f}"
    )
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


