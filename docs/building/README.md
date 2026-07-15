# Building docs index

Contracts and agent-facing docs are the **single source of truth in `src/`, beside the code they govern** ([ADR 0017](adr/0017-contracts-live-in-src-docs-link.md)). This file is the pointer to every one of them. The cross-stage map is [`STAGES.md`](STAGES.md).

## Parsers (Stage 1 — ingest)

- [`parsers/CONTRACT.md`](../../src/premura/parsers/CONTRACT.md) — the `PluginParser` plugin contract: `IngestBatch`, the field-resolution decision tree, the `derived:` and same-PR ontology rules.
- [`parsers/PARSER_CONTRIBUTING.md`](../../src/premura/parsers/PARSER_CONTRIBUTING.md) — contributor guide for federated parser work (the standards-first metric-resolution ladder, federated-vs-core).
- [`parsers/AI_CHAT_RECALL_CONTRACT.md`](../../src/premura/parsers/AI_CHAT_RECALL_CONTRACT.md) — the interchange format for AI-recalled supplement/medication JSON exports.

## Engine (Stage 2 — signal processing)

- [`engine/CONTRACT.md`](../../src/premura/engine/CONTRACT.md) — what a Stage 2 signal function may compute and claim (the result envelope, refusal rules, no network/LLM).
- [`engine/INTAKE_DIMENSIONS.md`](../../src/premura/engine/INTAKE_DIMENSIONS.md) — the four-step rule for making a declared intake domain usable through the input-resolution seam.

## Store (warehouse)

- [`store/UPDATE_STRATEGY.md`](../../src/premura/store/UPDATE_STRATEGY.md) — the six warehouse update kinds and which are implemented versus not yet built.
- [`store/PROFILE_AND_INTAKE_CONTRACT.md`](../../src/premura/store/PROFILE_AND_INTAKE_CONTRACT.md) — the meaning contract for the baseline-profile, nutrition-intake, and supplement-intake domains (with its `profile_intake_contracts/*.yaml`).

## MCP / trace (Stage 3)

- [`AUDIT_CONSUMER_CONTRACT.md`](../../src/premura/AUDIT_CONSUMER_CONTRACT.md) — the structured Session Disclosure object `trace.py` produces and the research-trace-audit skill consumes.

## UI (Stage 4 — runtime)

- [`ui/OPERATING_ROLES.md`](../../src/premura/ui/OPERATING_ROLES.md) — the runtime orchestrator: bounded operating roles, the blocking answer-audit gate, the improvement queue, share packets.
- [`ui/HUMAN_FACING.md`](../../src/premura/ui/HUMAN_FACING.md) — the `human_facing` role contract and the first-run interview flow.

## Bundled agent skills (installed via `premura install-skills`)

- [`skills/premura/SKILL.md`](../../src/premura/skills/premura/SKILL.md) — first-run onboarding chain: install-check → what to know → what data → how to collect → analysis.
- [`skills/parser-generator/SKILL.md`](../../src/premura/skills/parser-generator/SKILL.md) — generate a new `PluginParser` for an unmapped vendor export.
- [`skills/human-facing-teaching/SKILL.md`](../../src/premura/skills/human-facing-teaching/SKILL.md) — apply the disclosure rubric as an advisory drafting self-check before `present_answer`.
- [`skills/human-facing-teaching/DISCLOSURE_RUBRIC.md`](../../src/premura/skills/human-facing-teaching/DISCLOSURE_RUBRIC.md) — the four-dimension rubric for whether a correct health answer is also comprehensible and calibrated.
- [`skills/research-trace-audit/SKILL.md`](../../src/premura/skills/research-trace-audit/SKILL.md) — audit a final answer against its Session Disclosure (search effort, hidden refusals, overclaiming).
- [`skills/research-trace-audit/AUDIT_RUBRIC.md`](../../src/premura/skills/research-trace-audit/AUDIT_RUBRIC.md) — the four-category rubric that audit applies.

## Acceptance harness (eval tooling)

- [`harness/IMPROVEMENT_PLAYBOOK.md`](../../src/premura/harness/IMPROVEMENT_PLAYBOOK.md) — how the acceptance harness turns judge verdicts into improvement proposals.
- [`harness/JUDGE_RUBRIC.md`](../../src/premura/harness/JUDGE_RUBRIC.md) — the rubric the acceptance-harness AI judge scores runs against.
