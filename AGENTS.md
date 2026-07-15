# AGENTS.md

> Repo-root router for a **coding agent dropped into this clone** to change Premura's code. Use this file to find the right working guide, not as the full contract itself.
>
> **Different audience?** If you are operating a developed Premura for a human through tools (not editing the repo), stop here and read the [runtime-agent operating guide](docs/operating/RUNTIME_AGENT.md) instead. If you are a human deciding whether to use Premura, start at [`README.md`](README.md).

## Read this first — two rules govern everything here

Premura is **operated and extended by AI agents**, for a human beneficiary (agent-first in execution, human-first in purpose — roughly 80% agents, 20% humans). Two rules follow, and they govern every spec, plan, contract, and doc:

1. **Agent-first.** The agent is the primary operational client; the human supplies data, goals, and approvals. Do not design human forms, dashboards, or human-operated flows as the default. Capture and analysis are agent-mediated.
2. **Design a level above — guide, don't enumerate.** Write specs, contracts, and docs as bounded abstractions agents fill in (registries, rubrics, contracts), **not** as exhaustive lists of domains, metrics, questions, or policies. Self-check at specify/plan/review time: _does this hardcode a list where it should define the rule for adding to the list?_

**Before writing or reviewing any spec or plan, read [`docs/shared/DOCTRINE.md`](docs/shared/DOCTRINE.md)** — it is the authoritative statement of both rules, with worked examples. This is not optional context; it is the thing agents most often get wrong.

- Before producing prose, planning docs, or onboarding material, read `CONTEXT.md` §"Maintainer mental model" and §"Planning" — they define the canonical vocabulary and explain when to prefer plain English over SE/agile jargon.
- If you are changing Premura's codebase, start with `CONTRIBUTING.md`.
- If you are adding or reviewing a federated parser, read `docs/building/architecture/PARSER_CONTRIBUTING.md`, then `src/premura/parsers/CONTRACT.md`.
- If you are using Claude Code to generate a parser, also read `src/premura/skills/parser-generator/SKILL.md`.

## First steps in this clone

You are inside a working clone of the repo. Before changing anything:

1. **Bootstrap once.** Run `uv run premura bootstrap` — it prepares and verifies this checkout (environment + bundled skills) and tells you whether an agent-session reload is needed. It is setup-only; it never ingests, uploads, or touches the warehouse.
2. **Read in this order:** [`docs/shared/DOCTRINE.md`](docs/shared/DOCTRINE.md) (the two rules) → `CONTEXT.md` (maintainer vocabulary) → [`CONTRIBUTING.md`](CONTRIBUTING.md) (setup, checks, conventions, PR handoff) → the relevant contract for your change.
3. **Make the change safely** following `CONTRIBUTING.md` §"Change style" and §"Architecture boundaries". Keep changes inside the right stage.
4. **Before review handoff,** run the changed-scope checks (`ruff`, `mypy`, `pytest`) documented in `CONTRIBUTING.md` and prepare the pull request there.

`CONTRIBUTING.md` owns the full development setup, check commands, and PR/review workflow — this router points to it rather than restating it.

## Standards-first rule (project-level)

For parser work, resolve vendor fields in this order and stop at the first match: existing alias via `suggest_metric(X)` → `LOINC` for labs → `IEEE 1752.1` for wearables → bare English canonical name → `vendor:<source>:<field>`.

If no step applies, skip the field at parse time and surface it via `IngestBatch.unmapped_metrics` for human review. If a field _does_ resolve to a canonical metric but still cannot become a loadable row, surface it via `IngestBatch.skipped_rows` instead.

- Never copy real operator PDFs, extracted PHI, or generated private report artifacts into this repo or a git commit while doing parser or extractor work.

## Agent skills

### Issue tracker

Issues for this repo are tracked in GitHub Issues for `nicofirst1/premura`. See `docs/building/agents/issue-tracker.md`.

### Triage labels

This repo uses the canonical triage labels `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/building/agents/triage-labels.md`.

### Domain docs

This repo is configured as single-context: skills should look for a root `CONTEXT.md` and `docs/building/adr/` when present. See `docs/building/agents/domain.md`.
