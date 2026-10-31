"""Command-line entry point.

python -m job_pipeline extract              # all sources, today (UTC)
python -m job_pipeline load                 # load today's landed data
python -m job_pipeline run                  # extract + load
python -m job_pipeline run --source himalayas --date 2026-10-31 --max-pages 2
"""

import argparse
import sys
from datetime import UTC, date, datetime

from job_pipeline.extract import run_extract
from job_pipeline.load import run_load
from job_pipeline.sources import SOURCES

DEFAULT_MAX_PAGES = {"arbeitnow": 3, "himalayas": 5}  # ~900 + ~500 jobs per run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="job_pipeline")
    parser.add_argument("step", choices=["extract", "load", "run"])
    parser.add_argument("--source", choices=[*SOURCES, "all"], default="all")
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=datetime.now(UTC).date(),
        help="ingest date (YYYY-MM-DD), default today UTC",
    )
    parser.add_argument("--max-pages", type=int, help="override page cap per source")
    args = parser.parse_args(argv)

    names = list(SOURCES) if args.source == "all" else [args.source]
    failed = False
    for name in names:
        source = SOURCES[name]()
        print(f"[{name}] {args.step} for {args.date}")
        try:
            if args.step in ("extract", "run"):
                pages = args.max_pages or DEFAULT_MAX_PAGES[name]
                m = run_extract(source, args.date, pages)
                print(f"  extracted {m['jobs']} jobs in {m['pages']} page(s)")
            if args.step in ("load", "run"):
                n = run_load(source, args.date)
                print(f"  loaded {n} rows into raw.job_postings")
        except Exception as exc:  # one failing source must not stop the others
            failed = True
            print(f"  FAILED: {type(exc).__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
