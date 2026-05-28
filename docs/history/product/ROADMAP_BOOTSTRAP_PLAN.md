# Premura Initial Roadmap Plan

> Status: historical reference. This doc captured the first concrete roadmap pass. The minimal label set and GitHub tracking issues for M1-M3 now exist, and issues `#1`, `#2`, and `#3` are closed. GitHub milestones were **not** created from this plan, so the `v2.0` / `v2.1` milestone-and-tag workflow remains an intended convention rather than a completed historical fact.
>
> **Vocabulary note**: this doc uses the project vocabulary defined in `CONTEXT.md` §"Planning" (e.g. "ablation study" rather than "spike", "design decision note" rather than "ADR"). Live GitHub artifacts (issue titles, label values, file paths) keep their existing names — only prose follows the new vocabulary.
>
> **Naming note**: this doc is filed at `docs/history/product/ROADMAP_BOOTSTRAP_PLAN.md`. The word "bootstrap" collides with `ops/bootstrap.sh` (operational setup script). The doc's content avoids the word; a file rename is pending and will be a separate small commit.

## Purpose

Capture how the approved planning system was first turned into a concrete roadmap for Premura.

This is no longer the current next-action list. Use [FULL_APP_DEVELOPMENT_PLAN.md](FULL_APP_DEVELOPMENT_PLAN.md) for phase-level planning and GitHub issues for the active mission backlog.

This file answers:

- what roadmap items already exist in the docs
- which ones become missions under the mission/task split rule
- what milestone shape makes sense for the first pass
- what this first pass proposed creating, and what actually happened

## Inputs Used

- `CONTEXT.md` (vocabulary)
- `docs/operations/STATUS.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- `docs/product/ROADMAP.md`
- `docs/history/product/RISK_OPPORTUNITY.md`
- `docs/history/research/PROPOSAL_LABS.md`
- `docs/architecture/STAGES.md`
- `docs/architecture/UPDATE_STRATEGY.md`
- `docs/agents/issue-tracker.md`
- `docs/agents/triage-labels.md`
- `/tmp/premura-planning-handoff-2026-05-22.md`

## Working Assumptions

- The planning-system handoff was accepted in substance and used for the first application pass.
- This file now records that first pass after execution rather than serving as a pre-execution proposal.
- This plan is the near-term execution layer for Phases 1 and 2 in `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`, not a competing phase plan.
- `ROADMAP.md` has been reconciled against shipped state (commit `c11fc8c`), so this plan starts from remaining open work.
- The active backlog is **missions-only** — no tasks. SAA real-export validation and the wiki hub page are both deferred (wiki: "once we have a proper codebase"; SAA: file an issue if and when the next real export breaks something).

## What Was Done First

1. Create the minimal canonical label vocabulary: 5 bare `needs-triage`/etc. labels + `stage:*` (5) + `type:*` (6). This happened.
2. Create two milestones from the docs' natural sequencing: `v2.0 analytical surface`, `v2.1 labs`. This did **not** happen.
3. Create one GitHub tracking issue per mission (3 total), titled with `[M1]`/`[M2]`/`[M3]` prefixes. This happened; issues `#1`, `#2`, and `#3` were later closed.
4. Do not design the full Projects v2 board taxonomy yet — board fields and views are designed after M1 completes. This remains deferred.
5. Start with the `mcp+age` ablation study (M1), the highest-leverage open uncertainty per `docs/history/product/RISK_OPPORTUNITY.md:151`. This happened.

## Conventions

### Tag-cut on milestone close

When `v2.0 analytical surface` closes (M1 + M2 done), cut tag `v2.0.0`. When `v2.1 labs` closes (M3 done), cut `v2.1.0`. Tags are restore points: someone with the encrypted Drive snapshot + age key + a tag can reproduce the pipeline at a known state.

### Mission title format

`[M1] <descriptive title>`, `[M2] ...`, etc. Sorts cleanly in issue lists; grep-able in commits.

### Multi-stage labels

The planning-system handoff said "one stage per issue." Relax that: missions that genuinely span stages get multiple `stage:*` labels. M3 spans Stage 1 (parser) and Stage 2 (validity windows, missing-data policy, derived ratios), so it carries both `stage:ingest` and `stage:engine`.

### Mission breakdown

Each mission has **one** GitHub tracking issue. Intra-mission breakdown (e.g. M3's slices) lives inside `kitty-specs/<slug>/` as work packages when `/spec-kitty.specify` runs. Cross-mission dependencies (M2 blocked by M1, M3's Stage-3 sub-work blocked by M1 + M2) are encoded as "blocked by" comments on the tracking issues.

## Proposed Milestones

### `v2.0 analytical surface`

Purpose: settle how MCP reads the warehouse, then build the first real Stage 3 analytical surface.

Candidate contents:

- `mcp+age` compatibility ablation study (M1)
- First MCP analytical server (M2)
- Design decision note locking how MCP reads the warehouse (output of M1)

### `v2.1 labs`

Purpose: add clinical labs as the first new source class and the first substantive Stage 2 engine use.

Candidate contents (broken down inside `kitty-specs/<m3-slug>/` when M3 specifies):

- Docling ablation study on representative lab PDFs
- Lab PDF parser (in-tree under `src/premura/parsers/lab_pdf.py`)
- `dim_metric` additions for labs
- Validity-window and missing-data policy seeding for sparse lab metrics
- First derived lab signals

Not in this milestone:

- Stage 3 lab-signal exposure. That is later cross-mission follow-on work and depends on M1's design decision note plus M2's MCP infrastructure.

## Initial Backlog Proposal

### M1. Lock how MCP reads the warehouse

- **Milestone**: `v2.0 analytical surface`
- **Labels**: `stage:mcp`, `type:spike` (existing label name; the work itself is an ablation study)
- **Source docs**: `docs/history/product/RISK_OPPORTUNITY.md`, `docs/product/ROADMAP.md`
- **Outcome**: shipped and closed as issue `#1`; the result is design decision note `docs/adr/0002-mcp-local-warehouse-boundary.md`.
- **Tracking issue title**:
  - `[M1] Lock the MCP/warehouse boundary and keep age at export/upload` (existing GitHub title; preserved for traceability)
- **Definition of done (1-week time budget)**:
  - A design decision note is filed. It captures *one* of:
    - The recommended way MCP reads the warehouse, for M2, including where `age` applies and whether MCP can read the live warehouse directly.
    - Any rejected stricter alternatives, with the failure mode or tradeoff documented.
- **Follow-on output**:
  - Concrete recommendation for M2 (whether the existing MCP access path is sufficient or requires a wrapper).
  - Concrete recommendation for M3's later Stage-3 sub-work (whether the same access path applies to lab-derived signals).

### M2. Build the first MCP analytical server

- **Milestone**: `v2.0 analytical surface`
- **Labels**: `stage:mcp`, `type:feature`
- **Source docs**: `docs/product/ROADMAP.md`, `docs/architecture/STAGES.md`
- **Outcome**: issue `#2` is closed, and the scope was later extended by a follow-on grounded-signals mission beyond the original raw-tool-only slice.
- **Tracking issue title**:
  - `[M2] Build the first MCP analytical surface over the warehouse`
- **Scope (first mission pass, per `ROADMAP.md:70-77`)**:
  - `query_warehouse`
  - `list_metrics`
  - `metric_summary`
- **Explicitly deferred from M2** (each becomes its own future mission):
  - Deterministic stats tools (`correlate`, `paired_t_test`, ...)
  - PubMed integration
- **Dependency**: blocked by M1's design decision note.

### M3. Add clinical lab ingestion and sparse-signal foundations

- **Milestone**: `v2.1 labs`
- **Labels**: `stage:ingest`, `stage:engine`, `type:feature`
- **Source docs**: `docs/history/research/PROPOSAL_LABS.md`, `docs/architecture/STAGES.md`
- **Outcome**: shipped and closed as issue `#3`; lab ingest and the first sparse-signal foundations are in the codebase, with later follow-on work now tracked separately.
- **Tracking issue title**:
  - `[M3] Add lab PDF ingest and sparse-signal foundations`
- **Parser shape**: **in-tree** at `src/premura/parsers/lab_pdf.py`, not as a Claude Code skill.
  - Skill-model validation (R2 from the risk register) is deferred to a separate future mini-mission with a smaller, simpler vendor (e.g. Withings CSV). Compounding the unproven skill model with PDF/OCR/multi-language complexity on one mission is too much risk on one bet.
- **Proposed WP shape (materialized when `/spec-kitty.specify` runs on M3)**:
  - WP: run the docling ablation study and choose extraction path
  - WP: add lab parser and ontology rows
  - WP: seed validity windows and missing-data policies
  - WP: add first derived lab ratios
- **Stage 3 MCP exposure**: out of M3's first scope. Filed as cross-mission sub-work that depends on M1's design decision note + M2's MCP infrastructure. Encoded via a follow-on tracking issue, not a sub-issue of M3.
- **Parallelization note**: M3's Stage 1 + Stage 2 WPs do not depend on M1 and can run in parallel with M2.

## Items I Would Not Pull Into The First Roadmap Pass

These appear in `ROADMAP.md` but are deferred:

- `hpipe inspect <file>`
- `hpipe gc` extension for `data/raw/`
- `hp.fact_interval.unit` migration
- daily Health Connect pickup
- cross-source priority reconsideration
- backfill historical Garmin dumps
- FIT-file decoding
- sample-level Garmin HRV/respiration expansion
- Skill-model validation via a smaller vendor (post-M3; separate mini-mission)
- SAA real-export validation (file an issue only if/when a real export breaks something)
- Wiki hub page (deferred until the codebase is more mature)

Reason: none outrank the open MCP-access question in `docs/history/product/RISK_OPPORTUNITY.md` or the concrete next-source proposal in `docs/history/research/PROPOSAL_LABS.md`.

## Important Consequence Of The Mission/Task Split Rule

Under the mission/task split rule, some items that feel "small" in `ROADMAP.md` still become missions:

- `hpipe inspect <file>` introduces a new CLI verb, so it qualifies as a mission.
- A schema-affecting warehouse change like `hp.fact_interval.unit` also leans mission-shaped.

That is stricter than the prose tone in `ROADMAP.md`. Once the planning system is in use, the roadmap should be rewritten in terms of the stricter classification rather than the earlier informal size language.

## Proposed Roadmap Ordering

This was the default first-pass sequence, not a hard dependency chain. It has now been executed for M1-M3. Current next work should start from the open follow-on issues rather than from this historical ordering.

1. M1 `[M1] Lock the MCP/warehouse boundary and keep age at export/upload` (closed)
2. M2 `[M2] Build the first MCP analytical surface over the warehouse` (closed)
3. M3 `[M3] Add lab PDF ingest and sparse-signal foundations` (closed)

If capacity allows after M1, M2 and M3 can run in parallel. That low-ceremony order is what this document was designed to justify.

## What Was Actually Created

### Labels (minimal)

- Bare triage-state labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`
- `stage:*`: `stage:ingest`, `stage:engine`, `stage:mcp`, `stage:ui`, `stage:ops`
- `type:*`: `type:bug`, `type:feature`, `type:spike`, `type:research`, `type:docs`, `type:refactor`

Deferred: `pillar:*` and `priority:*`. Added later only if a real filtering need emerges.

### Milestones

- Not created from this plan.
- Consequence: the intended `v2.0.0` / `v2.1.0` tag cuts did not happen.

### First Mission Tracking Issues

- `[M1] Lock the MCP/warehouse boundary and keep age at export/upload`
- `[M2] Build the first MCP analytical surface over the warehouse`
- `[M3] Add lab PDF ingest and sparse-signal foundations`

All three now exist as issues `#1`, `#2`, and `#3`, and all three are closed.

No initial task issues were created. SAA validation and wiki hub page remain deferred (see Working Assumptions).

## Review Questions

No open review questions remain. Remaining decisions are execution choices, not planning-shape ambiguities.

## Recommendation

Treat this document as the record of the first application pass, not as the current next-action list.

For current planning:

1. Use [../../product/FULL_APP_DEVELOPMENT_PLAN.md](../../product/FULL_APP_DEVELOPMENT_PLAN.md) for phase-level sequencing.
2. Use [../../product/ROADMAP.md](../../product/ROADMAP.md) for the short live narrative of what is next.
3. Use GitHub issues for the active mission backlog.
