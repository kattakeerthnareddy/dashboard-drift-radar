# ADR-0001: Static artifact parsing over BI-server APIs

## Status

Accepted

## Context

Dashboard column usage can come from two places: the BI server's metadata
APIs (Tableau Metadata API, Power BI scanner APIs) or the artifact files
themselves (.twb XML, model.bim JSON), which live in version control at
any shop practicing BI-as-code.

## Options considered

Server APIs give richer lineage but demand credentials, a running server,
API rate budgets, and network access from CI, and they describe what is
*deployed*, not what is *about to be merged*. Artifact parsing needs no
credentials, runs on the PR's own files, and gates the change before
anything ships. The trade-off is fidelity: a .twb parse sees what the
file declares, not runtime behavior like custom SQL assembled at load.

## Decision

Parse the artifacts. The gate's job is a CI decision on a schema PR, and
the artifacts checked into the same forge are the ground truth for that
decision. Custom SQL blocks are the known fidelity gap and are named in
the README's failure modes rather than papered over.

## Consequences

- The gate is credential-free and runs anywhere, including this repo's CI.
- Shops that do not version their workbooks must export them first, which
  is a practice worth forcing anyway.
- Server-API enrichment (usage counts, owners for notifications) is an
  additive future layer, not a rewrite.
