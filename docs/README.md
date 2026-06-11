# Docs Guide

This index explains what each document is for and which ones are authoritative.

Docs are split **by audience** at the directory level — your location in the tree
tells you whose docs you are in:

- `shared/` — cross-cutting docs every audience needs (identity, contract, live
  state, direction).
- `using/` — for a **human** using or evaluating Premura.
- `operating/` — for an **agent operating a developed Premura** for a human
  through tools, without editing the repo.
- `building/` — for **coding agents and maintainers** changing the repo; keeps
  its domain subdirs (`architecture/`, `adr/`, `agents/`, `planning/`,
  `research/`, `product/`).
- `history/` — archived plans, proposals, spikes, and historical references kept
  for context (audience-neutral).

## Start here — find your audience

These four doors are deliberately distinct; pick the one that matches what you
are doing, not just who you are.

- **Human using or evaluating Premura** → `../README.md` — what it is, how to
  run it locally, and where to go next.
- **Agent operating a developed Premura for a human** (tools, no code edits) →
  `operating/RUNTIME_AGENT.md` — MCP-first operation, approvals, honest data
  state, trace disclosure, PubMed and privacy boundaries, operator fallback.
- **Coding agent dropped into this clone** to change the code → `../AGENTS.md` —
  first steps, authoritative read order, and the safe-change/PR workflow.
- **Contributor (human or agent) opening a PR** → `../CONTRIBUTING.md` —
  development setup, checks, conventions, and review handoff.

The runtime agent and the coding agent are **not** the same audience: one
operates a shipped Premura through tools, the other edits the repo. Keep their
routes separate.

## Source of truth

- `shared/DOCTRINE.md` — product identity: agent-primary execution, human-primary purpose.
- `shared/SPEC.md` — product and data-contract requirements.
- `building/product/FULL_APP_DEVELOPMENT_PLAN.md` — phase-level plan from the current shipped state forward.
- `building/architecture/STAGES.md` — architecture boundaries between parsers, engine, MCP, and UI.
- `building/architecture/UPDATE_STRATEGY.md` — supported and deferred warehouse update kinds.
- `../src/premura/parsers/CONTRACT.md` — authoritative parser plugin contract.

For the analytical layer specifically, the shortest trustworthy read order is:

- `shared/STATUS.md` — what analytical behavior is already shipped
- `building/architecture/STAGES.md` — where Stage 2 ends and Stage 3 begins
- `../src/premura/engine/CONTRACT.md` — what Stage 2 signals may and may not claim
- `building/product/FULL_APP_DEVELOPMENT_PLAN.md` §`v0.3 analytical depth` — the current phase-level plan

## Live reference

- `shared/STATUS.md` — what is currently true and shipped: a bounded snapshot and the single home for shipped-state counts.
- `shared/CHANGELOG.md` — append-only mission-by-mission narratives (what shipped when, and why it looks the way it does).
- `using/OPERATIONS.md` — operator commands and day-to-day run surface.
- `shared/ROADMAP.md` — short live narrative of what is next; points to the phase plan instead of restating it.
- `history/product/ROADMAP_BOOTSTRAP_PLAN.md` — historical record of the first mission-instantiation pass (M1-M3) and its rationale.
- `using/USERJOURNEY.md` — intended operator experience over time.
- `building/architecture/PARSER_CONTRIBUTING.md` — parser contributor guide layered on top of the
  parser contract.

## Proposal and archive

- `history/product/VISION.md` — long-term product trajectory.
- `history/architecture/ARCHITECTURE_HISTORY.md` — implementation history and architecture record
  for v1/v2.
- `history/research/PROPOSAL_LABS.md` — proposal for lab-ingestion support.
- `history/research/PRIOR_ART_BRIEF.md` — research brief used to generate the prior-art study.
- `history/research/PRIOR_ART_RESULTS.md` — results of the prior-art study.
- `history/product/RISK_OPPORTUNITY.md` — strategy memo that informed earlier prioritization; background, not the active plan.

## Guidance

- If two docs disagree, prefer the more code-adjacent shipped contract.
- Parser rules should live in `../src/premura/parsers/CONTRACT.md`; other docs
  should summarize and link, not restate.
- Stage-boundary rules should live in `building/architecture/STAGES.md`; other docs should reference
  it when needed.
