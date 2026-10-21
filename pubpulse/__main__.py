"""Command line entry point: python -m pubpulse <command>."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def load_dotenv(path: Path = Path(__file__).resolve().parent.parent / ".env") -> None:
    """Minimal .env loader for local runs (KEY=VALUE lines; existing environment wins)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="pubpulse", description="Weekly publication tracker (OpenAlex → site, feed, digest).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sync", help="refresh people.yml from the staff page and fetch publications from OpenAlex")
    s.add_argument("--dry-run", action="store_true", help="write results to out/ instead of data/ and people.yml")
    s.add_argument("--skip-people", action="store_true", help="do not touch the staff page; use people.yml as is")

    sub.add_parser("build", help="build dist/ (website), data/feed.xml and out/ (digest email, Teams card)")

    a = sub.add_parser("all", help="sync then build")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--skip-people", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd in ("sync", "all"):
        from .sync import run as sync_run

        rec = sync_run(dry_run=args.dry_run, skip_people=args.skip_people)
        if args.cmd == "sync":
            return 0
        if args.dry_run:
            print("dry run: skipping build (data/ not updated)")
            return 0
    if args.cmd in ("build", "all"):
        from .build import run as build_run

        build_run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
