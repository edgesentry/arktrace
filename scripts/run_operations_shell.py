from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import polars as pl


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "data" / "processed"

WATCHLIST_BY_REGION = {
    "singapore": DATA_DIR / "singapore_watchlist.parquet",
    "japan": DATA_DIR / "japansea_watchlist.parquet",
    "middleeast": DATA_DIR / "middleeast_watchlist.parquet",
    "europe": DATA_DIR / "europe_watchlist.parquet",
    "gulf": DATA_DIR / "gulf_watchlist.parquet",
}


def _prompt(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{prompt}{suffix}: ").strip()
    if not value and default is not None:
        return default
    return value


def _prompt_yes_no(prompt: str, default: bool = False) -> bool:
    label = "Y/n" if default else "y/N"
    raw = input(f"{prompt} ({label}): ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}


def _run_command(cmd: list[str]) -> int:
    print("\nRunning command:")
    print("  " + " ".join(cmd))
    print()
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _print_watchlist_summary(path: Path) -> None:
    if not path.exists():
        print(f"Result: watchlist not found at {path}")
        return

    df = pl.read_parquet(path)
    count = df.height
    print(f"Result: watchlist rows = {count}")
    if count > 0 and {"mmsi", "confidence"}.issubset(set(df.columns)):
        top = df.sort("confidence", descending=True).head(1)
        row = top.to_dicts()[0]
        print(
            "Top candidate: "
            f"mmsi={row.get('mmsi')} confidence={row.get('confidence')}"
        )
    print(f"Artifact: {path}")


def run_full_screening() -> None:
    print("\n[1] Full Screening")
    region = _prompt(
        "Region (singapore/japan/middleeast/europe/gulf)",
        default="singapore",
    ).lower()
    if region not in WATCHLIST_BY_REGION:
        print(f"Unsupported region: {region}")
        return

    stream_duration = _prompt("Stream duration seconds (0 to skip)", default="0")
    seed_dummy = _prompt_yes_no("Seed dummy vessels", default=False)

    cmd = [
        sys.executable,
        str((SCRIPTS_DIR / "run_pipeline.py").resolve()),
        "--region",
        region,
        "--non-interactive",
    ]
    if stream_duration.isdigit() and int(stream_duration) > 0:
        cmd.extend(["--stream-duration", stream_duration])
    if seed_dummy:
        cmd.append("--seed-dummy")

    rc = _run_command(cmd)
    if rc != 0:
        print(f"Result: FAILED (exit code {rc})")
        return

    print("Result: SUCCESS")
    _print_watchlist_summary(WATCHLIST_BY_REGION[region])


def run_review_feedback_evaluation() -> None:
    print("\n[2] Review-Feedback Evaluation")
    db = _prompt("DuckDB path", default="data/processed/mpol.duckdb")
    output = _prompt(
        "Output report path",
        default="data/processed/review_feedback_evaluation.json",
    )

    cmd = [
        sys.executable,
        str((SCRIPTS_DIR / "run_review_feedback_evaluation.py").resolve()),
        "--db",
        db,
        "--output",
        output,
    ]
    rc = _run_command(cmd)
    if rc != 0:
        print(f"Result: FAILED (exit code {rc})")
        return

    report_path = (PROJECT_ROOT / output).resolve()
    if not report_path.exists():
        print("Result: SUCCESS, but output report was not found")
        return

    report = _load_json(report_path)
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    reviewed = summary.get("reviewed_vessel_count", 0)
    regions = summary.get("regions_evaluated", 0)
    drift = summary.get("overall_drift_pass", True)

    print("Result: SUCCESS")
    print(
        "Summary: "
        f"reviewed_vessel_count={reviewed}, "
        f"regions_evaluated={regions}, "
        f"overall_drift_pass={drift}"
    )
    print(f"Artifact: {report_path}")


def run_historical_backtesting_public_batch() -> None:
    print("\n[3] Historical Backtesting + Public Integration Batch")
    regions = _prompt(
        "Regions (comma-separated)",
        default="singapore,japan,middleeast,europe,gulf",
    )
    strict_floor = _prompt_yes_no("Enable strict known-case floor", default=False)

    cmd = [
        sys.executable,
        str((SCRIPTS_DIR / "run_public_backtest_batch.py").resolve()),
        "--regions",
        regions,
    ]
    if strict_floor:
        cmd.append("--strict-known-cases")

    rc = _run_command(cmd)
    if rc != 0:
        print(f"Result: FAILED (exit code {rc})")
        return

    summary_path = (DATA_DIR / "backtest_public_integration_summary.json").resolve()
    report_path = (DATA_DIR / "backtest_report_public_integration.json").resolve()
    if not summary_path.exists():
        print("Result: SUCCESS, but summary report was not found")
        return

    summary = _load_json(summary_path)
    total_known = summary.get("total_known_cases", 0)
    region_list = summary.get("regions", [])

    print("Result: SUCCESS")
    print(
        "Summary: "
        f"regions={region_list}, "
        f"total_known_cases={total_known}"
    )
    print(f"Artifacts: {summary_path}, {report_path}")


def run_demo_smoke() -> None:
    print("\n[4] Demo/Smoke")
    backup = _prompt_yes_no("Backup existing candidate_watchlist.parquet", default=True)

    cmd = [
        sys.executable,
        str((SCRIPTS_DIR / "use_demo_watchlist.py").resolve()),
    ]
    if backup:
        cmd.append("--backup")

    rc = _run_command(cmd)
    if rc != 0:
        print(f"Result: FAILED (exit code {rc})")
        return

    target = (DATA_DIR / "candidate_watchlist.parquet").resolve()
    print("Result: SUCCESS")
    _print_watchlist_summary(target)


def main() -> None:
    actions = {
        "1": run_full_screening,
        "2": run_review_feedback_evaluation,
        "3": run_historical_backtesting_public_batch,
        "4": run_demo_smoke,
    }

    while True:
        print("\n=== arktrace Operations Shell ===")
        print("1) Full Screening")
        print("2) Review-Feedback Evaluation")
        print("3) Historical Backtesting + Public Integration Batch")
        print("4) Demo/Smoke")
        print("q) Quit")

        choice = input("Select job: ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            print("Bye")
            return

        action = actions.get(choice)
        if action is None:
            print("Invalid selection")
            continue

        try:
            action()
        except KeyboardInterrupt:
            print("\nCanceled by user")
        except Exception as exc:
            print(f"Unexpected error: {exc}")


if __name__ == "__main__":
    main()
