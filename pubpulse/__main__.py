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

    sub.add_parser("send-digest", help="email out/digest.* to the subscriber list (and DIGEST_TO) via Gmail SMTP")

    sc = sub.add_parser("scholar-check", help="compare Google Scholar profiles (via SerpAPI) with pubpulse; writes data/scholar_check.json")
    sc.add_argument("--max-searches", type=int, default=None)
    sc.add_argument("--only", help="slug of one person")
    sub.add_parser("mark-notified", help="clear the list of unannounced works (data/pending.json) after a successful notification")

    i = sub.add_parser("apply-issue", help="apply an 'identifiers' issue form body to people.yml")
    i.add_argument("--body-file", required=True)
    i.add_argument("--result-file", default="out/issue_result.md")

    a = sub.add_parser("all", help="sync then build")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--skip-people", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "mark-notified":
        from .sync import save_pending

        save_pending([])
        print("pending list cleared")
        return 0
    if args.cmd == "scholar-check":
        from .scholar import run as scholar_run

        return scholar_run(max_searches=args.max_searches, only=args.only)
    if args.cmd == "send-digest":
        from .mailer import run as mail_run

        return mail_run()
    if args.cmd == "apply-issue":
        from .issues import apply_identifiers, parse_issue_body
        from .sync import load_people, save_people

        people = load_people()
        changed, message = apply_identifiers(people, parse_issue_body(Path(args.body_file).read_text(encoding="utf-8")))
        if changed:
            save_people(people)
        Path(args.result_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.result_file).write_text(message, encoding="utf-8")
        print(message)
        return 0 if changed else 3
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
