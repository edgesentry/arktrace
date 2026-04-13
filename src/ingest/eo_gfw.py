"""
EO vessel detection ingestion — Global Fishing Watch Events API.

Fetches FISHING events from the GFW Events API for a given bounding box and
time range and stores them as eo_detections records.  These represent vessels
detected fishing in the region via AIS + ML activity classification.

Free-tier token access
----------------------
The free-tier GFW API token provides access to FISHING events only.
AIS GAP events (vessels that disabled their AIS transponder — the ideal
dark-vessel proxy) require a research or premium tier token from GFW.

To request research access: https://globalfishingwatch.org/data-access/

With a research token, change _GFW_EVENT_TYPES to ["GAP", "GAP_START"] and
update the source label to "gfw-gap" for semantically correct dark-vessel
counting in the eo_dark_count_30d feature.

With the free-tier token, FISHING events serve as a maritime activity density
signal: high fishing vessel density near a suspect vessel's track is a useful
operational context feature even if it is not a direct dark-vessel proxy.

API reference: https://globalfishingwatch.org/our-apis/documentation

Fallback: if no token is configured or the API is unreachable, records can be
ingested from a local CSV with the same schema.

CSV schema:
    detection_id  – unique identifier
    detected_at   – ISO-8601 UTC timestamp
    lat           – WGS-84 latitude (decimal degrees)
    lon           – WGS-84 longitude (decimal degrees)
    source        – data source label (e.g. "gfw", "skytruth")
    confidence    – detection confidence 0–1 (optional, default 1.0)

Usage:
    # From GFW API (requires GFW_API_TOKEN env var):
    uv run python src/ingest/eo_gfw.py --bbox 95,1,110,6 --days 365

    # From local CSV:
    uv run python src/ingest/eo_gfw.py --csv path/to/detections.csv
"""

from __future__ import annotations

import argparse
import os
import uuid
from datetime import UTC, datetime, timedelta

import duckdb
import polars as pl
from dotenv import load_dotenv

load_dotenv()

DEFAULT_DB_PATH = os.getenv("DB_PATH", "data/processed/mpol.duckdb")
GFW_API_BASE = "https://gateway.api.globalfishingwatch.org/v3"
GFW_API_TOKEN = os.getenv("GFW_API_TOKEN", "")

# Singapore / Malacca Strait default bounding box (lon_min, lat_min, lon_max, lat_max)
DEFAULT_BBOX = (95.0, 1.0, 110.0, 6.0)

_GFW_DATASET = "public-global-fishing-events:latest"
_GFW_EVENTS_PAGE_SIZE = 99999  # request the maximum to minimise pagination

# Free-tier token only grants access to FISHING events.
# Switch to ["GAP", "GAP_START"] with a research/premium token for dark-vessel detection.
_GFW_EVENT_TYPES = ["FISHING"]
_GFW_SOURCE_LABEL = "gfw-fishing"


def fetch_gfw_detections(
    bbox: tuple[float, float, float, float] = DEFAULT_BBOX,
    days: int = 365,
    api_token: str = GFW_API_TOKEN,
) -> list[dict]:
    """Fetch GFW fishing events as maritime-activity proxy records.

    Calls GET /v3/events with the configured event types.  Each event's start
    position and timestamp is mapped to one eo_detections row.  Results are
    post-filtered to the supplied bbox because the Events API does not support
    bounding-box spatial filtering natively.

    Free-tier tokens return FISHING events (vessel activity density signal).
    Research-tier tokens can return GAP/GAP_START (AIS gap = dark-vessel signal).

    Returns a list of detection dicts with keys:
        detection_id, detected_at, lat, lon, source, confidence

    Raises RuntimeError if no token is configured or the request fails.
    """
    if not api_token:
        raise RuntimeError(
            "GFW_API_TOKEN not set. Register at https://globalfishingwatch.org/data-access/ "
            "and set the token in your .env file, or use --csv for local ingestion."
        )

    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx is required for GFW API access: uv add httpx")

    lon_min, lat_min, lon_max, lat_max = bbox
    end_dt = datetime.now(UTC)
    start_dt = end_dt - timedelta(days=days)

    params: dict[str, object] = {
        "datasets[0]": _GFW_DATASET,
        "start-date": start_dt.strftime("%Y-%m-%d"),
        "end-date": end_dt.strftime("%Y-%m-%d"),
        "limit": _GFW_EVENTS_PAGE_SIZE,
        "offset": 0,
    }
    for i, etype in enumerate(_GFW_EVENT_TYPES):
        params[f"types[{i}]"] = etype

    headers = {"Authorization": f"Bearer {api_token}"}

    resp = httpx.get(
        f"{GFW_API_BASE}/events",
        params=params,
        headers=headers,
        timeout=120,
    )
    if not resp.is_success:
        raise RuntimeError(
            f"GFW Events API returned {resp.status_code}.\n"
            f"URL: {resp.url}\n"
            f"Body: {resp.text[:1000]}"
        )
    data = resp.json()

    total = data.get("total", "?") if isinstance(data, dict) else "?"
    print(
        f"[gfw] types={_GFW_EVENT_TYPES} total_global={total} "
        f"bbox=({lon_min},{lat_min},{lon_max},{lat_max})",
        flush=True,
    )

    detections = []
    for entry in data.get("entries", []):
        pos = entry.get("position") or {}
        lat = pos.get("lat") or pos.get("latitude")
        lon = pos.get("lon") or pos.get("longitude")
        if lat is None or lon is None:
            continue

        # Post-filter to bbox (Events API has no native bbox filter)
        if not (lat_min <= float(lat) <= lat_max and lon_min <= float(lon) <= lon_max):
            continue

        ts_str = entry.get("start") or entry.get("timestamp")
        if not ts_str:
            continue

        # Use potentialRisk flag as confidence signal when available (FISHING events).
        fishing_meta = entry.get("fishing") or {}
        confidence = 0.8 if fishing_meta.get("potentialRisk") else 0.5

        detections.append(
            {
                "detection_id": entry.get("id") or str(uuid.uuid4()),
                "detected_at": datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(
                    tzinfo=UTC
                ),
                "lat": float(lat),
                "lon": float(lon),
                "source": _GFW_SOURCE_LABEL,
                "confidence": confidence,
            }
        )
    return detections


def ingest_eo_records(
    records: list[dict],
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    """Insert EO detection dicts directly (for testing / programmatic use).

    Each dict must have: detected_at (datetime), lat, lon.
    detection_id is auto-generated if absent.
    """
    if not records:
        return 0

    rows = []
    for r in records:
        rows.append(
            {
                "detection_id": r.get("detection_id", str(uuid.uuid4())),
                "detected_at": r["detected_at"],
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "source": r.get("source", "unknown"),
                "confidence": float(r.get("confidence", 1.0)),
            }
        )

    df = pl.DataFrame(
        rows,
        schema={
            "detection_id": pl.Utf8,
            "detected_at": pl.Datetime("us", "UTC"),
            "lat": pl.Float64,
            "lon": pl.Float64,
            "source": pl.Utf8,
            "confidence": pl.Float32,
        },
    )

    con = duckdb.connect(db_path)
    try:
        con.execute("BEGIN")
        con.execute(
            """
            INSERT OR IGNORE INTO eo_detections
                (detection_id, detected_at, lat, lon, source, confidence)
            SELECT detection_id, detected_at, lat, lon, source, confidence
            FROM df
            """
        )
        con.execute("COMMIT")
        return len(df)
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def ingest_eo_csv(csv_path: str, db_path: str = DEFAULT_DB_PATH) -> int:
    """Load EO detections from a local CSV and upsert into eo_detections."""
    df = pl.read_csv(csv_path, try_parse_dates=True)

    missing = {"detection_id", "detected_at", "lat", "lon"} - set(df.columns)
    if missing:
        raise ValueError(f"EO CSV missing required columns: {missing}")

    for col, default in {"source": "unknown", "confidence": 1.0}.items():
        if col not in df.columns:
            df = df.with_columns(pl.lit(default).alias(col))

    df = df.select(
        [
            pl.col("detection_id").cast(pl.Utf8),
            pl.col("detected_at").cast(pl.Datetime("us", "UTC")),
            pl.col("lat").cast(pl.Float64),
            pl.col("lon").cast(pl.Float64),
            pl.col("source").cast(pl.Utf8),
            pl.col("confidence").cast(pl.Float32),
        ]
    )

    con = duckdb.connect(db_path)
    try:
        con.execute("BEGIN")
        con.execute(
            """
            INSERT OR IGNORE INTO eo_detections
                (detection_id, detected_at, lat, lon, source, confidence)
            SELECT detection_id, detected_at, lat, lon, source, confidence
            FROM df
            """
        )
        con.execute("COMMIT")
        return len(df)
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest EO vessel detections")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--csv", help="Path to local EO detections CSV")
    group.add_argument(
        "--bbox",
        help="GFW API bounding box: lon_min,lat_min,lon_max,lat_max (default: Singapore/Malacca)",
        metavar="LON_MIN,LAT_MIN,LON_MAX,LAT_MAX",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Lookback window in days (default: 365)",
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    if args.csv:
        n = ingest_eo_csv(args.csv, args.db)
        print(f"Inserted {n} EO detections from {args.csv}")
    else:
        bbox_parts = [float(x) for x in args.bbox.split(",")]
        bbox = (bbox_parts[0], bbox_parts[1], bbox_parts[2], bbox_parts[3])
        try:
            records = fetch_gfw_detections(bbox=bbox, days=args.days)
            n = ingest_eo_records(records, args.db)
            print(f"Fetched and inserted {n} EO detections from GFW API")
        except RuntimeError as e:
            print(f"GFW API unavailable: {e}")
            raise SystemExit(1)
