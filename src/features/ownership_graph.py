"""
Ownership graph feature engineering.

Queries Neo4j for graph-based risk features using native Cypher BFS
(no GDS plugin required for the core features).

Output columns (one row per MMSI):
    mmsi, sanctions_distance, cluster_sanctions_ratio,
    shared_manager_risk, shared_address_centrality, sts_hub_degree

Usage:
    uv run python src/features/ownership_graph.py
"""

import os

import polars as pl
from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

MAX_HOPS = 99  # sentinel for "no sanctions connection found"


# ---------------------------------------------------------------------------
# Cypher queries
# ---------------------------------------------------------------------------

# sanctions_distance: 0 = directly sanctioned, 1 = 1-hop owner/manager,
# 2 = 2-hop through parent company, 99 = no connection.
_QUERY_SANCTIONS_DISTANCE = """
MATCH (v:Vessel)
OPTIONAL MATCH (v)-[:SANCTIONED_BY]->()
WITH v, count(*) > 0 AS direct
OPTIONAL MATCH (v)-[:OWNED_BY|MANAGED_BY]->(c1:Company)-[:SANCTIONED_BY]->()
WITH v, direct, count(DISTINCT c1) > 0 AS one_hop
OPTIONAL MATCH (v)-[:OWNED_BY|MANAGED_BY]->(:Company)
      -[:CONTROLLED_BY]->(c2:Company)-[:SANCTIONED_BY]->()
WITH v, direct, one_hop, count(DISTINCT c2) > 0 AS two_hop
RETURN v.mmsi AS mmsi,
  CASE
    WHEN direct   THEN 0
    WHEN one_hop  THEN 1
    WHEN two_hop  THEN 2
    ELSE 99
  END AS sanctions_distance
"""

# cluster_sanctions_ratio: fraction of vessels sharing the same direct owner
# that are themselves directly sanctioned (proxy for Louvain community ratio).
_QUERY_CLUSTER_RATIO = """
MATCH (v:Vessel)-[:OWNED_BY]->(c:Company)<-[:OWNED_BY]-(peer:Vessel)
WHERE peer <> v
WITH v, collect(DISTINCT peer) AS peers
WITH v, peers, size(peers) AS cluster_size
UNWIND peers AS p
OPTIONAL MATCH (p)-[:SANCTIONED_BY]->()
WITH v, cluster_size, count(DISTINCT p) AS sanctioned_count
RETURN v.mmsi AS mmsi,
  CASE WHEN cluster_size = 0 THEN 0.0
       ELSE toFloat(sanctioned_count) / cluster_size
  END AS cluster_sanctions_ratio
"""

# shared_manager_risk: min sanctions_distance among co-managed peers.
# We compute this in Python using the sanctions_distance result above.

# shared_address_centrality: vessels sharing the same registered address.
_QUERY_SHARED_ADDRESS = """
MATCH (v:Vessel)-[:OWNED_BY|MANAGED_BY]->(:Company)
      -[:REGISTERED_AT]->(addr:Address)
      <-[:REGISTERED_AT]-(:Company)<-[:OWNED_BY|MANAGED_BY]-(v2:Vessel)
WHERE v2 <> v
RETURN v.mmsi AS mmsi, count(DISTINCT v2) AS shared_address_centrality
"""

# sts_hub_degree: number of distinct vessels this vessel has STS contact with.
_QUERY_STS_HUB = """
MATCH (v:Vessel)
OPTIONAL MATCH (v)-[:STS_CONTACT]->(other:Vessel)
RETURN v.mmsi AS mmsi, count(DISTINCT other) AS sts_hub_degree
"""

# For shared_manager_risk: peers sharing the same manager.
_QUERY_MANAGER_PEERS = """
MATCH (v:Vessel)-[:MANAGED_BY]->(m:Company)<-[:MANAGED_BY]-(peer:Vessel)
WHERE peer <> v
RETURN v.mmsi AS mmsi, collect(DISTINCT peer.mmsi) AS peer_mmsis
"""


def _run(driver: Driver, cypher: str) -> list[dict]:
    with driver.session() as session:
        return [dict(r) for r in session.run(cypher)]


def _compute_shared_manager_risk(
    manager_peers: list[dict],
    sanctions_map: dict[str, int],
) -> pl.DataFrame:
    """For each vessel, find the min sanctions_distance among its manager-sharing peers."""
    rows = []
    for r in manager_peers:
        mmsi = r["mmsi"]
        peers = r["peer_mmsis"] or []
        if not peers:
            rows.append({"mmsi": mmsi, "shared_manager_risk": MAX_HOPS})
            continue
        min_dist = min((sanctions_map.get(p, MAX_HOPS) for p in peers), default=MAX_HOPS)
        rows.append({"mmsi": mmsi, "shared_manager_risk": min_dist})
    return pl.DataFrame(rows, schema={"mmsi": pl.Utf8, "shared_manager_risk": pl.Int32}) \
        if rows else pl.DataFrame(schema={"mmsi": pl.Utf8, "shared_manager_risk": pl.Int32})


def compute_ownership_graph_features(driver: Driver) -> pl.DataFrame:
    """Query Neo4j for all ownership graph features. Returns one row per MMSI."""

    # sanctions_distance
    sd_rows = _run(driver, _QUERY_SANCTIONS_DISTANCE)
    sd_df = pl.DataFrame(sd_rows, schema={"mmsi": pl.Utf8, "sanctions_distance": pl.Int32}) \
        if sd_rows else pl.DataFrame(schema={"mmsi": pl.Utf8, "sanctions_distance": pl.Int32})

    sanctions_map: dict[str, int] = dict(zip(sd_df["mmsi"].to_list(),
                                             sd_df["sanctions_distance"].to_list()))

    # cluster_sanctions_ratio
    cr_rows = _run(driver, _QUERY_CLUSTER_RATIO)
    cr_df = pl.DataFrame(cr_rows, schema={"mmsi": pl.Utf8, "cluster_sanctions_ratio": pl.Float32}) \
        if cr_rows else pl.DataFrame(schema={"mmsi": pl.Utf8, "cluster_sanctions_ratio": pl.Float32})

    # shared_manager_risk (computed in Python)
    mp_rows = _run(driver, _QUERY_MANAGER_PEERS)
    smr_df = _compute_shared_manager_risk(mp_rows, sanctions_map)

    # shared_address_centrality
    sa_rows = _run(driver, _QUERY_SHARED_ADDRESS)
    sa_df = pl.DataFrame(sa_rows, schema={"mmsi": pl.Utf8, "shared_address_centrality": pl.Int32}) \
        if sa_rows else pl.DataFrame(schema={"mmsi": pl.Utf8, "shared_address_centrality": pl.Int32})

    # sts_hub_degree
    sts_rows = _run(driver, _QUERY_STS_HUB)
    sts_df = pl.DataFrame(sts_rows, schema={"mmsi": pl.Utf8, "sts_hub_degree": pl.Int32}) \
        if sts_rows else pl.DataFrame(schema={"mmsi": pl.Utf8, "sts_hub_degree": pl.Int32})

    all_mmsi = sd_df.select("mmsi")
    if all_mmsi.is_empty():
        return pl.DataFrame(schema={
            "mmsi": pl.Utf8,
            "sanctions_distance": pl.Int32,
            "cluster_sanctions_ratio": pl.Float32,
            "shared_manager_risk": pl.Int32,
            "shared_address_centrality": pl.Int32,
            "sts_hub_degree": pl.Int32,
        })

    return (
        all_mmsi.lazy()
        .join(sd_df.lazy(),  on="mmsi", how="left")
        .join(cr_df.lazy(),  on="mmsi", how="left")
        .join(smr_df.lazy(), on="mmsi", how="left")
        .join(sa_df.lazy(),  on="mmsi", how="left")
        .join(sts_df.lazy(), on="mmsi", how="left")
        .with_columns([
            pl.col("sanctions_distance").fill_null(MAX_HOPS).cast(pl.Int32),
            pl.col("cluster_sanctions_ratio").fill_null(0.0).cast(pl.Float32),
            pl.col("shared_manager_risk").fill_null(MAX_HOPS).cast(pl.Int32),
            pl.col("shared_address_centrality").fill_null(0).cast(pl.Int32),
            pl.col("sts_hub_degree").fill_null(0).cast(pl.Int32),
        ])
        .collect()
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Compute ownership graph features")
    parser.add_argument("--neo4j-uri", default=NEO4J_URI)
    parser.add_argument("--neo4j-user", default=NEO4J_USER)
    parser.add_argument("--neo4j-password", default=NEO4J_PASSWORD)
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))
    try:
        result = compute_ownership_graph_features(driver)
        print(f"Ownership graph features: {len(result)} vessels")
        print(result.head())
    finally:
        driver.close()
