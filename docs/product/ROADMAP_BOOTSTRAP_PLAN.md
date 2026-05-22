# Premura Roadmap Bootstrap Plan

> Status: review draft. Proposed application of the planning-system plan to Premura's current docs. No GitHub issues, labels, milestones, boards, specs, or doc edits have been created by this draft.

## Purpose

Turn the approved planning system into an initial concrete roadmap for Premura.

This file answers:

- what roadmap items already exist in the docs
- which ones should become missions vs tasks under the current partition rule
- what milestone shape makes sense for the next pass
- what I would create first once the user approves execution

## Inputs Used

- `docs/operations/STATUS.md`
- `docs/product/ROADMAP.md`
- `docs/product/RISK_OPPORTUNITY.md`
- `docs/research/PROPOSAL_LABS.md`
- `docs/architecture/STAGES.md`
- `docs/architecture/UPDATE_STRATEGY.md`
- `docs/product/USERJOURNEY.md`
- `docs/agents/issue-tracker.md`
- `docs/agents/triage-labels.md`
- `/tmp/premura-planning-handoff-2026-05-22.md`

## Working Assumptions

- The planning-system handoff is accepted in substance and is the process to apply.
- This pass instantiates the roadmap; it does not execute it.
- The current doc set is slightly ahead of `ROADMAP.md` in a few places, so the first roadmap pass should trust shipped-state docs over stale roadmap prose.

## What I Would Do First

1. Reconcile `docs/product/ROADMAP.md` against `docs/operations/STATUS.md` so already-shipped items stop looking open.
2. Convert the remaining open work in the docs into one initial roadmap backlog with explicit `mission` or `task` classification.
3. Create the canonical label vocabulary first: the 5 bare triage labels plus the agreed prefix families.
4. Create three initial milestone buckets from the docs' natural sequencing: `v1.1 closeout`, `v2.0 analytical surface`, `v2.1 labs`.
5. Create one GitHub roadmap issue per mission and one GitHub issue per task.
6. Do not design the full Projects v2 board taxonomy yet; per the planning-system plan, board fields and views should be designed after `M1` completes.
7. Start with the `mcp-server-duckdb + age` spike mission, because the docs already identify it as the highest-leverage uncertainty.

## Proposed Milestones

### `v1.1 closeout`

Purpose: close the remaining small shipped-surface residue from v1 and clean up roadmap/doc drift.

Candidate contents:

- Real Sleep as Android ingest on the next live monthly cadence
- Project wiki hub page
- Roadmap/doc reconciliation pass so `ROADMAP.md` matches `STATUS.md`

### `v2.0 analytical surface`

Purpose: answer the storage/MCP boundary question, then build the first real Stage 3 analytical surface.

Candidate contents:

- `mcp-server-duckdb + age` compatibility spike
- First MCP analytical server mission
- Any ADR needed to lock the encrypted-DuckDB access boundary

### `v2.1 labs`

Purpose: add clinical labs as the first new source class and the first substantive Stage 2 engine use.

Candidate contents:

- Docling spike on representative lab PDFs
- Lab PDF parser
- `dim_metric` additions for labs
- Validity-window and missing-data policy seeding for sparse lab metrics
- First derived lab signals
- Optional later Stage 3 exposure of those signals

## Initial Backlog Proposal

### Missions

#### M1. Spike encrypted DuckDB access for MCP

- Milestone: `v2.0 analytical surface`
- Source docs: `docs/product/RISK_OPPORTUNITY.md`, `docs/product/ROADMAP.md`
- Why this is a mission:
  - likely new Stage 2/3 boundary decision
  - likely ADR before follow-on analytical work
  - non-obvious acceptance criteria
  - likely more than one PR if the result is "adopt", "adapt", or "reject and replace"
- Suggested roadmap issue title:
  - `Spike MCP access to age-protected DuckDB and lock the boundary`
- Expected outputs:
  - explicit decision on how MCP reads warehouse data
  - ADR capturing the Stage 2/3 boundary decision, unless the spike proves the existing boundary is already sufficient with no architectural change
  - follow-on recommendation for M2 and Stage-3 sub-work in M3

#### M2. Build the first MCP analytical server

- Milestone: `v2.0 analytical surface`
- Source docs: `docs/product/ROADMAP.md`, `docs/architecture/STAGES.md`
- Why this is a mission:
  - introduces new public MCP tools
  - touches more than one stage
  - needs design discussion and acceptance criteria
- Suggested roadmap issue title:
  - `Build the first MCP analytical surface over the warehouse`
- Proposed scope for the first mission pass:
  - `query_warehouse`
  - `list_metrics`
  - `metric_summary`
  - this first mission pass stops at the warehouse-query surface, matching the build order in `docs/product/ROADMAP.md`
- Explicitly deferred from this first mission pass:
  - deterministic stats tools
  - PubMed integration
- Dependency:
  - depends on M1's boundary decision

#### M3. Add clinical lab ingestion and sparse-signal rules

- Milestone: `v2.1 labs`
- Source docs: `docs/research/PROPOSAL_LABS.md`, `docs/architecture/STAGES.md`
- Why this is a mission:
  - new source class
  - additive ontology growth plus Stage 2 signal rules
  - touches more than one stage even if Stage 3 is deferred
  - needs design discussion and non-obvious acceptance criteria
- Suggested roadmap issue title:
  - `Add lab PDF ingest and sparse-signal foundations`
- Proposed mission slices:
  - sub-issue: run the docling spike and choose extraction path
  - sub-issue: add lab parser and ontology rows
  - sub-issue: seed validity windows and missing-data policies
  - sub-issue: add first derived lab ratios
  - sub-issue: later MCP exposure, only after M1/M2 resolve the Stage-3 boundary
- Dependency notes:
  - Stage 1 plus Stage 2 work can proceed without M1
  - Stage 3 exposure depends on the M1 decision and likely M2 infrastructure
  - first mission scope should exclude Stage 3 MCP exposure entirely

### Tasks

#### T1. Reconcile `ROADMAP.md` with shipped state

- Milestone: `v1.1 closeout`
- Source docs: `docs/product/ROADMAP.md`, `docs/operations/STATUS.md`
- Why this is a task:
  - single doc-focused cleanup
  - no new public contract
  - can land in one PR
- Suggested issue title:
  - `Prune shipped items from ROADMAP and align it with STATUS`

#### T2. Run the first real Sleep as Android monthly ingest and capture parser fixups

- Milestone: `v1.1 closeout`
- Source docs: `docs/product/ROADMAP.md`, `docs/operations/STATUS.md`
- Why this is a task:
  - a concrete validation pass, likely one issue and one PR unless a larger parser redesign emerges
- Suggested issue title:
  - `Validate Sleep as Android parser on the first live monthly export`
- Note:
  - if real-data quirks force a retroactive reinterpretation of already-mapped fields, this escalates to a mission under update kind `(f)`

#### T3. Create the project wiki hub page

- Milestone: `v1.1 closeout`
- Source docs: `docs/product/ROADMAP.md`, `docs/product/USERJOURNEY.md`, `docs/product/SPEC.md`
- Why this is a task:
  - single output, no repo contract change
- Suggested issue title:
  - `Create the Premura project wiki hub page`

## Items I Would Not Pull Into The First Roadmap Pass

These appear in `ROADMAP.md`, but I would not front-load them before M1 to M3 and the v1.1 residue:

- `hpipe inspect <file>`
- `hpipe gc` extension for `data/raw/`
- `hp.fact_interval.unit` migration
- daily Health Connect pickup
- cross-source priority reconsideration
- backfill historical Garmin dumps
- FIT-file decoding
- sample-level Garmin HRV/respiration expansion

Reason: they are real work, but none outrank the open boundary question in `RISK_OPPORTUNITY.md` or the concrete next-source proposal in `PROPOSAL_LABS.md`.

## Important Consequence Of The Current Partition Rule

Under the current rule, some items that feel "small" in `ROADMAP.md` still become missions.

Examples:

- `hpipe inspect <file>` introduces a new CLI verb, so it qualifies as a mission.
- a schema-affecting warehouse change like `hp.fact_interval.unit` also leans mission-shaped.

That is not a problem by itself, but it is stricter than the prose tone in `ROADMAP.md`. Once the planning system is in use, the roadmap should be rewritten in terms of the stricter classification rather than the earlier informal size language.

## Proposed Roadmap Ordering

This is a low-ceremony default sequence, not a hard dependency chain. If capacity allows, `M3` Stage 1 plus Stage 2 can run in parallel with `M2`; only `M3` Stage 3 depends on the `M1` boundary decision and `M2` infrastructure.

1. T1 `Prune shipped items from ROADMAP and align it with STATUS`
2. T2 `Validate Sleep as Android parser on the first live monthly export`
3. T3 `Create the Premura project wiki hub page`
4. M1 `Spike MCP access to age-protected DuckDB and lock the boundary`
5. M2 `Build the first MCP analytical surface over the warehouse`
6. M3 `Add lab PDF ingest and sparse-signal foundations`

This order keeps v1 residue small, answers the major architectural uncertainty early, and delays the bigger source-class expansion until the Stage-3 boundary is no longer ambiguous.

## What I Would Create If Execution Were Approved

### Labels

- bare triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`
- prefix families: `type:*`, `stage:*`, `pillar:*`, `priority:*`

### Milestones

- `v1.1 closeout`
- `v2.0 analytical surface`
- `v2.1 labs`

### First Mission Issues

- `Spike MCP access to age-protected DuckDB and lock the boundary`
- `Build the first MCP analytical surface over the warehouse`
- `Add lab PDF ingest and sparse-signal foundations`

### First Task Issues

- `Prune shipped items from ROADMAP and align it with STATUS`
- `Validate Sleep as Android parser on the first live monthly export`
- `Create the Premura project wiki hub page`

## Review Questions

Before executing this roadmap bootstrap, I would want review on:

- whether `v1.1 closeout` should contain the roadmap/doc reconciliation item or keep it outside release milestones

## Recommendation

If the goal is to make the roadmap real with the least ceremony, approve this bootstrap shape and then perform exactly one application pass:

1. reconcile the prose roadmap against shipped state
2. create the three milestones
3. open the three mission issues and four task issues above
4. start M1 first
