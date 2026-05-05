# Development Reference

Repo layout, coding conventions, and external references.

## Repo Layout

```
.agents/skills/     Agent Skills (procedures — install: npx skills add edgesentry/arktrace)
_inputs/            Challenge docs (Cap Vista Solicitation 5.0 — do not edit)
docs/               Reference documentation (architecture, background, design decisions)
scripts/            Operator-facing CLI tools (run_pipeline.py, sync_r2.py, …)
pipeline/
  src/
    graph/          Lance Graph storage (store.py — node/relationship schemas, read/write)
    ingest/         Data ingestion (AIS, sanctions, registry, trade flow)
    features/       Feature engineering (Polars + Lance Graph)
    score/          Scoring engine (HDBSCAN, Isolation Forest, SHAP, DiD)
    analysis/       Post-confirmation intelligence (label_propagation, backtracking)
    api/            FastAPI pipeline API (POST /api/reviews/merge)
app/                React + TypeScript + Vite SPA (analyst dashboard)
  src/
    components/     KpiBar, WatchlistTable, VesselDetail, VesselMap, …
    lib/            duckdb.ts, opfs.ts, push.ts, reviews.ts, auth.ts, …
  functions/        Cloudflare Pages Functions (POST /api/reviews/push)
workers/
  review-merge-consumer/   CF Queue consumer Worker
data/
  raw/              Downloaded raw data (gitignored)
  processed/        DuckDB files, Parquet outputs, Lance Graph datasets (gitignored)
tests/
```

## Coding Conventions

- **Polars:** lazy API (`pl.scan_parquet`, `.lazy()`, `.collect()`) for all large AIS queries; avoid `.to_pandas()`
- **DuckDB:** parameterised queries only — never interpolate user-supplied strings into SQL
- **Lance Graph:** read via `src.graph.store.load_tables(db_path)`; write via `write_tables(db_path, tables)`
- **Output:** all intermediate outputs are Parquet in `data/processed/`; no CSV outputs
- **Secrets:** API keys in `.env` (gitignored); read via `python-dotenv`

## Key References

- Architecture and feature design: [architecture.md](architecture.md)
- Tech stack and data sources: [technical-solution.md](technical-solution.md)
- Implementation milestones: [roadmap/core-pipeline.md](roadmap/core-pipeline.md)

## Out of Scope

Physical vessel inspection, edge sensor measurement, and VDES communication belong in edgesentry-rs / edgesentry-app.
