"""Gate cost at fleet scale: parsing and diffing hundreds of dashboards.

A migration gate runs in CI on every schema PR; this measures whether it
stays fast when the BI estate is a real fleet rather than four demo files.

Run: python benchmark/run_benchmark.py
Raw output: benchmark/results/benchmark_results.json
"""

from __future__ import annotations

import json
import platform
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ddr.cli import _collect  # noqa: E402
from ddr.differ import check  # noqa: E402
from ddr.refs import ColumnRef  # noqa: E402
from ddr.simulator import TABLES, make_bim, make_twb, schema_rows  # noqa: E402

RESULTS_DIR = Path(__file__).parent / "results"


def build_fleet(outdir: Path, n_dashboards: int) -> None:
    tables = list(TABLES)
    for i in range(n_dashboards):
        table = tables[i % len(tables)]
        cols = [c for c, _ in TABLES[table]]
        if i % 10 == 0:
            (outdir / f"model_{i}.bim").write_text(make_bim(f"model_{i}"))
        else:
            (outdir / f"wb_{i}.twb").write_text(make_twb(f"wb_{i}", table, cols))


def run_scale(n: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        build_fleet(out, n)
        t0 = time.perf_counter()
        dashboards = _collect(out)
        parse_s = time.perf_counter() - t0

        new = {ColumnRef.make(r["table"], r["column"]): r["type"]
               for r in schema_rows(migrated=True)}
        old = {ColumnRef.make(r["table"], r["column"]): r["type"]
               for r in schema_rows(migrated=False)}
        t0 = time.perf_counter()
        report = check(dashboards, new, old)
        diff_s = time.perf_counter() - t0
        return {
            "dashboards": n,
            "parse_s": round(parse_s, 3),
            "diff_s": round(diff_s, 3),
            "total_s": round(parse_s + diff_s, 3),
            "broken_found": report.dashboards_broken,
        }


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    report = {
        "host": {"python": platform.python_version(),
                 "cpus": __import__("os").cpu_count()},
        "scales": [run_scale(n) for n in (50, 200, 1000)],
    }
    (RESULTS_DIR / "benchmark_results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
