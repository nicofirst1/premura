# AGENTS.md

> Repo-root router for humans and AI agents. Use this file to find the right
> working guide, not as the full contract itself.

- If you are changing Premura's codebase, start with `CONTRIBUTING.md`.
- If you are adding or reviewing a federated parser, read
  `docs/architecture/PARSER_CONTRIBUTING.md`, then `src/premura/parsers/CONTRACT.md`.
- If you are using Claude Code to generate a parser, also read
  `src/premura/skills/parser-generator/SKILL.md`.

## Standards-first rule (project-level)

For parser work, resolve vendor fields in this order and stop at the first
match: existing alias via `suggest_metric(X)` → `LOINC` for labs → `IEEE
1752.1` for wearables → bare English canonical name →
`vendor:<source>:<field>`.

If no step applies, skip the field at parse time and surface it via
`PluginParseResult.unmapped_metrics` for human review.

## Agent skills

### Issue tracker

Issues for this repo are tracked in GitHub Issues for `nicofirst1/premura`. See `docs/agents/issue-tracker.md`.

### Triage labels

This repo uses the canonical triage labels `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

This repo is configured as single-context: skills should look for a root `CONTEXT.md` and `docs/adr/` when present. See `docs/agents/domain.md`.
