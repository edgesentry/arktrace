"""
Unit tests for vessel_registry.py.

Neo4j driver calls are mocked — no live Neo4j instance is required.
"""

import csv
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import duckdb

from src.ingest.vessel_registry import (
    _CONSTRAINTS,
    BATCH_SIZE,
    init_constraints,
    load_equasis_csv,
    load_sanctions_graph,
    load_vessels_from_duckdb,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_driver(rows_by_query: dict | None = None):
    """Return a MagicMock Neo4j driver whose session().run() records calls."""
    session_mock = MagicMock()
    driver_mock = MagicMock()
    driver_mock.session.return_value.__enter__ = MagicMock(return_value=session_mock)
    driver_mock.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver_mock, session_mock


def _seed_vessel_meta(db_path: str, rows: list[tuple]) -> None:
    """Insert (mmsi, imo, name) rows into vessel_meta."""
    con = duckdb.connect(db_path)
    for mmsi, imo, name in rows:
        con.execute(
            "INSERT OR IGNORE INTO vessel_meta (mmsi, imo, name) VALUES (?, ?, ?)",
            [mmsi, imo, name],
        )
    con.close()


def _seed_sanctions(db_path: str, rows: list[tuple]) -> None:
    """Insert (entity_id, name, mmsi, imo, flag, type, list_source) into sanctions_entities."""
    con = duckdb.connect(db_path)
    for row in rows:
        con.execute(
            "INSERT OR IGNORE INTO sanctions_entities "
            "(entity_id, name, mmsi, imo, flag, type, list_source) VALUES (?,?,?,?,?,?,?)",
            list(row),
        )
    con.close()


# ---------------------------------------------------------------------------
# init_constraints
# ---------------------------------------------------------------------------

def test_init_constraints_runs_all_statements():
    driver, session = _make_driver()
    init_constraints(driver)
    assert session.run.call_count == len(_CONSTRAINTS)
    called_stmts = [c.args[0] for c in session.run.call_args_list]
    for stmt in _CONSTRAINTS:
        assert stmt in called_stmts


# ---------------------------------------------------------------------------
# load_vessels_from_duckdb
# ---------------------------------------------------------------------------

def test_load_vessels_empty_table(tmp_db):
    driver, session = _make_driver()
    n = load_vessels_from_duckdb(tmp_db, driver)
    assert n == 0
    session.run.assert_not_called()


def test_load_vessels_calls_merge(tmp_db):
    _seed_vessel_meta(tmp_db, [("123456789", "IMO001", "SHIP A"), ("999999999", "", "SHIP B")])
    driver, session = _make_driver()
    n = load_vessels_from_duckdb(tmp_db, driver)
    assert n == 2
    assert session.run.call_count >= 1
    # The batch kwarg should contain both vessels
    all_batches = []
    for c in session.run.call_args_list:
        batch = c.kwargs.get("batch") or (c.args[1] if len(c.args) > 1 else [])
        all_batches.extend(batch)
    mmsis = {r["mmsi"] for r in all_batches}
    assert mmsis == {"123456789", "999999999"}


def test_load_vessels_batches_large_set(tmp_db):
    rows = [(str(i).zfill(9), "", f"SHIP {i}") for i in range(BATCH_SIZE + 10)]
    _seed_vessel_meta(tmp_db, rows)
    driver, session = _make_driver()
    load_vessels_from_duckdb(tmp_db, driver)
    # Should have been called at least twice (two batches)
    assert session.run.call_count >= 2


# ---------------------------------------------------------------------------
# load_sanctions_graph
# ---------------------------------------------------------------------------

def test_load_sanctions_graph_empty(tmp_db):
    driver, session = _make_driver()
    counts = load_sanctions_graph(tmp_db, driver)
    assert counts["companies"] == 0
    assert counts["vessel_sanctions"] == 0
    assert counts["company_sanctions"] == 0


def test_load_sanctions_graph_with_data(tmp_db):
    _seed_sanctions(tmp_db, [
        ("co-001", "EVIL CORP", None, None, "KP", "Company", "ofac_sdn"),
        ("v-001", "SHADOW SHIP", "123456789", "IMO001", "KP", "Vessel", "ofac_sdn"),
    ])
    driver, session = _make_driver()
    counts = load_sanctions_graph(tmp_db, driver)
    assert counts["companies"] == 1
    assert counts["vessel_sanctions"] == 1
    assert counts["company_sanctions"] == 1
    assert session.run.call_count > 0


# ---------------------------------------------------------------------------
# load_equasis_csv
# ---------------------------------------------------------------------------

def _write_equasis_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "mmsi", "imo", "vessel_name",
        "owner_id", "owner_name", "owner_country", "owner_address_id", "owner_address",
        "manager_id", "manager_name", "manager_country",
        "since", "until",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def test_load_equasis_csv_ownership(tmp_path):
    csv_path = tmp_path / "equasis.csv"
    _write_equasis_csv(csv_path, [{
        "mmsi": "123456789", "imo": "IMO001", "vessel_name": "SHIP A",
        "owner_id": "co-001", "owner_name": "ACME LTD", "owner_country": "PA",
        "owner_address_id": "addr-001", "owner_address": "PO Box 1, Panama",
        "manager_id": "mgr-001", "manager_name": "MGMT CO", "manager_country": "SG",
        "since": "2022-01-01", "until": "",
    }])
    driver, session = _make_driver()
    counts = load_equasis_csv(str(csv_path), driver)
    assert counts["ownership"] == 1
    assert counts["management"] == 1
    assert counts["addresses"] == 1


def test_load_equasis_csv_skips_missing_mmsi(tmp_path):
    csv_path = tmp_path / "equasis.csv"
    _write_equasis_csv(csv_path, [
        {"mmsi": "", "owner_id": "co-001"},
        {"mmsi": "123456789", "owner_id": "co-002", "owner_name": "X"},
    ])
    driver, session = _make_driver()
    counts = load_equasis_csv(str(csv_path), driver)
    assert counts["ownership"] == 1  # only the row with a valid mmsi


def test_load_equasis_csv_no_address_if_id_missing(tmp_path):
    csv_path = tmp_path / "equasis.csv"
    _write_equasis_csv(csv_path, [{
        "mmsi": "123456789", "owner_id": "co-001", "owner_name": "X",
        "owner_address_id": "",  # no address id → no address node
        "owner_address": "Some street",
    }])
    driver, session = _make_driver()
    counts = load_equasis_csv(str(csv_path), driver)
    assert counts["addresses"] == 0
