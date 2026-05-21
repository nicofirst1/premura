# Docs Guide

This index explains what each document is for and which ones are authoritative.

Docs are grouped by **content domain** into four folders:

- `product/` — what the system is and where it's going.
- `architecture/` — how the system is shaped and what its contracts are.
- `operations/` — what the system currently does and how to run it.
- `research/` — proposals, prior-art studies, and forward-looking analyses.

## Start here

- `../README.md` — operator and installation entry point.
- `../CONTRIBUTING.md` — main development guide for contributors and coding
  agents.
- `../AGENTS.md` — short router for agents and quick human navigation.

## Source of truth

- `product/SPEC.md` — product and data-contract requirements.
- `architecture/STAGES.md` — architecture boundaries between parsers, engine, MCP, and UI.
- `architecture/UPDATE_STRATEGY.md` — supported and deferred warehouse update kinds.
- `../src/premura/parsers/CONTRACT.md` — authoritative parser plugin contract.

## Live reference

- `operations/STATUS.md` — what is currently true and shipped.
- `operations/OPERATIONS.md` — operator commands and day-to-day run surface.
- `product/ROADMAP.md` — current sequencing of future work.
- `product/USERJOURNEY.md` — intended operator experience over time.
- `architecture/PARSER_CONTRIBUTING.md` — parser contributor guide layered on top of the
  parser contract.

## Proposal and archive

- `product/VISION.md` — long-term product trajectory.
- `architecture/ARCHITECTURE_HISTORY.md` — implementation history and architecture record
  for v1/v2.
- `research/PROPOSAL_LABS.md` — proposal for lab-ingestion support.
- `research/PRIOR_ART_BRIEF.md` — research brief used to generate the prior-art study.
- `research/PRIOR_ART_RESULTS.md` — results of the prior-art study.
- `product/RISK_OPPORTUNITY.md` — strategy memo on how much to invest next.

## Guidance

- If two docs disagree, prefer the more code-adjacent shipped contract.
- Parser rules should live in `../src/premura/parsers/CONTRACT.md`; other docs
  should summarize and link, not restate.
- Stage-boundary rules should live in `architecture/STAGES.md`; other docs should reference
  it when needed.
