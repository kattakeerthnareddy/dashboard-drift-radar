"""The common currency: column references extracted from BI artifacts.

Every extractor (Tableau, Power BI) reduces its format to a set of
ColumnRef(table, column) per dashboard, all lowercase, so the differ never
cares where a reference came from. Case is folded because warehouses fold
identifier case differently than BI tools record it; that single decision
is load-bearing (see the war story).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnRef:
    table: str
    column: str

    @staticmethod
    def make(table: str, column: str) -> "ColumnRef":
        return ColumnRef(table.strip().lower(), column.strip().lower())


@dataclass
class DashboardRefs:
    name: str
    source_file: str
    kind: str  # "tableau" or "powerbi"
    refs: set[ColumnRef]
