# Docs Guide

This index explains what each document is for and which ones are authoritative.

Docs are grouped by **content domain** into five folders:

- `product/` — what the system is and where it's going.
- `architecture/` — how the system is shaped and what its contracts are.
- `operations/` — what the system currently does and how to run it.
- `research/` — proposals, prior-art studies, and forward-looking analyses.
- `history/` — archived plans, proposals, spikes, and historical references kept for context.

## Start here

- `../README.md` — operator and installation entry point.
- `../CONTRIBUTING.md` — main development guide for contributors and coding
  agents.
- `../AGENTS.md` — short router for agents and quick human navigation.

## Source of truth

- `product/DOCTRINE.md` — product identity: agent-primary execution, human-primary purpose.
- `product/SPEC.md` — product and data-contract requirements.
- `product/FULL_APP_DEVELOPMENT_PLAN.md` — phase-level plan from the current shipped state forward.
- `architecture/STAGES.md` — architecture boundaries between parsers, engine, MCP, and UI.
- `architecture/UPDATE_STRATEGY.md` — supported and deferred warehouse update kinds.
- `../src/premura/parsers/CONTRACT.md` — authoritative parser plugin contract.

For the analytical layer specifically, the shortest trustworthy read order is:

- `operations/STATUS.md` — what analytical behavior is already shipped
- `architecture/STAGES.md` — where Stage 2 ends and Stage 3 begins
- `../src/premura/engine/CONTRACT.md` — what Stage 2 signals may and may not claim
- `product/FULL_APP_DEVELOPMENT_PLAN.md` §`v2.2 analytical depth` — the current phase-level plan

## Live reference

- `operations/STATUS.md` — what is currently true and shipped.
- `operations/OPERATIONS.md` — operator commands and day-to-day run surface.
- `product/ROADMAP.md` — short live narrative of what is next; points to the phase plan instead of restating it.
- `history/product/ROADMAP_BOOTSTRAP_PLAN.md` — historical record of the first mission-instantiation pass (M1-M3) and its rationale.
- `product/USERJOURNEY.md` — intended operator experience over time.
- `architecture/PARSER_CONTRIBUTING.md` — parser contributor guide layered on top of the
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
- Stage-boundary rules should live in `architecture/STAGES.md`; other docs should reference
  it when needed.
