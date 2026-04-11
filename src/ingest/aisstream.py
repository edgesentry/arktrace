"""aisstream.io WebSocket AIS collector.

aisstream.io provides a free real-time AIS WebSocket stream with global
coverage including Singapore / Malacca Strait.

Registration: https://aisstream.io  (instant — no equipment required)

WebSocket endpoint: wss://stream.aisstream.io/v0/stream

Subscription message:
    {
      "APIKey": "your-key",
      "BoundingBoxes": [[[lat_min, lon_min], [lat_max, lon_max]]],
      "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
    }

Note: aisstream.io is a live stream — no historical data. Run this on a
schedule (e.g. every 30 minutes via cron) to accumulate position history.
After 24–48 hours of collection the AIS gap features will be meaningful.

Usage:
    # Set AISSTREAM_API_KEY in .env, then:
    uv run python -m src.ingest.aisstream --duration 300   # collect 5 min
    uv run python -m src.ingest.aisstream --duration 600 --bbox -2 98 8 110
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
from datetime import datetime, timezone

import duckdb
import websockets
from dotenv import load_dotenv

from src.ingest.schema import init_schema

load_dotenv()

DEFAULT_DB_PATH = os.getenv("DB_PATH", "data/processed/mpol.duckdb")
AISSTREAM_WS_URL = "wss://stream.aisstream.io/v0/stream"

DEFAULT_BBOX = {
    "lat_min": -2.0,
    "lat_max": 8.0,
    "lon_min": 98.0,
    "lon_max": 110.0,
}


def _subscribe_message(api_key: str, bbox: dict) -> str:
    return json.dumps({
        "APIKey": api_key,
        "BoundingBoxes": [[
            [bbox["lat_min"], bbox["lon_min"]],
            [bbox["lat_max"], bbox["lon_max"]],
        ]],
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    })


def _parse_position(msg: dict) -> dict | None:
    """Extract ais_positions row from a PositionReport message."""
    meta = msg.get("MetaData", {})
    payload = msg.get("Message", {}).get("PositionReport", {})
    mmsi = str(meta.get("MMSI", "")).strip()
    if not mmsi:
        return None
    lat = payload.get("Latitude") or meta.get("latitude")
    lon = payload.get("Longitude") or meta.get("longitude")
    if lat is None or lon is None:
        return None
    ts_raw = meta.get("time_utc") or meta.get("TimeReceived")
    try:
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")) if ts_raw else datetime.now(timezone.utc)
    except (ValueError, AttributeError):
        ts = datetime.now(timezone.utc)
    return {
        "mmsi": mmsi,
        "timestamp": ts,
        "lat": float(lat),
        "lon": float(lon),
        "sog": float(payload["Sog"]) if payload.get("Sog") is not None else None,
        "cog": float(payload["Cog"]) if payload.get("Cog") is not None else None,
        "nav_status": int(payload["NavigationalStatus"]) if payload.get("NavigationalStatus") is not None else None,
        "ship_type": None,
    }


def _parse_static(msg: dict) -> dict | None:
    """Extract vessel_meta row from a ShipStaticData message."""
    meta = msg.get("MetaData", {})
    payload = msg.get("Message", {}).get("ShipStaticData", {})
    mmsi = str(meta.get("MMSI", "")).strip()
    if not mmsi:
        return None
    return {
        "mmsi": mmsi,
        "imo": str(payload.get("ImoNumber", "") or "").strip() or None,
        "name": str(payload.get("Name", "") or "").strip() or None,
        "flag": str(payload.get("Flag", "") or "").strip() or None,
        "ship_type": int(payload["Type"]) if payload.get("Type") is not None else None,
        "gross_tonnage": None,
    }


async def _collect(
    api_key: str,
    bbox: dict,
    duration: int,
    db_path: str,
) -> tuple[int, int]:
    """Connect to aisstream.io and collect for *duration* seconds.

    Returns (positions_inserted, vessels_seen).
    """
    positions: list[dict] = []
    meta_map: dict[str, dict] = {}
    deadline = asyncio.get_event_loop().time() + duration

    print(f"  Connecting to {AISSTREAM_WS_URL} …")
    async with websockets.connect(AISSTREAM_WS_URL, ping_interval=20) as ws:
        await ws.send(_subscribe_message(api_key, bbox))
        print(f"  Subscribed — collecting for {duration}s (Ctrl-C to stop early)")

        try:
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 10))
                except asyncio.TimeoutError:
                    continue

                msg = json.loads(raw)
                msg_type = msg.get("MessageType")

                if msg_type == "PositionReport":
                    row = _parse_position(msg)
                    if row:
                        positions.append(row)
                        if len(positions) % 100 == 0:
                            print(f"\r  Received {len(positions)} positions …", end="", flush=True)
                elif msg_type == "ShipStaticData":
                    row = _parse_static(msg)
                    if row:
                        meta_map[row["mmsi"]] = row

        except (websockets.exceptions.ConnectionClosed, KeyboardInterrupt):
            pass

    print(f"\n  Collected {len(positions)} positions, {len(meta_map)} vessel static records")

    if not positions:
        return 0, 0

    import polars as pl

    pos_df = pl.DataFrame(positions)  # noqa: F841
    meta_rows = list(meta_map.values())

    con = duckdb.connect(db_path)
    try:
        before = con.execute("SELECT count(*) FROM ais_positions").fetchone()[0]  # type: ignore[index]
        con.execute("""
            INSERT OR IGNORE INTO ais_positions
                (mmsi, timestamp, lat, lon, sog, cog, nav_status, ship_type)
            SELECT mmsi, timestamp, lat, lon, sog, cog, nav_status, ship_type
            FROM pos_df
        """)
        inserted = con.execute("SELECT count(*) FROM ais_positions").fetchone()[0] - before  # type: ignore[index]

        if meta_rows:
            meta_df = pl.DataFrame(meta_rows).unique(subset=["mmsi"], keep="first")  # noqa: F841
            con.execute("""
                INSERT OR IGNORE INTO vessel_meta (mmsi, imo, name, flag, ship_type, gross_tonnage)
                SELECT mmsi, imo, name, flag, ship_type, gross_tonnage
                FROM meta_df
                WHERE mmsi IS NOT NULL
            """)
    finally:
        con.close()

    return inserted, len(meta_map)


def collect(
    api_key: str,
    db_path: str = DEFAULT_DB_PATH,
    bbox: dict | None = None,
    duration: int = 300,
) -> tuple[int, int]:
    """Blocking entry point — collect AIS data for *duration* seconds."""
    init_schema(db_path)
    bb = bbox or DEFAULT_BBOX

    # Handle Ctrl-C gracefully in sync context
    loop = asyncio.new_event_loop()

    def _sigint(sig, frame):  # type: ignore[type-arg]
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGINT, _sigint)

    try:
        return loop.run_until_complete(_collect(api_key, bb, duration, db_path))
    finally:
        loop.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect live AIS from aisstream.io into DuckDB")
    parser.add_argument(
        "--api-key",
        default=os.getenv("AISSTREAM_API_KEY", ""),
        help="aisstream.io API key (or set AISSTREAM_API_KEY in .env)",
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Collection duration in seconds (default: 300 = 5 min)",
    )
    parser.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        metavar=("LAT_MIN", "LON_MIN", "LAT_MAX", "LON_MAX"),
        default=None,
        help=(
            "Bounding box: lat_min lon_min lat_max lon_max. "
            "Default: Singapore/Malacca (-2 98 8 110). "
            "Strait only: 1.0 103.5 1.5 104.5"
        ),
    )
    args = parser.parse_args()

    if not args.api_key:
        parser.error(
            "API key required. Set AISSTREAM_API_KEY in .env or pass --api-key. "
            "Register free at https://aisstream.io"
        )

    bbox = None
    if args.bbox:
        lat_min, lon_min, lat_max, lon_max = args.bbox
        bbox = {"lat_min": lat_min, "lat_max": lat_max, "lon_min": lon_min, "lon_max": lon_max}

    inserted, vessels = collect(args.api_key, args.db, bbox, args.duration)
    print(f"Rows inserted into ais_positions : {inserted}")
    print(f"Vessels in vessel_meta           : {vessels}")


if __name__ == "__main__":
    main()
