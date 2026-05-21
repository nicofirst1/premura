# Parser Contributing

> Status: live reference. Parser contributor guide; authoritative parser rules live in `src/premura/parsers/CONTRACT.md`.

This guide is for contributors extending Premura through its federated parser
surface. If you are making general code changes across the repo, start with
`CONTRIBUTING.md` instead.

## Standards-first rule (project-level)

When mapping a vendor field to a canonical `metric_id` (in any parser, any
ontology row, any review comment), you MUST resolve in this order and stop at
the first match:

1. **Existing alias** in `src/premura/dim_metric.yaml` — call `suggest_metric(X)`.
2. **LOINC** for clinical lab markers — `metric_id = "lab:<english_canonical_name>"`.
3. **IEEE 1752.1** for wearable / physiological metrics.
4. **Bare English canonical name** for reusable cross-vendor concepts that
   neither LOINC nor IEEE 1752.1 covers.
5. **`vendor:<source>:<field>`** as the fallback for source-specific concepts.

If no step applies, do not invent a `metric_id`. Skip the field at parse time
and surface it via `PluginParseResult.unmapped_metrics` for human review.

Aliases recorded in `dim_metric.yaml` are restricted to **clinically standard
names and abbreviations only** — not free-text search terms or marketing
phrasing.

## Where to read next

- **Parser plugin contract (agent-agnostic, authoritative):**
  `src/premura/parsers/CONTRACT.md` — defines `PluginParser`,
  `PluginParseResult`, the full decision tree, the `derived:` namespace rule,
  and the same-PR ontology rule.
- **Claude Code skill (parser-generation walkthrough):**
  `src/premura/skills/parser-generator/SKILL.md` — installable via
  `hpipe install-skills`, which copies the skill into `./.claude/skills/` in
  the current project root.
- **General development guide:** `CONTRIBUTING.md`
- **Four-stage data flow:** `docs/STAGES.md` — Ingest (parsers) → Engine →
  MCP → UI. Each stage's importable Python package documents its layering
  rule in its `__init__.py` docstring (notably: Stage 3 MCP never reads
  `hp.fact_measurement` directly; Stage 4 UI never reads it or calls the
  engine directly).
- **Warehouse update policy:** `docs/UPDATE_STRATEGY.md` — the six update
  kinds and which ones the current architecture handles versus defers.

If `CONTRACT.md` ever disagrees with this file, `CONTRACT.md` wins.

## Stage naming (final)

The four stages are `parsers`, `engine`, `mcp`, `ui`. Stage 4 is `ui/`, not
`learn/` — an earlier draft used `learn`; that name is dead. Do not
reintroduce it.

## Canonical vocabulary policy

The policy above is defined now. **Renaming the legacy v1 `metric_id`s to the
final canonical vocabulary is deferred** to a later mission and will happen
via a **full rebuild from raw inputs**, not an in-place metric-id rewrite
migration. New parsers and ontology rows added today follow the policy;
existing rows are left in place.

## Federated vs. core

- **Federated (PRs welcome):** new parsers under `src/premura/parsers/` plus
  the matching `dim_metric.yaml` rows, governed by this file and
  `src/premura/parsers/CONTRACT.md`.
- **Core (this repo's maintainers):** engine signal functions, MCP wiring, UI
  flow. Those layers are not federated work.
