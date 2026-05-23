# Premura Initial Roadmap Plan

> Status: review draft. Proposed application of the planning system to Premura's current docs. No GitHub issues, labels, milestones, boards, or specs have been created by this draft. Doc edits driven by this plan are committed separately (see git log — e.g. `ROADMAP.md` reconciliation landed at `c11fc8c`).
>
> **Naming note**: this doc is filed at `docs/product/ROADMAP_BOOTSTRAP_PLAN.md`. The word "bootstrap" collides with `ops/bootstrap.sh` (operational setup script). The doc's content avoids the word; a file rename is pending and will be a separate small commit.

## Purpose

Turn the approved planning system into the first concrete roadmap for Premura.

This file answers:

- what roadmap items already exist in the docs
- which ones become missions under the partition rule
- what milestone shape makes sense for the first pass
- what would be created first once execution is approved

## Inputs Used

- `docs/operations/STATUS.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- `docs/product/ROADMAP.md`
- `docs/product/RISK_OPPORTUNITY.md`
- `docs/research/PROPOSAL_LABS.md`
- `docs/architecture/STAGES.md`
- `docs/architecture/UPDATE_STRATEGY.md`
- `docs/agents/issue-tracker.md`
- `docs/agents/triage-labels.md`
- `/tmp/premura-planning-handoff-2026-05-22.md`

## Working Assumptions

- The planning-system handoff is accepted in substance and is the process to apply.
- This pass instantiates the roadmap; it does not execute it.
- This plan is the near-term execution layer for Phases 1 and 2 in `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`, not a competing phase plan.
- `ROADMAP.md` has been reconciled against shipped state (commit `c11fc8c`), so this plan starts from remaining open work.
- The active backlog is **missions-only** — no tasks. SAA real-export validation and the wiki hub page are both deferred (wiki: "once we have a proper codebase"; SAA: file an issue if and when the next real export breaks something).

## What Would Be Done First

1. Create the minimal canonical label vocabulary: 5 bare triage labels + `stage:*` (5) + `type:*` (6). No `pillar:*` or `priority:*` yet.
2. Create two milestones from the docs' natural sequencing: `v2.0 analytical surface`, `v2.1 labs`.
3. Create one GitHub tracking issue per mission (3 total), titled with `[M1]`/`[M2]`/`[M3]` prefixes.
4. Do not design the full Projects v2 board taxonomy yet — board fields and views are designed after M1 completes.
5. Start with the `mcp+age` spike (M1), the highest-leverage open uncertainty per `RISK_OPPORTUNITY.md:151`.

## Discipline rules

### Tag-cut on milestone close

When `v2.0 analytical surface` closes (M1 + M2 done), cut tag `v2.0.0`. When `v2.1 labs` closes (M3 done), cut `v2.1.0`. Tags are restore points: someone with the encrypted Drive snapshot + age key + a tag can reproduce the pipeline at a known state.

### Mission title format

`[M1] <descriptive title>`, `[M2] ...`, etc. Sorts cleanly in issue lists; grep-able in commits.

### Cross-stage labeling

The planning-system handoff said "one stage per issue." Relax that: missions that genuinely span stages get multiple `stage:*` labels. M3 spans Stage 1 (parser) and Stage 2 (validity windows, missing-data policy, derived ratios), so it carries both `stage:ingest` and `stage:engine`.

### Decomposition surface

Each mission has **one** GitHub tracking issue. Intra-mission decomposition (e.g. M3's slices) lives inside `kitty-specs/<slug>/` as work packages when `/spec-kitty.specify` runs. Cross-mission dependencies (M2 blocked by M1, M3's Stage-3 sub-work blocked by M1 + M2) are encoded as "blocked by" comments on the tracking issues.

## Proposed Milestones

### `v2.0 analytical surface`

Purpose: answer the storage/MCP boundary question, then build the first real Stage 3 analytical surface.

Candidate contents:

- `mcp+age` compatibility spike (M1)
- First MCP analytical server (M2)
- ADR locking the encrypted-DuckDB access boundary (output of M1)

### `v2.1 labs`

Purpose: add clinical labs as the first new source class and the first substantive Stage 2 engine use.

Candidate contents (decomposed inside `kitty-specs/<m3-slug>/` when M3 specifies):

- Docling spike on representative lab PDFs
- Lab PDF parser (in-tree under `src/premura/parsers/lab_pdf.py`)
- `dim_metric` additions for labs
- Validity-window and missing-data policy seeding for sparse lab metrics
- First derived lab signals

Not in this milestone:

- Stage 3 lab-signal exposure. That is later cross-mission follow-on work and depends on M1's ADR plus M2's MCP infrastructure.

## Initial Backlog Proposal

### M1. Lock the MCP/warehouse boundary

- **Milestone**: `v2.0 analytical surface`
- **Labels**: `stage:mcp`, `type:spike`
- **Source docs**: `docs/product/RISK_OPPORTUNITY.md`, `docs/product/ROADMAP.md`
- **Tracking issue title**:
  - `[M1] Lock the MCP/warehouse boundary and keep age at export/upload`
- **Definition of done (1-week timebox)**:
  - An ADR is filed. The ADR captures *one* of:
    - The recommended boundary for M2, including where `age` applies and whether MCP can read the live warehouse directly.
    - Any rejected stricter alternatives, with the failure mode or tradeoff documented.
- **Follow-on output**:
  - Concrete recommendation for M2 (whether the existing MCP boundary is sufficient or requires a wrapper).
  - Concrete recommendation for M3's later Stage-3 sub-work (whether the same boundary applies to lab-derived signals).

### M2. Build the first MCP analytical server

- **Milestone**: `v2.0 analytical surface`
- **Labels**: `stage:mcp`, `type:feature`
- **Source docs**: `docs/product/ROADMAP.md`, `docs/architecture/STAGES.md`
- **Tracking issue title**:
  - `[M2] Build the first MCP analytical surface over the warehouse`
- **Scope (first mission pass, per `ROADMAP.md:70-77`)**:
  - `query_warehouse`
  - `list_metrics`
  - `metric_summary`
- **Explicitly deferred from M2** (each becomes its own future mission):
  - Deterministic stats tools (`correlate`, `paired_t_test`, ...)
  - PubMed integration
- **Dependency**: blocked by M1's ADR.

### M3. Add clinical lab ingestion and sparse-signal foundations

- **Milestone**: `v2.1 labs`
- **Labels**: `stage:ingest`, `stage:engine`, `type:feature`
- **Source docs**: `docs/research/PROPOSAL_LABS.md`, `docs/architecture/STAGES.md`
- **Tracking issue title**:
  - `[M3] Add lab PDF ingest and sparse-signal foundations`
- **Parser shape**: **in-tree** at `src/premura/parsers/lab_pdf.py`, not as a Claude Code skill.
  - Skill-model validation (R2 from the risk register) is deferred to a separate future mini-mission with a smaller, simpler vendor (e.g. Withings CSV). Compounding the unproven skill model with PDF/OCR/multi-language complexity on one mission is too much risk on one bet.
- **Proposed WP shape (materialized when `/spec-kitty.specify` runs on M3)**:
  - WP: run the docling spike and choose extraction path
  - WP: add lab parser and ontology rows
  - WP: seed validity windows and missing-data policies
  - WP: add first derived lab ratios
- **Stage 3 MCP exposure**: out of M3's first scope. Filed as cross-mission sub-work that depends on M1's ADR + M2's MCP infrastructure. Encoded via a follow-on tracking issue, not a sub-issue of M3.
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

Reason: none outrank the open boundary question in `RISK_OPPORTUNITY.md` or the concrete next-source proposal in `PROPOSAL_LABS.md`.

## Important Consequence Of The Current Partition Rule

Under the partition rule, some items that feel "small" in `ROADMAP.md` still become missions:

- `hpipe inspect <file>` introduces a new CLI verb, so it qualifies as a mission.
- A schema-affecting warehouse change like `hp.fact_interval.unit` also leans mission-shaped.

That is stricter than the prose tone in `ROADMAP.md`. Once the planning system is in use, the roadmap should be rewritten in terms of the stricter classification rather than the earlier informal size language.

## Proposed Roadmap Ordering

This is a default sequence, not a hard dependency chain. If capacity allows, M3's Stage 1 + Stage 2 WPs can run in parallel with M2; only M3's Stage-3 sub-work strictly depends on M1's ADR and M2's MCP infrastructure.

1. M1 `[M1] Lock the MCP/warehouse boundary and keep age at export/upload`
2. M2 `[M2] Build the first MCP analytical surface over the warehouse` as the default next mission
3. M3 `[M3] Add lab PDF ingest and sparse-signal foundations`

If capacity allows after M1, M2 and M3 can run in parallel. The default low-ceremony order above keeps the first execution pass simple.

## What Would Be Created On Execution

### Labels (minimal)

- Bare triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`
- `stage:*`: `stage:ingest`, `stage:engine`, `stage:mcp`, `stage:ui`, `stage:ops`
- `type:*`: `type:bug`, `type:feature`, `type:spike`, `type:research`, `type:docs`, `type:refactor`

Deferred: `pillar:*` and `priority:*`. Added later only if a real filtering need emerges.

### Milestones

- `v2.0 analytical surface`
- `v2.1 labs`

### First Mission Tracking Issues

- `[M1] Lock the MCP/warehouse boundary and keep age at export/upload`
- `[M2] Build the first MCP analytical surface over the warehouse`
- `[M3] Add lab PDF ingest and sparse-signal foundations`

No initial task issues. SAA validation and wiki hub page are both deferred (see Working Assumptions).

## Review Questions

No open review questions remain. Remaining decisions are execution choices, not planning-shape ambiguities.

## Recommendation

Approve this shape and perform exactly one application pass:

1. Create the minimal label vocabulary.
2. Create the two milestones.
3. Open the three mission tracking issues above.
4. Start M1 first.

When M1 + M2 both close, cut `v2.0.0`. When M3 closes, cut `v2.1.0`.
