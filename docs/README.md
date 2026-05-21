# Docs Guide

This index explains what each document is for and which ones are authoritative.

## Start here

- `../README.md` — operator and installation entry point.
- `../CONTRIBUTING.md` — main development guide for contributors and coding
  agents.
- `../AGENTS.md` — short router for agents and quick human navigation.

## Source of truth

- `SPEC.md` — product and data-contract requirements.
- `STAGES.md` — architecture boundaries between parsers, engine, MCP, and UI.
- `UPDATE_STRATEGY.md` — supported and deferred warehouse update kinds.
- `../src/premura/parsers/CONTRACT.md` — authoritative parser plugin contract.

## Live reference

- `STATUS.md` — what is currently true and shipped.
- `OPERATIONS.md` — operator commands and day-to-day run surface.
- `ROADMAP.md` — current sequencing of future work.
- `USERJOURNEY.md` — intended operator experience over time.
- `PARSER_CONTRIBUTING.md` — parser contributor guide layered on top of the
  parser contract.

## Proposal and archive

- `VISION.md` — long-term product trajectory.
- `ARCHITECTURE_HISTORY.md` — implementation history and architecture record
  for v1/v2.
- `PROPOSAL_LABS.md` — proposal for lab-ingestion support.
- `PRIOR_ART_BRIEF.md` — research brief used to generate the prior-art study.
- `PRIOR_ART_RESULTS.md` — results of the prior-art study.
- `RISK_OPPORTUNITY.md` — strategy memo on how much to invest next.

## Guidance

- If two docs disagree, prefer the more code-adjacent shipped contract.
- Parser rules should live in `../src/premura/parsers/CONTRACT.md`; other docs
  should summarize and link, not restate.
- Stage-boundary rules should live in `STAGES.md`; other docs should reference
  it when needed.
