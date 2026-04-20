"""Review sync endpoint — called by the CF Queue consumer Worker after a user pushes."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

router = APIRouter()
logger = logging.getLogger(__name__)

_SCRIPTS_DIR = Path(__file__).resolve().parents[4] / "scripts"


def _run_merge_reviews() -> None:
    """Run sync_r2.py merge-reviews as a background task."""
    script = _SCRIPTS_DIR / "sync_r2.py"
    result = subprocess.run(
        [sys.executable, "-m", "uv", "run", "python", str(script), "merge-reviews"],
        capture_output=True,
        text=True,
        cwd=str(_SCRIPTS_DIR.parent),
    )
    if result.returncode != 0:
        logger.error("[merge-reviews] failed:\n%s\n%s", result.stdout, result.stderr)
    else:
        logger.info("[merge-reviews] done:\n%s", result.stdout)


@router.post("/api/reviews/merge", status_code=202)
async def trigger_merge_reviews(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Trigger a server-side merge of all per-user review Parquet files into
    reviews/merged/*.parquet and patch ducklake_manifest.json.

    Called by the CF Queue consumer Worker (workers/review-merge-consumer/).
    Protected by a shared secret in the X-Pipeline-Secret header.
    """
    secret = request.headers.get("X-Pipeline-Secret", "")
    expected = os.getenv("PIPELINE_SECRET", "")
    if not expected or secret != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    background_tasks.add_task(_run_merge_reviews)
    return {"status": "accepted"}
