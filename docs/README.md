# Docs Guide

This index explains what each document is for and which are authoritative.

Docs are split **by audience** at the directory level — your location in the tree tells you whose docs you are in:

- `shared/` — cross-cutting docs every audience needs (identity, contract, live state).
- `using/` — for a **human** using or evaluating Premura.
- `operating/` — for an **agent operating a developed Premura** for a human through tools, without editing the repo.
- `building/` — for **coding agents and maintainers** changing the repo (`architecture/`, `adr/`).

## Start here — find your audience

These four doors are deliberately distinct; pick the one that matches what you are doing, not just who you are.

- **Human using or evaluating Premura** → `../README.md` — what it is, how to run it locally, and where to go next.
- **Agent operating a developed Premura for a human** (tools, no code edits) → `operating/RUNTIME_AGENT.md` — MCP-first operation, approvals, honest data state, trace disclosure, PubMed and privacy boundaries, operator fallback.
- **Coding agent dropped into this clone** to change the code → `../AGENTS.md` — first steps, authoritative read order, and the safe-change/PR workflow.
- **Contributor (human or agent) opening a PR** → `../CONTRIBUTING.md` — development setup, checks, conventions, and review handoff.

The runtime agent and the coding agent are **not** the same audience: one operates a shipped Premura through tools, the other edits the repo. Keep their routes separate.

## Source of truth

- `shared/DOCTRINE.md` — product identity: agent-primary execution, human-primary purpose.
- `shared/SPEC.md` — product and data-contract requirements.
- `building/architecture/STAGES.md` — architecture boundaries between parsers, engine, MCP, and UI.
- `../src/premura/engine/CONTRACT.md` — what Stage 2 signals may and may not claim.
- `../src/premura/parsers/CONTRACT.md` — the parser plugin contract.
- Operating, interview, storage, and domain contracts live beside their code under `../src/premura/{ui,store,engine,parsers}/`; `building/architecture/STAGES.md` indexes them.

## Live reference

- Shipped-state counts (tools, signals, tests) live in no doc — read them from `premura --help`, `premura status`, and the test suite.
- `shared/CHANGELOG.md` — append-only mission-by-mission narratives (what shipped when, and why).
- `using/OPERATIONS.md` — operator commands and day-to-day run surface.
- `using/USERJOURNEY.md` — intended operator experience over time.

Direction and what's next live in GitHub milestones, not in a standalone roadmap doc.

## Guidance

- If two docs disagree, prefer the more code-adjacent shipped contract.
- Parser rules live in `../src/premura/parsers/CONTRACT.md`; other docs summarize and link, not restate.
- Stage-boundary rules live in `building/architecture/STAGES.md`; other docs reference it when needed.
