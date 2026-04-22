# arktrace

**Causal Inference Engine for Shadow Fleet Prediction** — identifies vessels that *causally respond* to sanction announcements with evasion behaviour, ranking unknown threats before they appear on public sanctions lists.

Built for **Cap Vista Accelerator Solicitation 5.0, Challenge 1** (deadline: 29 April 2026).

## Quick Start

### Dashboard (browser app — no server required)

The dashboard is a static React SPA deployed to Cloudflare Pages. Open it directly:

**[arktrace.edgesentry.io](https://arktrace.edgesentry.io)** — demo data loaded automatically, no credentials needed.

To run the dashboard locally from source:

```bash
git clone https://github.com/edgesentry/arktrace && cd arktrace
cd app && npm install   # first time only
cd app && npm run dev   # http://localhost:5173
```

Prerequisites: Node.js 20+.

### Pipeline — run the scoring pipeline

```bash
git clone https://github.com/edgesentry/arktrace && cd arktrace
uv sync --all-extras

# Pull demo data from R2 (no credentials needed)
uv run python scripts/sync_r2.py pull-demo

# Score a region
uv run python scripts/run_pipeline.py --region japan --non-interactive
```

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/).

Supported regions: `singapore`, `japan`, `middleeast`, `europe`, `persiangulf`, `blacksea`, `gulfofaden`, `gulfofguinea`, `gulfofmexico`.

### Docker — pipeline only

The Docker image runs the **pipeline** (not the dashboard). The dashboard is served from Cloudflare Pages.

```bash
docker run \
  -v arktrace-data:/root/.arktrace/data \
  ghcr.io/edgesentry/arktrace:latest \
  python scripts/run_pipeline.py --region singapore --non-interactive
```

See [docs/deployment.md](docs/deployment.md) for full setup options.

### macOS — AIS stream collection

To collect live AIS position data via launchd agents (one per region):

```bash
# Install stream collectors + R2 backup job (reads credentials from ~/.zshrc or .env)
bash scripts/install_launchd_agents.sh

# Check status
bash scripts/install_launchd_agents.sh --status

# Install all regions
bash scripts/install_launchd_agents.sh --all
```

See [docs/deployment.md](docs/deployment.md) for credential setup.

### Operations shell

For a menu-driven interface covering pipeline runs, backtesting, R2 sync, and feedback loops:

```bash
bash scripts/run_operations_shell.sh
```

## What It Does

arktrace applies Difference-in-Differences (DiD) causal modelling to identify vessels whose behaviour changed *specifically because of* a sanction event — not merely vessels that look anomalous. AIS position history, ownership graph proximity, and trade flow data serve as the evidentiary substrate.

**Two-phase architecture:**

1. **Deterministic scoring pipeline** — feature engineering, anomaly detection (Isolation Forest + HDBSCAN), ownership graph risk, identity confidence, DiD causal model, SHAP attribution. No LLM involved.
2. **Bounded text synthesis** — the browser app generates plain-language patrol briefs via a local LLM endpoint with strict anti-hallucination constraints (system prompt, `max_tokens=200`, `temperature=0.3`). The LLM cannot modify scores or access external data. See [docs/llm-grounding.md](docs/llm-grounding.md).

**Output:** `candidate_watchlist.parquet` — ranked vessels with composite confidence score, SHAP-explained signals, causal ATT estimate, and ownership graph path, ready for duty-officer triage.

**Validated metrics (blind run, singapore, 2026-04-14):**

| Metric | Value | Notes |
|---|---|---|
| AUROC | 1.0 | All confirmed positives ranked above all negatives |
| Recall@200 | 1.0 | All confirmed positives in top 200 |
| Precision@50 | 0.06 | Structural ceiling = 3 positives / 50 labeled rows |
| Precision@50 (multi-region, ≥50 labels) | 0.68 | Demonstrated technical ceiling; CI regression gate |
| Precision@50 contractual gate | ≥ 0.60 | Cap Vista Scope of Work acceptance threshold |

See [docs/evaluation-metrics.md](docs/evaluation-metrics.md) for the full metric hierarchy and seeded vs. blind run disclosure.

## Why this project is called Arktrace?

`Arktrace` is a portmanteau of "Ark" (denoting protection, sanctuary, and the traditional maritime vessel) and "Trace" (representing the digital footprint, vessel tracks, and the pursuit of evidence).

## Documentation

Full documentation is in [`docs/`](docs/):

| Document | Contents |
|---|---|
| [Introduction](docs/index.md) | What it does, how it fits the full system, Cap Vista alignment |
| [Background](docs/background.md) | Shadow fleet problem, geography, evasion techniques, prior art |
| [Architecture](docs/architecture.md) | Pipeline diagram, data storage design, feature and scoring design |
| [Technical Solution](docs/technical-solution.md) | Tech stack, data sources, algorithms, output schema |
| [Deployment](docs/deployment.md) | Docker, native setup, cloud deployment, AIS stream collection |
| [Development](docs/development.md) | Repo layout, commands, coding conventions |
| [Scenarios](docs/scenarios.md) | End-to-end workflows: morning brief, investigation, streaming, patrol handoff |
| [Evaluation Metrics](docs/evaluation-metrics.md) | Metric definitions, acceptance thresholds, seeded vs. blind disclosure |
| [Backtesting Validation](docs/backtesting-validation.md) | Offline evaluation workflow, labels policy, threshold tuning |
| [LLM Grounding](docs/llm-grounding.md) | Two-phase architecture, anti-hallucination constraints, prompt templates |
| [Regional Playbooks](docs/regional-playbooks.md) | Per-region AIS bbox, weight tuning, and operational notes |
| [Trial Specification](docs/trial-specification.md) | Datasets, platform requirements, trial demonstration strategy |
| [Prelabel Governance](docs/prelabel-governance.md) | Analyst pre-label policy, leakage rules, confidence tiers |
| [Triage Governance](docs/triage-governance.md) | Tier taxonomy, evidence policy, escalation lifecycle, KPI spec |
| [Roadmap](docs/roadmap.md) | Phase A (screening) + Phase B (field investigation) |
| [Field Investigation](docs/field-investigation.md) | Physical vessel measurement, evidence capture, VDES reporting |

## Scope

**This repo:** AIS ingestion → feature engineering → shadow fleet scoring → ranked candidate watchlist → browser dashboard.

**Out of scope:** Physical vessel inspection, edge sensor measurement, VDES reporting — implemented in [edgesentry-rs](https://github.com/edgesentry/edgesentry-rs) and edgesentry-app. See [docs/field-investigation.md](docs/field-investigation.md) for the design.

## License

Apache-2.0 OR MIT
