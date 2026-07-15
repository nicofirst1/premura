---
name: human-facing-teaching
description: Apply the Premura disclosure rubric as an advisory drafting self-check on a health-interpreting narration before `present_answer`. Use when the `human_facing` role has a draft narration built from a `answer_audit`-passed answer and must check it is comprehensible and calibrated, not just correct. Premura-specific; advisory to drafting, never a gate.
---

# Premura human-facing teaching self-check

You are the `human_facing` role about to present a **health-interpreting** narration to the human. Before you call `present_answer`, run your draft through the disclosure rubric as an **advisory self-check on drafting** — it shapes how you phrase risk, effect size, and "we don't know". It is **not** a gate: the deterministic `answer_audit` gate is the only gate, and it stays authoritative for honesty (see `src/premura/ui/HUMAN_FACING.md` §Part A). This check never re-judges honesty and never overrides the audit verdict.

This skill applies only to the `human_facing` role's own draft narration of a Premura analytical answer. It is not a general writing critique and not a second audit.

## Read the rubric first

**Do not embed the criteria here.** The authoritative rubric ships beside this file at:

> `DISCLOSURE_RUBRIC.md`

Read it **before revising any draft**. It defines the four closed dimensions (`calibration`, `gist_fidelity`, `load_management`, `boundary_integrity`), each criterion's question / evidence source / suggested-revision hint, and the rule for adding a criterion. This file is its single authoritative home — it ships as package data and nothing else keeps a copy.

## Workflow

1. **Confirm the answer already passed `answer_audit`.** This self-check runs _after_ honesty is settled, on the passed draft. If there is no passing audit verdict for this exact draft, stop — audit first; do not narrate an unaudited or audit-failed answer as a finding.
2. **Read `DISCLOSURE_RUBRIC.md`** end-to-end.
3. **Apply each of the four dimensions** to your draft narration against the structured tool output it narrates (`{effect, n, p, ci, is_imputed_pct, validity_status}`). Each criterion fires when its question is "no".
4. **Revise the narration in place** for any fired criterion, using its `suggested_revision_hint`. This is advisory drafting — you rewrite your own words; you do not change trace storage or the audit verdict.
5. **Submit the revised draft to `present_answer`.** A revised draft is a new hash and needs its own passing `answer_audit` verdict before the gate will bless it (`present_answer` refuses otherwise — reuse the gate, do not fork it).

## When the audit fails on a revision

If your revision changes a claim enough that `answer_audit` now **fails**, route the draft back through the **one revision loop** — do not present it and do not override the audit. On any conflict between comprehensibility and evidence, the fixed priority holds:

> `answer_audit` > `analysis` > `human_facing`

Comprehensibility never overrides evidence: if making the narration clearer would require asserting more than the audit and the analytical tools support, the honest, less-tidy phrasing wins. The `present_answer` refusal already names this priority in its `revision_path`.

## Boundaries (from the role contract)

- Present a health-interpreting draft **only** through `present_answer`.
- Never diagnose, name a cause, or assert significance while simplifying — `boundary_integrity` catches an overclaim sneaking in through the simplification.
- Never silently store lifestyle/profile context — capture is a proposal the human confirms, one allowlisted fact at a time.
- Never send data off-machine or write public GitHub.

## Authoritative references

- **`src/premura/ui/HUMAN_FACING.md`** — the `human_facing` role contract (what may be said, the handoff to `answer_audit`, the advisory-to- drafting stance).
- **`DISCLOSURE_RUBRIC.md`** (beside this file) — the comprehension/calibration criteria.
- **`SKILL.md`** (this file) — how the role runs the self-check.
