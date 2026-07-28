"""Typer CLI: `ddr simulate` writes demo assets, `ddr gate` runs the check."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .differ import check
from .log import ctx, get_logger
from .powerbi import extract as extract_bim
from .simulator import write_demo
from .tableau import extract as extract_twb
from .warehouse import load

app = typer.Typer(add_completion=False,
                  help="Gate schema migrations on dashboard blast radius")
logger = get_logger("ddr.cli")


def _collect(dashboards_dir: Path):
    dashboards = []
    for p in sorted(dashboards_dir.rglob("*")):
        if p.suffix.lower() == ".twb":
            dashboards.append(extract_twb(p))
        elif p.suffix.lower() == ".bim":
            dashboards.append(extract_bim(p))
    return dashboards


@app.command()
def simulate(outdir: Path = typer.Option(Path("data/generated"))) -> None:
    """Write demo dashboards plus current and migrated schema snapshots."""
    counts = write_demo(outdir)
    typer.echo(f"wrote {counts['dashboards']} dashboards and 2 schema snapshots"
               f" to {outdir}")


@app.command()
def gate(
    dashboards: Path = typer.Option(..., help="Directory of .twb / .bim files"),
    schema: Path = typer.Option(..., help="Target schema (.json snapshot or .duckdb)"),
    before: Path = typer.Option(None, help="Pre-migration schema for rename/type hints"),
    json_out: Path = typer.Option(None),
) -> None:
    """Exit 1 if any dashboard breaks against the target schema."""
    try:
        dash_refs = _collect(dashboards)
        if not dash_refs:
            raise ValueError(f"no .twb or .bim files under {dashboards}")
        new_schema = load(schema)
        old_schema = load(before) if before else None
        report = check(dash_refs, new_schema, old_schema)
    except Exception as exc:
        logger.error("gate failed to run", extra=ctx(error=str(exc)))
        raise typer.Exit(code=3) from exc

    if json_out:
        json_out.write_text(json.dumps(report.to_dict(), indent=2))
    try:
        typer.echo(f"dashboards checked: {report.dashboards_checked}, "
                   f"broken: {report.dashboards_broken}")
        for f in report.findings:
            col = f".{f.column}" if f.column else ""
            typer.echo(f"  [{f.kind}] {f.dashboard}: {f.table}{col} ({f.detail})")
        typer.echo("Result: " + ("BLOCK MIGRATION" if report.breaking else "SAFE"))
    except BrokenPipeError:
        pass
    raise typer.Exit(code=1 if report.breaking else 0)


if __name__ == "__main__":
    app()
