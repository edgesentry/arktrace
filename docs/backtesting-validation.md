# Historical Backtesting Validation

This document defines the reproducible offline evaluation workflow used to validate shadow-fleet candidate detection quality against historical public evidence.

## Why Backtesting

We cannot know all true shadow-fleet vessels in real time. Backtesting provides a practical validation loop by replaying historical windows with known outcomes and measuring ranking quality.

Primary objective: maximize operational triage utility (high hit-rate in top-N candidates), not claim perfect 100% classification.

## Inputs

1. A versioned manifest file listing evaluation windows
2. A watchlist parquet per window
3. A labels CSV per window with evidence-backed positive/negative labels

Templates:

- `config/evaluation_manifest.sample.json`
- `config/eval_labels.template.csv`

## Automation Boundary

This section clarifies what can be automated end-to-end and what still requires human judgment.

### Can be automated

1. Data extraction and file generation
- Generate draft labels CSV rows from sanctions tables (MMSI/IMO/name/list source).
- Generate manifest windows with watchlist and label file paths.
- Validate required columns and file shape before running backtest.

2. Backtest execution and metric reporting
- Run historical window evaluation from manifest.
- Compute ranking and classification metrics (Precision@K, Recall@K, AUROC, PR-AUC, calibration error).
- Generate threshold suggestions for fixed review capacities.
- Export JSON reports for CI artifacts and dashboards.

3. Regression monitoring
- Run repeatable checks in CI on curated historical windows.
- Alert when key metrics drift below agreed thresholds.

### Cannot be fully automated

1. Ground-truth certainty
- Public data is incomplete and delayed; many true shadow-fleet outcomes are never formally published.
- Therefore, a fully complete positive/negative truth set cannot be auto-derived.

2. High-confidence negative labeling
- "No public evidence" is not the same as "truly negative."
- Negative labels with high confidence require analyst review and policy criteria.

3. Evidence quality and temporal validity
- Source credibility, evidence freshness, and timeline consistency require human validation.
- Leakage checks (ensuring evidence was known within the historical window) require governance decisions.

4. Operational decisioning
- The model provides ranked candidates and scores; officers decide investigation priority.
- Final status assignment (confirmed/cleared/inconclusive) is a human-in-the-loop decision.

### Recommended split of responsibilities

- Automation handles: candidate generation, metric computation, report generation, regression checks.
- Human review handles: evidence adjudication, label confidence assignment, final investigative decisions.
- Feedback loop combines both: human outcomes are fed back into periodic model/threshold updates.

## Label Policy

- `label`: `positive` or `negative`
- `label_confidence`: `high`, `medium`, `weak` (or `unknown`)
- `evidence_source`/`evidence_url`: public source traceability

Recommended:

- Use only evidence available up to each window end date
- Keep label confidence explicit to avoid over-claiming
- Prefer MMSI and IMO where possible

## Run Backtest

```bash
uv run python -m src.score.backtest \
  --manifest config/evaluation_manifest.sample.json \
  --output data/processed/backtest_report.json \
  --review-capacities 25,50,100
```

## Output

`data/processed/backtest_report.json` includes:

- Window-level metrics
- Cross-window summary with mean and 95% CI (when multiple windows exist)
- Stratified metrics by vessel type
- False-positive/false-negative example rows
- Operational threshold suggestions by review capacity

Core metrics reported:

- `precision_at_50`
- `precision_at_100`
- `recall_at_100`
- `recall_at_200`
- `auroc`
- `pr_auc`
- `calibration_error` (ECE)

## Threshold Recommendation Policy

The report includes:

1. `recommended_threshold`: score threshold maximizing F1 on labeled set
2. `ops_thresholds`: min score and hit-rate for specific review capacities

Use `ops_thresholds` for deployment defaults when analyst capacity is fixed.

## CI Integration

Unit tests validate backtest metric/report generation (`tests/test_backtest.py`).

For full offline evaluations in CI, add a scheduled job with curated historical artifacts and publish `backtest_report.json` as an artifact.
