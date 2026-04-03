from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy bundled demo watchlist parquet into processed output path"
    )
    parser.add_argument(
        "--source",
        default="data/demo/candidate_watchlist_demo.parquet",
        help="Bundled demo watchlist parquet path",
    )
    parser.add_argument(
        "--target",
        default="data/processed/candidate_watchlist.parquet",
        help="Dashboard watchlist parquet path",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Backup target file to <target>.bak before overwrite",
    )
    args = parser.parse_args()

    source = Path(args.source)
    target = Path(args.target)

    if not source.exists():
        raise SystemExit(f"Source demo watchlist not found: {source}")

    target.parent.mkdir(parents=True, exist_ok=True)
    if args.backup and target.exists():
        backup = target.with_suffix(target.suffix + ".bak")
        shutil.copy2(target, backup)
        print(f"Backed up: {backup}")

    shutil.copy2(source, target)
    print(f"Copied demo watchlist: {source} -> {target}")


if __name__ == "__main__":
    main()
