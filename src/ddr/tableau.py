"""Tableau workbook (.twb) reference extraction.

A .twb is XML. Physical columns live in datasource relations
(<relation table="[schema].[table]">) and column mappings
(<map key="[column]" value="[table].[column]"/>); worksheet usage appears
as <column ... name="[column]"/> under datasource-dependencies. We extract
the physical (table, column) pairs a workbook can touch: for a
migration gate, "the workbook references it anywhere" is the safe
definition of usage, because a column referenced only by a hidden
calculation still breaks the extract refresh.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .log import ctx, get_logger
from .refs import ColumnRef, DashboardRefs

logger = get_logger("ddr.tableau")

_BRACKETS = re.compile(r"^\[|\]$")


def _unbracket(s: str) -> str:
    return _BRACKETS.sub("", s or "")


class TwbParseError(ValueError):
    pass


def extract(path: str | Path) -> DashboardRefs:
    p = Path(path)
    try:
        tree = ET.parse(p)
    except ET.ParseError as exc:
        raise TwbParseError(f"{p.name}: not valid XML: {exc}") from exc
    root = tree.getroot()
    refs: set[ColumnRef] = set()

    # relation elements name physical tables; their column maps bind columns
    for ds in root.iter("datasource"):
        table_by_alias: dict[str, str] = {}
        for rel in ds.iter("relation"):
            table = _unbracket(rel.get("table", ""))
            alias = rel.get("name", table)
            if table:
                # "[main].[fct_sales]" -> fct_sales (schema prefix dropped:
                # the differ works on table names within one target schema)
                table_name = table.split("].[")[-1]
                table_by_alias[alias] = _unbracket(table_name)
        for m in ds.iter("map"):
            value = m.get("value", "")  # "[fct_sales].[revenue]"
            parts = [_unbracket(x) for x in value.split("].[")]
            if len(parts) == 2:
                alias, column = parts
                table = table_by_alias.get(alias, alias)
                refs.add(ColumnRef.make(table, column))

    name = root.get("name") or p.stem
    result = DashboardRefs(name=name, source_file=str(p), kind="tableau", refs=refs)
    logger.info("parsed workbook", extra=ctx(file=p.name, refs=len(refs)))
    if not refs:
        logger.warning("workbook yielded zero references",
                       extra=ctx(file=p.name))
    return result
