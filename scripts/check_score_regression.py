"""Score regression gate for CI.

Reads the JSON artefacts produced by run_public_backtest_batch.py and exits
non-zero if any metric violates its floor or ceiling.

Both floor AND ceiling checks matter:
  - Floor breach  → scoring is broken (e.g. AUROC < 0.65 means worse than random)
  - Ceiling breach → data leakage or label inflation (e.g. P@50 = 1.0 on real data
    is implausibly perfect and signals a seeding bug like #229)

Exit codes
----------
  0  all checks passed
  1  one or more metric violations
  2  required input files are missing (pipeline did not run)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Thresholds (mirrors the table in issue #237)
# ---------------------------------------------------------------------------
THRESHOLDS: list[dict] = [
    {
        "metric": "precision_at_50",
        "floor": 0.25,
        "ceiling": 0.95,
        "rationale": "< 0.25 → scoring broken; > 0.95 → label inflation",
    },
    {
        "metric": "auroc",
        "floor": 0.65,
        "ceiling": 0.99,
        "rationale": "< 0.65 → worse than random; > 0.99 → data leakage",
    },
    {
        "metric": "recall_at_200",
        "floor": 0.50,
        "ceiling": None,
        "rationale": "all positives must be reachable in top 200",
    },
    {
        "metric": "total_known_cases",
        "floor": 5,
        "ceiling": 500,
        "rationale": "< 5 → eval DB empty; > 500 → label inflation",
    },
]


def _load_json(path: Path) -> dict:
    if not path.exists():
        print(f"[error] required file not found: {path}", flush=True)
        sys.exit(2)
    with path.open() as f:
        return json.load(f)


def _collect_metrics(summary: dict, report: dict) -> dict[str, float | int]:
    """Flatten the key metrics from both JSON files into a single dict."""
    ms = summary.get("metrics_summary", {})

    def _mean(key: str) -> float | None:
        block = ms.get(key, {})
        return block.get("mean") if isinstance(block, dict) else None

    # false_negatives: any confirmed OFAC vessel scoring near-zero across all windows
    false_negatives: list = []
    for window in report.get("windows", []):
        false_negatives.extend(window.get("error_analysis", {}).get("false_negatives", []))

    return {
        "precision_at_50": _mean("precision_at_50"),
        "auroc": _mean_auroc(report),
        "recall_at_200": _mean("recall_at_200"),
        "total_known_cases": summary.get("total_known_cases"),
        "false_negatives": len(false_negatives),
        "skipped_regions": summary.get("skipped_regions", []),
    }


def _mean_auroc(report: dict) -> float | None:
    """Average AUROC across all windows that have a value."""
    values = [
        w["metrics"]["auroc"]
        for w in report.get("windows", [])
        if w.get("metrics", {}).get("auroc") is not None
    ]
    return sum(values) / len(values) if values else None


def _print_summary_table(metrics: dict, violations: list[str]) -> None:
    print()
    print("┌─────────────────────┬──────────────┬────────────┬────────────┬────────┐")
    print("│ Metric              │ Value        │ Floor      │ Ceiling    │ Status │")
    print("├─────────────────────┼──────────────┼────────────┼────────────┼────────┤")

    def _row(name: str, value, floor, ceiling) -> str:
        val_str = f"{value:.4f}" if isinstance(value, float) else str(value)
        floor_str = f"{floor}" if floor is not None else "—"
        ceil_str = f"{ceiling}" if ceiling is not None else "—"
        ok = True
        if value is not None:
            if floor is not None and value < floor:
                ok = False
            if ceiling is not None and value > ceiling:
                ok = False
        status = "✓" if ok else "✗ FAIL"
        return f"│ {name:<19} │ {val_str:<12} │ {floor_str:<10} │ {ceil_str:<10} │ {status:<6} │"

    for t in THRESHOLDS:
        print(_row(t["metric"], metrics.get(t["metric"]), t["floor"], t["ceiling"]))

    # false_negatives (ceiling only = 0)
    fn = metrics.get("false_negatives", 0)
    fn_ok = fn == 0
    print(
        f"│ {'false_negatives':<19} │ {str(fn):<12} │ {'—':<10} │ {'0':<10} │ {'✓' if fn_ok else '✗ FAIL':<6} │"
    )

    print("└─────────────────────┴──────────────┴────────────┴────────────┴────────┘")

    skipped = metrics.get("skipped_regions", [])
    if skipped:
        print(f"\n[warn] skipped regions: {skipped}")

    print()
    if violations:
        print(f"RESULT: {len(violations)} violation(s) detected")
        for v in violations:
            print(f"  • {v}")
    else:
        print("RESULT: all checks passed ✓")
    print()


def run_checks(summary_path: Path, report_path: Path) -> list[str]:
    summary = _load_json(summary_path)
    report = _load_json(report_path)
    metrics = _collect_metrics(summary, report)

    violations: list[str] = []

    for t in THRESHOLDS:
        value = metrics.get(t["metric"])
        if value is None:
            violations.append(f"{t['metric']}: no value found in output files")
            continue
        if t["floor"] is not None and value < t["floor"]:
            violations.append(
                f"{t['metric']} = {value:.4f} is below floor {t['floor']} ({t['rationale']})"
            )
        if t["ceiling"] is not None and value > t["ceiling"]:
            violations.append(
                f"{t['metric']} = {value:.4f} exceeds ceiling {t['ceiling']} ({t['rationale']})"
            )

    fn = metrics.get("false_negatives", 0)
    if fn > 0:
        violations.append(
            f"false_negatives = {fn}: confirmed OFAC vessel(s) scoring near-zero — "
            "check MMSI/IMO matching in the sanctions join"
        )

    _print_summary_table(metrics, violations)
    return violations


def main() -> None:
    parser = argparse.ArgumentParser(description="Score regression gate for CI")
    parser.add_argument(
        "--summary",
        default="data/processed/backtest_public_integration_summary.json",
        help="Path to backtest_public_integration_summary.json",
    )
    parser.add_argument(
        "--report",
        default="data/processed/backtest_report_public_integration.json",
        help="Path to backtest_report_public_integration.json",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    summary_path = (project_root / args.summary).resolve()
    report_path = (project_root / args.report).resolve()

    violations = run_checks(summary_path, report_path)
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
