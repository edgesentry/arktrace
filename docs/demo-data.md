# Demo Data — R2 Distribution

arktrace ships a lightweight **demo bundle** to Cloudflare R2 after every
successful data-publish CI run.  Developers can download it with a single
command, no credentials required, to explore the dashboard output without
running the full AIS ingestion and scoring pipeline locally.

---

## For developers — pulling the demo bundle

```bash
# Option A: convenience shell script (recommended)
bash scripts/fetch_demo_data.sh

# Option B: Python sync script
uv run python scripts/sync_r2.py pull-demo
```

Both commands download `demo.zip` from the public R2 bucket and extract:

| File | Contents |
|------|----------|
| `candidate_watchlist.parquet` | Top candidate shadow-fleet vessels, scored and ranked |
| `composite_scores.parquet` | Full composite score table for all vessels |
| `causal_effects.parquet` | C3 DiD causal uplift estimates |
| `validation_metrics.json` | Backtest metrics (AUROC, Recall@200, P@50) |

Files land in `data/processed/`.  After pulling, start the dashboard:

```bash
uv run streamlit run src/ui/app.py
open http://localhost:8501
```

### Optional extras

```bash
# OpenSanctions DuckDB — needed for integration tests, not the dashboard
uv run python scripts/sync_r2.py pull-sanctions-db

# Full pipeline snapshot — includes regional DuckDBs and Lance graphs (~500 MB)
uv run python scripts/sync_r2.py pull --region singapore
```

---

## For app owners — generating fresh demo data and pushing to R2

The CI job (`data-publish.yml`) pushes the demo bundle automatically after
every weekly pipeline run.  If you need to push a manually generated batch:

### 1. Run the pipeline locally

```bash
# Singapore is the primary demo region
uv run python scripts/run_pipeline.py --region singapore --non-interactive

# Optional: also run Japan and Middle East for a fuller candidate_watchlist
uv run python scripts/run_pipeline.py --region japan,middleeast --non-interactive
```

This writes pipeline outputs to `data/processed/`.

### 2. Run the backtest to generate validation_metrics.json

```bash
uv run python scripts/run_public_backtest_batch.py \
  --regions singapore \
  --skip-pipeline \
  --max-known-cases 200
```

### 3. Push the demo bundle to R2

```bash
# Requires R2 write credentials in .env or environment:
#   AWS_ACCESS_KEY_ID=<key>
#   AWS_SECRET_ACCESS_KEY=<secret>
uv run python scripts/sync_r2.py push-demo
```

This overwrites `demo.zip` in R2 with the current `data/processed/` outputs.
The push is idempotent — re-running it replaces the previous demo bundle.

### 4. Verify (optional)

```bash
# Pull in a clean temp directory to confirm the bundle is intact
mkdir -p /tmp/arktrace-demo-check/data/processed
uv run python scripts/sync_r2.py pull-demo --data-dir /tmp/arktrace-demo-check/data/processed
ls -lh /tmp/arktrace-demo-check/data/processed/
```

---

## R2 credentials setup

R2 credentials are only required for **push** commands.  Pull commands work
without credentials because the `arktrace-public` bucket has public access
enabled.

1. Create an R2 API token at Cloudflare Dashboard → R2 → Manage R2 API Tokens
   with **Object Read & Write** permission scoped to `arktrace-public`.
2. Add to `.env` (or set as environment variables / CI secrets):

```dotenv
AWS_ACCESS_KEY_ID=<your-r2-access-key-id>
AWS_SECRET_ACCESS_KEY=<your-r2-secret-access-key>
AWS_REGION=auto
S3_ENDPOINT=https://b8a0b09feb89390fb6e8cf4ef9294f48.r2.cloudflarestorage.com
S3_BUCKET=arktrace-public
```

In CI, these are stored as repository secrets (`AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`).

---

## CI integration

The `data-publish.yml` workflow runs every Monday 02:00 UTC and after each
successful public-backtest-integration run.  The pipeline is:

1. Pull watchlists from R2
2. Run backtest (`--skip-pipeline`)
3. **Push demo bundle** (`push-demo`) — overwrites `demo.zip`
4. Push full snapshot (`push`) — timestamped rotation zip
5. Push OpenSanctions DB (`push-sanctions-db`)
6. Send metrics email

Step 3 ensures the public demo bundle is always in sync with the latest
backtest output, so developers pulling `pull-demo` always get recent data.

See also: [r2-data-layout.md](r2-data-layout.md) for the full R2 bucket structure.
