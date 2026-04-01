"""
Vessel ownership registry — Neo4j graph builder.

Builds the ownership graph in Neo4j from two sources:

1. **Vessel nodes** seeded from DuckDB vessel_meta (populated by AIS ingestion).
2. **Company, ownership, and sanctions relationships** derived from DuckDB
   sanctions_entities (populated by src/ingest/sanctions.py).
3. **Equasis-style ownership chains** from an optional CSV export.

Requires a running Neo4j instance (see AGENTS.md for the Docker command).

Usage:
    uv run python src/ingest/vessel_registry.py

    # Also load Equasis ownership chains
    uv run python src/ingest/vessel_registry.py --equasis-csv data/raw/equasis.csv
"""

import argparse
import csv
import os
from typing import Any

import duckdb
from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

load_dotenv()

DEFAULT_DB_PATH = os.getenv("DB_PATH", "data/processed/mpol.duckdb")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

BATCH_SIZE = 500


# ---------------------------------------------------------------------------
# Schema / constraints
# ---------------------------------------------------------------------------

_CONSTRAINTS = [
    "CREATE CONSTRAINT vessel_mmsi IF NOT EXISTS FOR (v:Vessel) REQUIRE v.mmsi IS UNIQUE",
    "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT country_code IF NOT EXISTS FOR (c:Country) REQUIRE c.code IS UNIQUE",
    "CREATE CONSTRAINT address_id IF NOT EXISTS FOR (a:Address) REQUIRE a.address_id IS UNIQUE",
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.person_id IS UNIQUE",
    "CREATE CONSTRAINT regime_name IF NOT EXISTS FOR (r:SanctionsRegime) REQUIRE r.name IS UNIQUE",
]


def init_constraints(driver: Driver) -> None:
    """Create uniqueness constraints (idempotent)."""
    with driver.session() as session:
        for stmt in _CONSTRAINTS:
            session.run(stmt)


# ---------------------------------------------------------------------------
# Vessel nodes from DuckDB
# ---------------------------------------------------------------------------

_MERGE_VESSELS = """
UNWIND $batch AS row
MERGE (v:Vessel {mmsi: row.mmsi})
SET v.imo  = row.imo,
    v.name = row.name
"""

_MERGE_VESSEL_ALIAS = """
UNWIND $batch AS row
MATCH (v:Vessel {mmsi: row.mmsi})
MERGE (n:VesselName {name: row.alias_name})
MERGE (v)-[:ALIAS {date: row.alias_date}]->(n)
"""


def load_vessels_from_duckdb(db_path: str, driver: Driver) -> int:
    """Seed Vessel nodes from DuckDB vessel_meta. Returns node count upserted."""
    con = duckdb.connect(db_path, read_only=True)
    try:
        rows = con.execute(
            "SELECT mmsi, COALESCE(imo,'') AS imo, COALESCE(name,'') AS name "
            "FROM vessel_meta WHERE mmsi IS NOT NULL"
        ).fetchall()
    finally:
        con.close()

    if not rows:
        return 0

    batch = [{"mmsi": r[0], "imo": r[1], "name": r[2]} for r in rows]
    total = 0
    with driver.session() as session:
        for i in range(0, len(batch), BATCH_SIZE):
            chunk = batch[i : i + BATCH_SIZE]
            session.run(_MERGE_VESSELS, batch=chunk)
            total += len(chunk)
    return total


# ---------------------------------------------------------------------------
# Company / sanctions nodes from DuckDB sanctions_entities
# ---------------------------------------------------------------------------

_MERGE_COMPANIES = """
UNWIND $batch AS row
MERGE (c:Company {id: row.entity_id})
SET c.name    = row.name,
    c.country = row.flag
WITH c, row
WHERE row.flag IS NOT NULL
MERGE (co:Country {code: row.flag})
MERGE (c)-[:REGISTERED_IN]->(co)
"""

_MERGE_VESSEL_SANCTIONS = """
UNWIND $batch AS row
MATCH (v:Vessel)
WHERE v.mmsi = row.mmsi OR v.imo = row.imo
MERGE (r:SanctionsRegime {name: row.list_source})
MERGE (v)-[:SANCTIONED_BY {list: row.list_source, date: row.entity_id}]->(r)
"""

_MERGE_COMPANY_SANCTIONS = """
UNWIND $batch AS row
MERGE (c:Company {id: row.entity_id})
SET c.name = row.name
MERGE (r:SanctionsRegime {name: row.list_source})
MERGE (c)-[:SANCTIONED_BY {list: row.list_source}]->(r)
"""


def load_sanctions_graph(db_path: str, driver: Driver) -> dict[str, int]:
    """Create Company and SanctionsRegime nodes from DuckDB sanctions_entities."""
    con = duckdb.connect(db_path, read_only=True)
    try:
        companies = con.execute(
            "SELECT entity_id, name, flag, list_source FROM sanctions_entities "
            "WHERE type IN ('Company','Organization','LegalEntity')"
        ).fetchall()

        sanctioned_vessels = con.execute(
            "SELECT entity_id, mmsi, imo, list_source FROM sanctions_entities "
            "WHERE type = 'Vessel' AND (mmsi IS NOT NULL OR imo IS NOT NULL)"
        ).fetchall()

        sanctioned_companies = con.execute(
            "SELECT entity_id, name, list_source FROM sanctions_entities "
            "WHERE type IN ('Company','Organization','LegalEntity')"
        ).fetchall()
    finally:
        con.close()

    counts: dict[str, int] = {}

    # Upsert company nodes
    company_batch = [
        {"entity_id": r[0], "name": r[1], "flag": r[2], "list_source": r[3]}
        for r in companies
    ]
    with driver.session() as session:
        for i in range(0, len(company_batch), BATCH_SIZE):
            session.run(_MERGE_COMPANIES, batch=company_batch[i : i + BATCH_SIZE])
    counts["companies"] = len(company_batch)

    # SANCTIONED_BY edges for vessels
    vessel_batch = [
        {"entity_id": r[0], "mmsi": r[1] or "", "imo": r[2] or "", "list_source": r[3]}
        for r in sanctioned_vessels
    ]
    with driver.session() as session:
        for i in range(0, len(vessel_batch), BATCH_SIZE):
            session.run(_MERGE_VESSEL_SANCTIONS, batch=vessel_batch[i : i + BATCH_SIZE])
    counts["vessel_sanctions"] = len(vessel_batch)

    # SANCTIONED_BY edges for companies
    co_sanction_batch = [
        {"entity_id": r[0], "name": r[1], "list_source": r[2]}
        for r in sanctioned_companies
    ]
    with driver.session() as session:
        for i in range(0, len(co_sanction_batch), BATCH_SIZE):
            session.run(_MERGE_COMPANY_SANCTIONS, batch=co_sanction_batch[i : i + BATCH_SIZE])
    counts["company_sanctions"] = len(co_sanction_batch)

    return counts


# ---------------------------------------------------------------------------
# Equasis CSV loader
# ---------------------------------------------------------------------------
#
# Expected CSV columns (all optional except mmsi):
#   mmsi, imo, vessel_name,
#   owner_id, owner_name, owner_country, owner_address_id, owner_address,
#   manager_id, manager_name, manager_country,
#   since, until
#
# Rows without owner_id are silently skipped (vessel node still created).

_MERGE_OWNERSHIP = """
UNWIND $batch AS row
MERGE (v:Vessel {mmsi: row.mmsi})
SET v.imo = row.imo, v.name = row.vessel_name
MERGE (c:Company {id: row.owner_id})
SET c.name = row.owner_name
WITH v, c, row
WHERE row.owner_country <> ''
MERGE (co:Country {code: row.owner_country})
MERGE (c)-[:REGISTERED_IN]->(co)
WITH v, c, row
MERGE (v)-[r:OWNED_BY]->(c)
SET r.since = row.since, r.until = row.until
"""

_MERGE_MANAGEMENT = """
UNWIND $batch AS row
MATCH (v:Vessel {mmsi: row.mmsi})
MERGE (m:Company {id: row.manager_id})
SET m.name = row.manager_name
WITH v, m, row
MERGE (v)-[r:MANAGED_BY]->(m)
SET r.since = row.since, r.until = row.until
"""

_MERGE_OWNER_ADDRESS = """
UNWIND $batch AS row
MATCH (c:Company {id: row.owner_id})
MERGE (a:Address {address_id: row.owner_address_id})
SET a.street = row.owner_address
MERGE (c)-[:REGISTERED_AT]->(a)
"""


def load_equasis_csv(csv_path: str, driver: Driver) -> dict[str, int]:
    """Load vessel ownership chains from an Equasis-style CSV export."""
    ownership_batch: list[dict] = []
    management_batch: list[dict] = []
    address_batch: list[dict] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mmsi = (row.get("mmsi") or "").strip()
            if not mmsi:
                continue

            base = {
                "mmsi": mmsi,
                "imo": (row.get("imo") or "").strip(),
                "vessel_name": (row.get("vessel_name") or "").strip(),
                "since": (row.get("since") or "").strip(),
                "until": (row.get("until") or "").strip(),
            }

            owner_id = (row.get("owner_id") or "").strip()
            if owner_id:
                ownership_batch.append({
                    **base,
                    "owner_id": owner_id,
                    "owner_name": (row.get("owner_name") or "").strip(),
                    "owner_country": (row.get("owner_country") or "").strip(),
                })

                addr_id = (row.get("owner_address_id") or "").strip()
                if addr_id:
                    address_batch.append({
                        "owner_id": owner_id,
                        "owner_address_id": addr_id,
                        "owner_address": (row.get("owner_address") or "").strip(),
                    })

            manager_id = (row.get("manager_id") or "").strip()
            if manager_id:
                management_batch.append({
                    **base,
                    "manager_id": manager_id,
                    "manager_name": (row.get("manager_name") or "").strip(),
                })

    counts: dict[str, int] = {}
    with driver.session() as session:
        for i in range(0, len(ownership_batch), BATCH_SIZE):
            session.run(_MERGE_OWNERSHIP, batch=ownership_batch[i : i + BATCH_SIZE])
        counts["ownership"] = len(ownership_batch)

        for i in range(0, len(management_batch), BATCH_SIZE):
            session.run(_MERGE_MANAGEMENT, batch=management_batch[i : i + BATCH_SIZE])
        counts["management"] = len(management_batch)

        for i in range(0, len(address_batch), BATCH_SIZE):
            session.run(_MERGE_OWNER_ADDRESS, batch=address_batch[i : i + BATCH_SIZE])
        counts["addresses"] = len(address_batch)

    return counts


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build vessel ownership graph in Neo4j")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--neo4j-uri", default=NEO4J_URI)
    parser.add_argument("--neo4j-user", default=NEO4J_USER)
    parser.add_argument("--neo4j-password", default=NEO4J_PASSWORD)
    parser.add_argument("--equasis-csv", default=None,
                        help="Path to Equasis ownership chain CSV export")
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))
    try:
        print("Initialising Neo4j constraints …")
        init_constraints(driver)

        print("Loading vessel nodes from DuckDB vessel_meta …")
        n = load_vessels_from_duckdb(args.db, driver)
        print(f"  {n} vessel nodes upserted")

        print("Loading company/sanctions graph from DuckDB sanctions_entities …")
        counts = load_sanctions_graph(args.db, driver)
        for k, v in counts.items():
            print(f"  {k}: {v}")

        if args.equasis_csv:
            print(f"Loading ownership chains from {args.equasis_csv} …")
            counts = load_equasis_csv(args.equasis_csv, driver)
            for k, v in counts.items():
                print(f"  {k}: {v}")

    finally:
        driver.close()
