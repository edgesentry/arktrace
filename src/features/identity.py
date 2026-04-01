"""
Identity volatility feature engineering.

Queries Neo4j for per-vessel identity change counts and ownership structure.
Also reads vessel_meta from DuckDB for the current flag state.

Output columns (one row per MMSI):
    mmsi, flag_changes_2y, name_changes_2y, owner_changes_2y,
    high_risk_flag_ratio, ownership_depth

Usage:
    uv run python src/features/identity.py
"""

import os

import duckdb
import polars as pl
from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase

load_dotenv()

DEFAULT_DB_PATH = os.getenv("DB_PATH", "data/processed/mpol.duckdb")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Flags with weak Port State Control oversight (UNCTAD/Paris MOU grey/black list proxies)
HIGH_RISK_FLAGS = {
    "KP", "IR", "VE", "SY", "CU",   # sanctioned states
    "KM", "GA", "CM", "PW",          # high-risk open registries (Comoros, Gabon, Cameroon, Palau)
    "KI", "TG", "SL", "ST",          # frequently flagged in shadow fleet reports
}


# ---------------------------------------------------------------------------
# Neo4j queries
# ---------------------------------------------------------------------------

_QUERY_NAME_CHANGES = """
MATCH (v:Vessel)
OPTIONAL MATCH (v)-[:ALIAS]->(n:VesselName)
RETURN v.mmsi AS mmsi, count(n) AS name_changes_2y
"""

_QUERY_OWNER_CHANGES = """
MATCH (v:Vessel)
OPTIONAL MATCH (v)-[r:OWNED_BY]->()
RETURN v.mmsi AS mmsi, count(r) AS owner_changes_2y
"""

_QUERY_OWNERSHIP_DEPTH = """
MATCH (v:Vessel)
OPTIONAL MATCH path = (v)-[:OWNED_BY]->(:Company)-[:CONTROLLED_BY*0..5]->(:Company)
RETURN v.mmsi AS mmsi, coalesce(max(length(path)), 0) AS ownership_depth
"""

_QUERY_OWNER_COUNTRIES = """
MATCH (v:Vessel)
OPTIONAL MATCH (v)-[:OWNED_BY]->(c:Company)-[:REGISTERED_IN]->(co:Country)
RETURN v.mmsi AS mmsi, collect(co.code) AS owner_countries
"""


def _run_query(driver: Driver, cypher: str) -> list[dict]:
    with driver.session() as session:
        return [dict(r) for r in session.run(cypher)]


def _compute_high_risk_ratio(owner_countries: list[str]) -> float:
    """Fraction of owning-company country codes that are high-risk."""
    if not owner_countries:
        return 0.0
    risky = sum(1 for c in owner_countries if c in HIGH_RISK_FLAGS)
    return risky / len(owner_countries)


def compute_identity_features(
    driver: Driver,
    db_path: str = DEFAULT_DB_PATH,
) -> pl.DataFrame:
    """Query Neo4j + DuckDB for identity volatility features."""

    # --- Name changes ---
    name_rows = _run_query(driver, _QUERY_NAME_CHANGES)
    name_df = pl.DataFrame(name_rows, schema={"mmsi": pl.Utf8, "name_changes_2y": pl.Int32}) \
        if name_rows else pl.DataFrame(schema={"mmsi": pl.Utf8, "name_changes_2y": pl.Int32})

    # --- Owner changes ---
    owner_rows = _run_query(driver, _QUERY_OWNER_CHANGES)
    owner_df = pl.DataFrame(owner_rows, schema={"mmsi": pl.Utf8, "owner_changes_2y": pl.Int32}) \
        if owner_rows else pl.DataFrame(schema={"mmsi": pl.Utf8, "owner_changes_2y": pl.Int32})

    # --- Ownership depth ---
    depth_rows = _run_query(driver, _QUERY_OWNERSHIP_DEPTH)
    depth_df = pl.DataFrame(depth_rows, schema={"mmsi": pl.Utf8, "ownership_depth": pl.Int32}) \
        if depth_rows else pl.DataFrame(schema={"mmsi": pl.Utf8, "ownership_depth": pl.Int32})

    # --- High-risk flag ratio (from owning company countries) ---
    country_rows = _run_query(driver, _QUERY_OWNER_COUNTRIES)
    if country_rows:
        hrisk_df = pl.DataFrame([
            {
                "mmsi": r["mmsi"],
                "high_risk_flag_ratio": _compute_high_risk_ratio(r["owner_countries"] or []),
            }
            for r in country_rows
        ], schema={"mmsi": pl.Utf8, "high_risk_flag_ratio": pl.Float32})
    else:
        hrisk_df = pl.DataFrame(schema={"mmsi": pl.Utf8, "high_risk_flag_ratio": pl.Float32})

    # --- flag_changes_2y: from vessel current flag in DuckDB (0 where history unavailable) ---
    con = duckdb.connect(db_path, read_only=True)
    try:
        meta = con.execute(
            "SELECT mmsi, COALESCE(flag,'') AS flag FROM vessel_meta WHERE mmsi IS NOT NULL"
        ).pl()
    finally:
        con.close()

    flag_df = meta.with_columns(
        pl.lit(0).cast(pl.Int32).alias("flag_changes_2y")
    ).select(["mmsi", "flag_changes_2y"])

    # --- Join ---
    all_mmsi = name_df.select("mmsi")
    if all_mmsi.is_empty() and not flag_df.is_empty():
        all_mmsi = flag_df.select("mmsi")

    return (
        all_mmsi.lazy()
        .join(name_df.lazy(),  on="mmsi", how="left")
        .join(owner_df.lazy(), on="mmsi", how="left")
        .join(depth_df.lazy(), on="mmsi", how="left")
        .join(hrisk_df.lazy(), on="mmsi", how="left")
        .join(flag_df.lazy(),  on="mmsi", how="left")
        .with_columns([
            pl.col("flag_changes_2y").fill_null(0).cast(pl.Int32),
            pl.col("name_changes_2y").fill_null(0).cast(pl.Int32),
            pl.col("owner_changes_2y").fill_null(0).cast(pl.Int32),
            pl.col("high_risk_flag_ratio").fill_null(0.0).cast(pl.Float32),
            pl.col("ownership_depth").fill_null(0).cast(pl.Int32),
        ])
        .collect()
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Compute identity volatility features")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--neo4j-uri", default=NEO4J_URI)
    parser.add_argument("--neo4j-user", default=NEO4J_USER)
    parser.add_argument("--neo4j-password", default=NEO4J_PASSWORD)
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))
    try:
        result = compute_identity_features(driver, args.db)
        print(f"Identity features: {len(result)} vessels")
        print(result.head())
    finally:
        driver.close()
