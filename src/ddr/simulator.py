"""Demo asset generator: a warehouse schema, Tableau workbooks, and a Power
BI model that reference it, plus a 'migration' that breaks some of them.

Everything the README claims is reproducible from these assets; they also
serve as parser fixtures, so the extractors are tested against the same
shapes they will meet in real exports.
"""

from __future__ import annotations

import json
from pathlib import Path

TABLES = {
    "fct_sales": [("sale_id", "bigint"), ("customer_id", "bigint"),
                  ("product_id", "bigint"), ("sale_date", "date"),
                  ("quantity", "integer"), ("revenue", "decimal(12,2)")],
    "dim_customers": [("customer_id", "bigint"), ("name", "varchar"),
                      ("region", "varchar"), ("segment", "varchar")],
    "dim_products": [("product_id", "bigint"), ("product_name", "varchar"),
                     ("category", "varchar"), ("unit_price", "decimal(9,2)")],
}

# The migration under review: rename one column, drop one, retype one.
MIGRATED_CHANGES = {
    "rename": ("dim_customers", "segment", "customer_segment"),
    "drop": ("fct_sales", "quantity"),
    "retype": ("dim_products", "unit_price", "varchar"),
}


def schema_rows(migrated: bool = False) -> list[dict]:
    rows = []
    for table, cols in TABLES.items():
        for col, typ in cols:
            if migrated:
                if (table, col) == MIGRATED_CHANGES["drop"][:2]:
                    continue
                if (table, col) == MIGRATED_CHANGES["rename"][:2]:
                    col = MIGRATED_CHANGES["rename"][2]
                if (table, col) == MIGRATED_CHANGES["retype"][:2]:
                    typ = MIGRATED_CHANGES["retype"][2]
            rows.append({"table": table, "column": col, "type": typ})
    return rows


TWB_TEMPLATE = """<?xml version='1.0' encoding='utf-8' ?>
<workbook name="{name}" version="18.1">
  <datasources>
    <datasource name="warehouse">
      <connection class="snowflake" dbname="ANALYTICS"/>
      <relation name="{table}" table="[main].[{table}]" type="table"/>
      {maps}
    </datasource>
  </datasources>
</workbook>
"""


def make_twb(name: str, table: str, columns: list[str]) -> str:
    maps = "\n      ".join(
        f'<map key="[{c}]" value="[{table}].[{c}]"/>' for c in columns
    )
    return TWB_TEMPLATE.format(name=name, table=table, maps=maps)


def make_bim(name: str = "revenue_model") -> str:
    model = {
        "name": name,
        "model": {
            "tables": [
                {
                    "name": "Sales", "source": "fct_sales",
                    "columns": [
                        {"name": "Revenue", "sourceColumn": "revenue"},
                        {"name": "Quantity", "sourceColumn": "quantity"},
                        {"name": "SaleDate", "sourceColumn": "sale_date"},
                    ],
                    "measures": [
                        {"name": "Total Revenue",
                         "expression": "SUM(fct_sales[revenue])"},
                        {"name": "Units",
                         "expression": "SUMX(fct_sales, fct_sales[quantity])"},
                    ],
                },
                {
                    "name": "Customers", "source": "dim_customers",
                    "columns": [
                        {"name": "Region", "sourceColumn": "region"},
                        {"name": "Segment", "sourceColumn": "segment"},
                    ],
                    "measures": [],
                },
            ]
        },
    }
    return json.dumps(model, indent=2)


def write_demo(outdir: str | Path) -> dict[str, int]:
    out = Path(outdir)
    (out / "dashboards").mkdir(parents=True, exist_ok=True)
    (out / "dashboards" / "exec_revenue.twb").write_text(
        make_twb("exec_revenue", "fct_sales", ["revenue", "sale_date", "quantity"]))
    (out / "dashboards" / "customer_mix.twb").write_text(
        make_twb("customer_mix", "dim_customers", ["region", "segment", "name"]))
    (out / "dashboards" / "catalog_health.twb").write_text(
        make_twb("catalog_health", "dim_products",
                 ["category", "unit_price", "product_name"]))
    (out / "dashboards" / "revenue_model.bim").write_text(make_bim())
    (out / "schema_current.json").write_text(json.dumps(schema_rows(False), indent=2))
    (out / "schema_migrated.json").write_text(json.dumps(schema_rows(True), indent=2))
    return {"dashboards": 4, "schemas": 2}
