# Analyst Pre-Label Holdout Governance

This document defines the policy for creating, maintaining, and using the analyst-curated pre-label holdout set introduced in [#62](https://github.com/edgesentry/arktrace/issues/62).

## Purpose

Public-data backtesting (C9 / issue #53) measures how well the model ranks vessels that are *already* on sanctions lists. That approach has a structural blind spot: the most operationally valuable cases are vessels that are **not yet publicly confirmed** but show the same behavioural indicators.

The analyst pre-label holdout set addresses this by providing leading-indicator ground truth:

- Analyst labels vessels *before* they appear on any sanctions list.
- The model is evaluated against those labels to measure early-detection capability.
- As labels mature (confirmed or cleared by public evidence), they convert to confirmed labels in the standard backtest pipeline.

---

## Pre-Label Taxonomy

| Pre-label | Meaning | Maps to in evaluation |
|---|---|---|
| `suspected-positive` | Analyst believes vessel is conducting evasion, with documented evidence, but no public confirmation yet | `y_true = 1` |
| `analyst-negative` | Analyst has reviewed and determined vessel is not a shadow-fleet candidate, despite model signals | `y_true = 0` |
| `uncertain` | Insufficient evidence to decide either way; kept for monitoring but excluded from binary metrics | `y_true = None` (excluded) |

---

## Confidence Tiers

| Tier | Criteria |
|---|---|
| `high` | Multiple independent corroborating signals (e.g. AIS manipulation + STS satellite imagery + ownership evasion pattern) with specific evidence links |
| `medium` | Two or more indicators, with at least one documented source, but some ambiguity remains |
| `weak` | Single indicator only, or significant alternative explanation exists; included for monitoring but not primary KPI |

Use `--min-confidence-tier medium` in evaluation runs to exclude weak labels from precision/recall metrics. Use `weak` only for exploratory analysis.

---

## Evidence Requirements

Every pre-label entry must include:

| Field | Requirement |
|---|---|
| `mmsi` | 9-digit MMSI (mandatory) |
| `imo` | IMO number where known |
| `pre_label` | One of `suspected-positive`, `uncertain`, `analyst-negative` |
| `confidence_tier` | One of `high`, `medium`, `weak` |
| `region` | One of `singapore`, `middleeast`, `europe`, `japan`, `persiangulf`, `blacksea`, `gulfofaden`, `gulfofguinea`, `gulfofmexico` |
| `evidence_notes` | Human-readable summary of the evidence basis (mandatory) |
| `source_urls` | At least one URL or internal report reference for `high`/`medium` labels |
| `analyst_id` | Analyst identifier (e.g. `analyst-a`) |
| `evidence_timestamp` | ISO-8601 timestamp — **when the evidence was gathered**, not when the row was entered |

The `evidence_timestamp` is the leakage control gate. Any pre-label with `evidence_timestamp > window_end_date` is automatically dropped before evaluation.

---

## Leakage Policy

A pre-label is only valid for evaluating a window if the analyst had access to the evidence **before the window closed**.

```
evidence_timestamp <= window_end_date
```

This prevents future knowledge from inflating metrics. The evaluation pipeline enforces this automatically and reports the count of dropped labels in `leakage_report.labels_dropped`.

Consequences:
- Use `--end-date` (or `window_end_date` in manifests) when running evaluation.
- Analysts must record `evidence_timestamp` as the date the evidence was observed, not the date of entry.
- Back-filling with post-hoc analysis is not permitted.

---

## Holdout Dataset Provenance

The initial curated set is stored at:

```
data/demo/analyst_prelabels_demo.csv
```

| Attribute | Value |
|---|---|
| Vessel count | 60 |
| Regions | `singapore` (20), `middleeast` (20), `europe` (20) |
| Class breakdown | ~30 suspected-positive, ~10 uncertain, ~15 analyst-negative |
| Evidence window | 2025-09 through 2025-11 |
| Version | v1.0 |

The demo CSV is a portable fixture for development and testing. Operational pre-labels reside in the `analyst_prelabels` DuckDB table (persisted in `data/processed/mpol.duckdb`).

To load the demo set into the database:

```python
import duckdb, csv

con = duckdb.connect("data/processed/mpol.duckdb")
with open("data/demo/analyst_prelabels_demo.csv") as f:
    rows = list(csv.DictReader(f))
for row in rows:
    con.execute(
        "INSERT INTO analyst_prelabels "
        "(mmsi, imo, pre_label, confidence_tier, region, evidence_notes, "
        " source_urls_json, analyst_id, evidence_timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [row["mmsi"], row.get("imo"), row["pre_label"], row["confidence_tier"],
         row.get("region"), row.get("evidence_notes"), row.get("source_urls"),
         row["analyst_id"], row["evidence_timestamp"]],
    )
con.close()
```

---

## Review Cadence

| Frequency | Action |
|---|---|
| **Monthly** | Review all `uncertain` labels; upgrade to `suspected-positive` or `analyst-negative` where evidence has developed |
| **Monthly** | Check `suspected-positive` labels against updated sanctions lists; convert to confirmed backtest labels if publicly confirmed |
| **Quarterly** | Full holdout set audit: verify evidence links still resolve, update confidence tiers, remove stale entries |
| **Triggered** | When a vessel in the holdout set appears on a public sanctions list, immediately reclassify and flag for retrospective analysis |

**Assigned:** The analyst who created the label is responsible for the monthly review. The senior analyst covers labels where the original analyst is unavailable.

---

## Versioning

When significant changes are made to the holdout set (new entries, confidence upgrades, reclassifications):

1. Export the current state to a versioned CSV: `data/demo/analyst_prelabels_v{N}.csv`
2. Record the manifest entry in `data/processed/prelabel_manifest.json` (auto-generated by `scripts/run_prelabel_evaluation.py`)
3. Commit the versioned CSV under `data/demo/` with a descriptive message

---

## Running the Pre-Label Evaluation

Against the demo CSV:

```bash
uv run python -m src.score.prelabel_evaluation \
  --watchlist data/processed/candidate_watchlist.parquet \
  --prelabels-csv data/demo/analyst_prelabels_demo.csv \
  --output data/processed/prelabel_evaluation.json \
  --end-date 2025-11-15 \
  --min-confidence-tier medium \
  --review-capacities 25,50,100
```

Against the database:

```bash
uv run python -m src.score.prelabel_evaluation \
  --watchlist data/processed/candidate_watchlist.parquet \
  --db data/processed/mpol.duckdb \
  --output data/processed/prelabel_evaluation.json \
  --end-date 2025-11-15 \
  --region singapore \
  --min-confidence-tier medium \
  --review-capacities 25,50,100
```

---

## Disagreement Analysis

The evaluation report includes a disagreement section highlighting cases where the model and analyst diverge:

- **`model_high_analyst_negative`**: Vessels the model scored ≥ threshold that the analyst cleared. Review these to identify model false positives that may warrant feature adjustment.
- **`model_low_analyst_positive`**: Vessels the analyst suspects but the model ranked low. These are high-value misses — review signals and consider feature uplift.

The disagreement threshold defaults to the best-F1 threshold on the labeled set. Override with `--disagreement-threshold`.

---

## Integration with Public-Data Backtest

The pre-label evaluation is a **separate reporting slice** from the public-label backtest. Do not merge the two:

| Slice | Label source | Purpose |
|---|---|---|
| Public-label backtest | OFAC / UN / EU sanctions | Measures confirmed-case recall; lagging indicator |
| Pre-label holdout | Analyst curation | Measures early-detection precision; leading indicator |

Run both and compare. If the public-label backtest is strong but the pre-label precision is low, the model is detecting known entities but missing novel evasion patterns.
