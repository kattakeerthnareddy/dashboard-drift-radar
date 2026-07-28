"""The gate: dashboard references vs a schema (or a schema migration).

Finding kinds, per dashboard:
- missing-table: every referenced column of a table is gone (or the table
  never existed): the tile will not render at all.
- missing-column: the column is gone but its table survives: specific
  visuals and filters break.
- type-changed: only reported when diffing two schema snapshots; numeric
  to varchar breaks aggregations even though the column "exists".
- probable-rename: a missing column whose table gained a new column with
  high name similarity; reported as the likely fix.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from .refs import ColumnRef, DashboardRefs


@dataclass
class Finding:
    dashboard: str
    kind: str
    table: str
    column: str | None
    detail: str


@dataclass
class GateReport:
    findings: list[Finding] = field(default_factory=list)
    dashboards_checked: int = 0
    dashboards_broken: int = 0

    @property
    def breaking(self) -> bool:
        return any(f.kind in ("missing-table", "missing-column", "type-changed")
                   for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dashboards_checked": self.dashboards_checked,
            "dashboards_broken": self.dashboards_broken,
            "breaking": self.breaking,
            "findings": [f.__dict__ for f in self.findings],
        }


def _rename_candidates(
    missing: ColumnRef, new_schema: dict[ColumnRef, str], old_schema: dict[ColumnRef, str]
) -> str | None:
    added = [r for r in new_schema if r.table == missing.table and r not in old_schema]
    best, best_score = None, 0.0
    for cand in added:
        score = SequenceMatcher(None, missing.column, cand.column).ratio()
        if score > best_score:
            best, best_score = cand, score
    if best is not None and best_score >= 0.6:
        return best.column
    return None


def check(
    dashboards: list[DashboardRefs],
    new_schema: dict[ColumnRef, str],
    old_schema: dict[ColumnRef, str] | None = None,
) -> GateReport:
    """Diff dashboards against new_schema. When old_schema is given, also
    report type changes and probable renames (migration mode)."""
    report = GateReport(dashboards_checked=len(dashboards))
    new_tables = {r.table for r in new_schema}
    for dash in dashboards:
        broke = False
        by_table: dict[str, list[ColumnRef]] = {}
        for ref in sorted(dash.refs, key=lambda r: (r.table, r.column)):
            by_table.setdefault(ref.table, []).append(ref)
        for table, refs in by_table.items():
            if table not in new_tables:
                report.findings.append(Finding(
                    dash.name, "missing-table", table, None,
                    f"{len(refs)} referenced columns unreachable"))
                broke = True
                continue
            for ref in refs:
                if ref not in new_schema:
                    rename = (_rename_candidates(ref, new_schema, old_schema)
                              if old_schema else None)
                    if rename:
                        report.findings.append(Finding(
                            dash.name, "probable-rename", ref.table, ref.column,
                            f"likely renamed to {rename!r}; update the {dash.kind} source"))
                    report.findings.append(Finding(
                        dash.name, "missing-column", ref.table, ref.column,
                        "referenced column absent from target schema"))
                    broke = True
                elif old_schema and ref in old_schema:
                    old_t, new_t = old_schema[ref], new_schema[ref]
                    if old_t != new_t and _breaking_type_change(old_t, new_t):
                        report.findings.append(Finding(
                            dash.name, "type-changed", ref.table, ref.column,
                            f"{old_t} -> {new_t}"))
                        broke = True
        if broke:
            report.dashboards_broken += 1
    return report


_NUMERIC = ("int", "bigint", "decimal", "double", "float", "numeric", "hugeint")


def _breaking_type_change(old: str, new: str) -> bool:
    """Numeric->text and date->text break aggregations and date filters.
    Widening within a family (int -> bigint, decimal precision) does not."""
    def family(t: str) -> str:
        t = t.lower()
        if any(n in t for n in _NUMERIC):
            return "numeric"
        if "date" in t or "time" in t:
            return "temporal"
        return "text"

    return family(old) != family(new)
