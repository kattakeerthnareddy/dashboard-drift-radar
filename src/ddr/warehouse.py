"""Warehouse schema snapshots: from a live DuckDB file or a JSON export.

The JSON snapshot format is one query away on any warehouse:

    SELECT table_name, column_name, data_type
    FROM information_schema.columns WHERE table_schema = 'ANALYTICS'

exported as [{"table": ..., "column": ..., "type": ...}, ...]. Two
snapshots (current and post-migration) are what the gate diffs, so the
check runs BEFORE the migration is applied anywhere real.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from .refs import ColumnRef


class SchemaLoadError(ValueError):
    pass


def from_duckdb(db_path: str | Path) -> dict[ColumnRef, str]:
    p = Path(db_path)
    if not p.exists():
        raise SchemaLoadError(f"database not found: {p}")
    con = duckdb.connect(str(p), read_only=True)
    rows = con.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns"
        " WHERE table_schema = 'main'"
    ).fetchall()
    con.close()
    return {ColumnRef.make(t, c): str(ty).lower() for t, c, ty in rows}


def from_json(path: str | Path) -> dict[ColumnRef, str]:
    p = Path(path)
    if not p.exists():
        raise SchemaLoadError(f"schema snapshot not found: {p}")
    try:
        rows = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise SchemaLoadError(f"{p.name}: not valid JSON: {exc}") from exc
    out: dict[ColumnRef, str] = {}
    for row in rows:
        if not {"table", "column", "type"} <= set(row):
            raise SchemaLoadError(f"snapshot rows need table/column/type: {row}")
        out[ColumnRef.make(row["table"], row["column"])] = str(row["type"]).lower()
    if not out:
        raise SchemaLoadError(f"{p.name}: empty schema snapshot")
    return out


def load(path: str | Path) -> dict[ColumnRef, str]:
    p = Path(path)
    if p.suffix.lower() == ".json":
        return from_json(p)
    if p.suffix.lower() in (".duckdb", ".db"):
        return from_duckdb(p)
    raise SchemaLoadError(f"unsupported schema source: {p.suffix} (use .json or .duckdb)")
