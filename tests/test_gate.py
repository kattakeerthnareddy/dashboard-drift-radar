import json

import pytest
from typer.testing import CliRunner

from ddr.cli import app
from ddr.differ import check
from ddr.refs import ColumnRef, DashboardRefs
from ddr.warehouse import SchemaLoadError, from_json
from ddr.simulator import schema_rows, write_demo

runner = CliRunner()
CR = ColumnRef.make


def dash(name, refs, kind="tableau"):
    return DashboardRefs(name=name, source_file=f"{name}.twb", kind=kind,
                         refs={CR(t, c) for t, c in refs})


SCHEMA = {CR("fct_sales", "revenue"): "decimal(12,2)",
          CR("fct_sales", "quantity"): "integer",
          CR("dim_customers", "region"): "varchar"}


def test_clean_dashboard_passes():
    r = check([dash("ok", [("fct_sales", "revenue")])], SCHEMA)
    assert not r.breaking and r.dashboards_broken == 0


def test_missing_column_and_table():
    r = check([dash("d", [("fct_sales", "discount"), ("dim_dates", "day")])], SCHEMA)
    kinds = {f.kind for f in r.findings}
    assert kinds == {"missing-column", "missing-table"}
    assert r.breaking and r.dashboards_broken == 1


def test_rename_hint_only_in_migration_mode():
    old = dict(SCHEMA)
    new = dict(SCHEMA)
    del new[CR("dim_customers", "region")]
    new[CR("dim_customers", "customer_region")] = "varchar"
    d = [dash("d", [("dim_customers", "region")])]
    plain = check(d, new)
    assert {f.kind for f in plain.findings} == {"missing-column"}
    migration = check(d, new, old)
    assert "probable-rename" in {f.kind for f in migration.findings}
    hint = next(f for f in migration.findings if f.kind == "probable-rename")
    assert "customer_region" in hint.detail


def test_type_family_change_breaks_but_widening_does_not():
    old = {CR("t", "a"): "integer", CR("t", "b"): "integer"}
    new = {CR("t", "a"): "varchar", CR("t", "b"): "bigint"}
    r = check([dash("d", [("t", "a"), ("t", "b")])], new, old)
    typed = [f for f in r.findings if f.kind == "type-changed"]
    assert len(typed) == 1 and typed[0].column == "a"


def test_schema_snapshot_validation(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps([{"table": "t"}]))
    with pytest.raises(SchemaLoadError, match="need table/column/type"):
        from_json(p)
    p.write_text("[]")
    with pytest.raises(SchemaLoadError, match="empty"):
        from_json(p)


def test_cli_end_to_end_block_and_safe(tmp_path):
    write_demo(tmp_path)
    r = runner.invoke(app, ["gate", "--dashboards", str(tmp_path / "dashboards"),
                            "--schema", str(tmp_path / "schema_current.json")])
    assert r.exit_code == 0 and "SAFE" in r.output
    out = tmp_path / "report.json"
    r = runner.invoke(app, [
        "gate", "--dashboards", str(tmp_path / "dashboards"),
        "--schema", str(tmp_path / "schema_migrated.json"),
        "--before", str(tmp_path / "schema_current.json"),
        "--json-out", str(out),
    ])
    assert r.exit_code == 1 and "BLOCK MIGRATION" in r.output
    payload = json.loads(out.read_text())
    assert payload["breaking"] and payload["dashboards_broken"] == 4
    kinds = {f["kind"] for f in payload["findings"]}
    assert {"missing-column", "type-changed", "probable-rename"} <= kinds


def test_cli_empty_dashboard_dir_exits_three(tmp_path):
    (tmp_path / "empty").mkdir()
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps(schema_rows()))
    r = runner.invoke(app, ["gate", "--dashboards", str(tmp_path / "empty"),
                            "--schema", str(schema)])
    assert r.exit_code == 3


def test_duckdb_schema_source(tmp_path):
    import duckdb

    db = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE fct_sales (revenue DECIMAL(12,2), quantity INTEGER)")
    con.close()
    from ddr.warehouse import load

    schema = load(db)
    assert CR("fct_sales", "revenue") in schema
    r = check([dash("d", [("fct_sales", "revenue")])], schema)
    assert not r.breaking
