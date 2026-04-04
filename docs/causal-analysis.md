# Causal Analysis: Unknown-Unknown Reasoning and Drift Monitoring

This document explains the `src/analysis/causal.py` and `src/analysis/monitor.py`
prototype modules introduced in issue #63.

---

## 1. Unknown-Unknown Causal Reasoner (`src/analysis/causal.py`)

### Problem

The C3 DiD model (`src/score/causal_sanction.py`) quantifies causal links between
sanction announcements and AIS-gap behaviour for vessels already *connected* to the
known sanctions graph.  This leaves a blind spot: vessels with no current sanctions
overlap that nonetheless exhibit evasion-consistent behaviour — the "unknown-unknowns".

### Method

For every vessel with `sanctions_distance = 99` (no graph link):

1. **Feature-delta profile** — compare AIS gap rate in the recent 30-day window vs
   the 30–90-day baseline window (same DiD intuition as C3, applied per-vessel).
2. **Static signal checks** — `sts_candidate_count ≥ 3` and `flag_changes_2y ≥ 2`
   from `vessel_features` are treated as additional evasion signals.
3. **Signal scoring** — matching signals are combined via mean log-uplift, normalised
   to [0, 1] with a soft cap at 10× uplift.
4. **Causal evidence attachment** — C3 `CausalEffect` objects (ATT, CI, p-value) from
   regimes with positive ATT are attached as context for analyst prompts.

### Confidence and limitations

- A high causal score is an **investigative lead**, not a confirmed finding.
- The module cannot distinguish vessels with legitimately elevated activity from evasion
  candidates without additional field evidence.
- C3 causal evidence is regime-level (not vessel-level); it describes *in general* how
  sanctions affect gap behaviour, not whether *this specific vessel* responded to an
  announcement.
- Minimum signals threshold (`min_signals=1` by default) can be raised to reduce false
  positives at the cost of lower recall.

### Usage

```python
from src.analysis.causal import score_unknown_unknowns
from src.score.causal_sanction import run_causal_model

effects = run_causal_model()
candidates = score_unknown_unknowns(db_path="data/processed/mpol.duckdb",
                                    causal_effects=effects)
for c in candidates[:5]:
    print(c.mmsi, c.causal_score)
    print(c.prompt_context())
```

### Analyst brief integration

When `GET /api/briefs/{mmsi}` is called, the brief system prompt automatically
includes the candidate's causal evidence context (if the vessel appears in the
unknown-unknown ranked list).  The context block has the form:

```
CAUSAL EVIDENCE (unknown-unknown candidate):
  • [OFAC Russia] ATT=+2.345 (95% CI [0.800, 3.890]), p=0.0210 (significant)
BEHAVIOURAL SIGNALS:
  • ais_gap_count: recent=8.00, baseline=0.50, uplift×16.00
  • flag_changes_2y: recent=3.00, baseline=0.00, uplift×3.00
NOTE: This vessel is NOT in any current sanctions list. ...
```

---

## 2. Drift Monitor (`src/analysis/monitor.py`)

### Overview

The drift monitor runs four automated checks and emits `DriftAlert` objects with
severity levels `ok | warning | critical`.

| Check | What it detects |
|---|---|
| `ais_gap_rate` | Shift in AIS gap rate (gaps/vessel-day) between recent 30d and baseline 30–90d |
| `flag_distribution` | Shift in mean high-risk flag ratio vs a reference baseline (0.35) |
| `watchlist_score_shift` | Change in mean confidence score across sequential review history halves |
| `concept_drift_proxy` | Drop in confirmed/probable ratio across two sequential 90-day review windows |

### Severity thresholds

| Check | Warning | Critical |
|---|---|---|
| AIS gap rate | ±30% relative change | ±60% |
| Flag distribution | ±10% relative change | ±25% |
| Watchlist score | ±8% relative change | ±15% |
| Concept drift proxy | ±10% relative change | ±20% |

### What counts as a drift alert

A `warning` alert should trigger **investigation**: review whether recent ingestion
quality has changed, whether new vessel classes have been added to the watchlist,
or whether analyst review behaviour has shifted.

A `critical` alert should trigger **escalation**: notify the data/model owner and
consider pausing automated ranking decisions until the root cause is understood.

### Limitations

- `watchlist_score_shift` and `concept_drift_proxy` require at least 10 review records
  to produce non-trivial output.
- `flag_distribution` uses a hard-coded reference baseline (0.35) rather than a stored
  snapshot — this is a prototype approximation.
- None of these checks substitute for a proper held-out evaluation set (see issue #62).

### CLI usage

```bash
# Human-readable output
uv run python src/analysis/monitor.py --db data/processed/mpol.duckdb

# Machine-readable JSON
uv run python src/analysis/monitor.py --db data/processed/mpol.duckdb --json
```

### Programmatic usage

```python
from src.analysis.monitor import run_drift_checks, alerts_to_dict

alerts = run_drift_checks("data/processed/mpol.duckdb")
for alert in alerts:
    if alert.severity != "ok":
        print(alert)

# JSON export
import json
print(json.dumps(alerts_to_dict(alerts), indent=2))
```
