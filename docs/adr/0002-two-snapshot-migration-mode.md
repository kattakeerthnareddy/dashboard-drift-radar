# ADR-0002: Two-snapshot migration mode over live-schema-only checks

## Status

Accepted

## Context

The simplest check compares dashboards against one schema: whatever is
missing is broken. But the high-value moment is *before* a migration
applies, and a single post-state cannot distinguish "column never existed"
from "this PR removes it", nor detect breaking type changes at all
(the column still exists, its type just changed), nor suggest renames.

## Options considered

Live schema only: simple, catches drift after the fact, which is exactly
when it is too late; the exec dashboard is already blank. Parsing the
migration SQL: fragile across dialects and tools (dbt, Flyway, raw DDL).
Two snapshots (current and post-migration), each one information_schema
query: tool-agnostic, and the diff between them is precisely the PR's
blast surface.

## Decision

Support both. Single-snapshot mode answers "are my dashboards consistent
with production right now" (drift detection). Two-snapshot mode is the
migration gate: it adds type-family change detection (numeric to text
breaks aggregations; int to bigint widening does not) and
probable-rename hints via containment-aware name similarity, so the
finding arrives with its likely fix attached.

## Consequences

- Producing the post-migration snapshot requires applying the migration
  somewhere disposable (a CI database or schema clone), which good
  migration pipelines already do.
- The rename heuristic is a hint, never an auto-fix; it names the
  candidate and the artifact to update.
- Type-family rules are conservative by design; precision-only changes
  do not block, and the family table is 10 lines of code to extend.
