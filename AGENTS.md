# AGENTS

Shadow fleet candidate screening application. Consumes edgesentry-rs primitives; business logic lives here, not in edgesentry-rs.

## Directory map

| Path | Purpose |
|---|---|
| `pipeline/src/ingest/` | AIS, sanctions, vessel registry, EO detection ingestion |
| `pipeline/src/features/` | Feature engineering (AIS behaviour, identity, ownership graph, trade mismatch) |
| `pipeline/src/score/` | Scoring: HDBSCAN baseline, Isolation Forest, DiD causal model, composite + SHAP |
| `pipeline/src/analysis/` | Post-confirmation: label propagation, causal rewind, backtracking |
| `pipeline/src/graph/` | Lance Graph storage (node/relationship schemas, read/write) |
| `pipeline/src/api/` | FastAPI endpoint (`POST /api/reviews/merge`) |
| `app/src/` | React SPA — KpiBar, WatchlistTable, VesselDetail, VesselMap |
| `app/src/lib/` | DuckDB-WASM, OPFS, push/pull, auth |
| `app/functions/` | Cloudflare Pages Functions (`POST /api/reviews/push`) |
| `workers/` | CF Queue consumer Worker (review-merge) |
| `scripts/` | Operator CLI: `run_pipeline.py`, `sync_r2.py`, `run_operations_shell.sh` |
| `data/processed/` | DuckDB files, Parquet outputs, Lance Graph datasets (gitignored) |
| `tests/` | Pipeline unit and integration tests |
| `docs/` | Architecture, background, scenarios, LLM grounding, roadmap |

## Key files

- Pipeline entry point: `scripts/run_pipeline.py`
- Scoring output: `data/processed/candidate_watchlist.parquet`
- Schema: `pipeline/src/ingest/schema.py`
- Dashboard entry: `app/src/main.tsx`

## Coding conventions

- **Polars:** use lazy API (`pl.scan_parquet`, `.lazy()`, `.collect()`) for large AIS queries
- **DuckDB:** parameterised queries only — never interpolate user strings into SQL
- **Lance Graph:** read via `src.graph.store.load_tables()`; write via `write_tables()`
- **Output:** all intermediate outputs are Parquet in `data/processed/`; no CSV outputs
- **Secrets:** API keys in `.env` (gitignored); read via `python-dotenv`

## Commit convention

Conventional Commits (`fix:`, `feat:`, `feat!:`)

## Docs

- Architecture and data flow: `docs/architecture.md`
- Problem context: `docs/background.md`
- Tech stack and algorithms: `docs/technical-solution.md`
- LLM anti-hallucination design: `docs/llm-grounding.md`
- Use case flows: `docs/scenarios.md`
- Roadmap: `docs/roadmap/index.md`

## Agent Skills

```bash
npx skills add edgesentry/arktrace
```

| Skill | Trigger |
|---|---|
| `/arktrace-run-pipeline` | Scoring a region; refreshing the watchlist; when pipeline step fails |
| `/arktrace-run-dashboard` | Developing the React frontend; verifying UI changes locally |
| `/arktrace-run-tests` | Before committing; when CI fails on pytest or eslint |
| `/arktrace-deploy` | Setting up Cloudflare Pages, R2, or CI; updating production config |
| `/arktrace-llm-setup` | Configuring LLM provider (OpenAI / Ollama / llama.cpp) |
| `/arktrace-demo-data` | Need sample data without running the full pipeline |
