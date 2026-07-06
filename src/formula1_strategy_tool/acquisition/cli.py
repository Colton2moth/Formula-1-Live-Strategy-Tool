"""
Command-line entry point for the historical OpenF1 bulk downloader.

Run tomorrow morning before work:

    source .venv/bin/activate
    f1-download-openf1

Or in the background so it survives terminal close:

    nohup f1-download-openf1 > download.log 2>&1 &

Defaults: years 2023 through current year, Race sessions only, output data/raw/.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from formula1_strategy_tool.acquisition.client import OpenF1Client
from formula1_strategy_tool.acquisition.downloader import download_year


def build_parser() -> argparse.ArgumentParser:
    """Define CLI flags for the bulk historical download."""
    current_year = datetime.now(timezone.utc).year

    parser = argparse.ArgumentParser(
        description=(
            "Download historical OpenF1 race data for strategy-model training. "
            "Safe to re-run — skips files already on disk."
        ),
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2023,
        help="First season to download (OpenF1 history begins in 2023).",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=current_year,
        help="Last season to download (default: current year).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw"),
        help="Root directory for raw JSON files.",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(list(argv) if argv is not None else None)


def main(argv: Sequence[str] | None = None) -> None:
    """
    Parse arguments and download all requested years sequentially.

    Years are processed one at a time so progress is easy to follow in the log.
    """
    args = parse_args(argv)

    if args.start_year < 2023:
        raise ValueError("OpenF1 historical data begins in 2023.")

    if args.end_year < args.start_year:
        raise ValueError("--end-year must be >= --start-year.")

    # One client for the whole run — reuses connections and rate-limit state.
    client = OpenF1Client()

    for year in range(args.start_year, args.end_year + 1):
        download_year(
            client=client,
            output_root=args.output,
            year=year,
        )

    print("\nDownload finished.", flush=True)
    print(f"Data saved under: {args.output.resolve()}", flush=True)
    print("Check download_errors.jsonl for any failed endpoints.", flush=True)


if __name__ == "__main__":
    main()
