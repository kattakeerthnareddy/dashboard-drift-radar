"""Power BI model reference extraction (model.bim / TMSL JSON).

A dataset's model.bim lists tables with columns, plus measures whose DAX
expressions reference columns as Table[Column] or 'Table Name'[Column].
Physical columns come straight from the tables array; measure references
are additionally scanned so a measure over a dropped column flags even if
the column was removed from the visible table list.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .log import ctx, get_logger
from .refs import ColumnRef, DashboardRefs

logger = get_logger("ddr.powerbi")

# Table[Column] or 'Table with spaces'[Column]
_DAX_REF = re.compile(r"(?:'([^']+)'|(\b[A-Za-z_][\w ]*?))\[([^\[\]]+)\]")


class BimParseError(ValueError):
    pass


def extract(path: str | Path) -> DashboardRefs:
    p = Path(path)
    try:
        model = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise BimParseError(f"{p.name}: not valid JSON: {exc}") from exc

    tables = (model.get("model") or {}).get("tables") or model.get("tables")
    if tables is None:
        raise BimParseError(f"{p.name}: no tables array; is this a model.bim?")

    refs: set[ColumnRef] = set()
    for t in tables:
        tname = t.get("name", "")
        source = t.get("source") or tname  # partition source table if present
        for col in t.get("columns", []) or []:
            src_col = col.get("sourceColumn") or col.get("name")
            if tname and src_col:
                refs.add(ColumnRef.make(source, src_col))
        for measure in t.get("measures", []) or []:
            expr = measure.get("expression", "") or ""
            if isinstance(expr, list):
                expr = "\n".join(expr)
            for m in _DAX_REF.finditer(expr):
                table = m.group(1) or m.group(2) or ""
                refs.add(ColumnRef.make(table, m.group(3)))

    name = model.get("name") or p.stem
    result = DashboardRefs(name=name, source_file=str(p), kind="powerbi", refs=refs)
    logger.info("parsed model", extra=ctx(file=p.name, refs=len(refs)))
    return result
