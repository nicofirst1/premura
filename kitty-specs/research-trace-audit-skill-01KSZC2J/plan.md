# Implementation Plan: Research Trace Audit Skill

**Branch**: `master` | **Date**: 2026-05-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/research-trace-audit-skill-01KSZC2J/spec.md`

**Branch Contract**: Current branch at plan start is `master`. Planning/base branch is
`master`. Completed changes merge into `master`. `branch_matches_target` = true.

## Summary

Ship a **Premura-specific agent skill** that audits a final analytical answer against the
**session research trace** disclosure that already ships (the audit-consumer contract from
`session-research-trace-01KSYT4A`). The skill is the *interpretation* half the trace
mission deliberately withheld: given the structured Session Disclosure plus the final answer
text, it guides an agent through a reproducible review and emits a `pass` / `needs revision` /
`blocked` judgment with cited reasons and suggested revisions.

**Technical approach (confirmed in planning):**

- The skill ships as **prose `SKILL.md` + checked-in fixtures**, with **no runtime Python**.
  It lives at `src/premura/skills/research-trace-audit/`, matching the existing
  `parser-generator` convention. Runtime use is offline and agent-mediated (NFR-005).
- The **audit rubric is a bounded registry** — `AUDIT_RUBRIC.md` defines criteria *categories*
  plus **the rule for adding a criterion**, not a frozen list of banned phrases. This is the
  Design-Altitude / "guide, don't enumerate" gate applied directly to the deliverable.
- The skill **reads the audit-consumer contract structured fields**; it never parses the
  `disclosure_text` prose and never changes any trace count or schema (C-001…C-005).
- **WP0 (research slice) gates implementation.** The plan fixes the *shape* above now; the
  exact rubric criteria and the final set of installation targets are finalized only after
  WP0 is reviewed and accepted (FR-001).
- **Installation:** Claude-style (`.claude/skills/`, the existing `install_skills` path) ships
  unconditionally; extending `install_skills()` to an OpenCode-style home is a **contingent**
  work package, executed only if WP0 recommends *adopt*.

## Technical Context

**Language/Version**: Python 3.11+ (existing package). The skill deliverables are Markdown +
JSON fixtures; the only Python touched is `src/premura/skills/__init__.py` (`install_skills`),
and only in the contingent installer WP.
**Primary Dependencies**: None new. `install_skills` uses stdlib `importlib.resources` + `hashlib`.
The skill conforms to the **open Agent Skills standard** ([agentskills.io](https://agentskills.io/home);
folder with `SKILL.md` + optional bundled resources), so its *content* is write-once across the
skills-compatible client ecosystem (Claude Code, OpenCode, Cursor, Codex, …) — per-home variation
is the install *path* only. WP0 validates this (see `research.md`).
**Storage**: N/A. The skill is a read-only consumer of the audit-consumer contract object;
no migration, no `hp.*`/`trace.*` change (C-001).
**Testing**: pytest for any `install_skills` change (tested through the public function +
on-disk bytes, DIRECTIVE_036). The rubric's reproducibility (NFR-002) and the 5-case fixture
set (SC-002) are verified by **reviewer agents** running the rubric against the checked-in
fixtures — fixtures-with-expected-verdicts are authored *before* the rubric prose (the
test-first analog for a prose deliverable, DIRECTIVE_034).
**Target Platform**: macOS local-first; deliverables are platform-portable Markdown/JSON.
**Project Type**: single project (Python package with a bundled skill).
**Performance Goals**: `hpipe install-skills` stays under the 2 s non-ingest CLI target.
Audit runtime performs **no network call** (NFR-005).
**Constraints**: Read-only over the trace; offline at runtime; bounded rubric (no enumerated
banned-phrase list); fixtures use **synthetic** disclosure objects only — no real `hp.*` rows,
no PHI in fixtures or commits (risk boundary 5; the trace stores no health rows by design).
**Scale/Scope**: One skill directory; one contingent ~30-line installer extension; a fixture
set of at least 5 representative cases (SC-002).

## Charter Check

*GATE: passed for Phase 0. Re-checked after Phase 1 design — still passing.*

| Charter gate | Verdict | How this plan satisfies it |
|---|---|---|
| **Design Altitude / Directive 9 (guide, don't enumerate)** | ✅ | The rubric is a registry of criteria *categories* with a documented rule for adding a criterion (`contracts/rubric-criterion-contract.md`), not a hardcoded list of banned words. This is the single highest-risk gate for this mission and is the reason the deliverable is a rubric, not a checker. |
| **Test-first — DIRECTIVE_034** | ✅ | Fixtures with expected verdicts are authored before the rubric prose (red→green for a prose artifact). The contingent `install_skills` extension follows a failing pytest first. No horizontal slicing: fixtures and rubric land together per WP, not as a batch of imagined cases. |
| **Public-interface testing — DIRECTIVE_036** | ✅ | `install_skills` is exercised through its public signature and observable on-disk bytes/sha256, not internal helpers. The rubric is exercised through its documented inputs (disclosure + answer) and observable verdict, not implementation detail. |
| **Quality gates — DIRECTIVE_030** | ✅ | `ruff` (lint **and** `format --check`), `mypy` for changed Python scope, `pytest -q` green before handoff. Markdown WPs still run `ruff format --check` on any touched Python so the skill bundle can't land format-dirty (known per-WP-review gap). |
| **Spec fidelity — DIRECTIVE_010** | ✅ | Every FR maps to an artifact below; deviations (e.g. WP0 surfacing a contract mismatch) require explicit maintainer approval (Out of Scope item 1). |
| **Small blast radius — DIRECTIVE_024** | ✅ | A new skill directory is purely additive; the only existing file touched is `install_skills`, and only contingently. |
| **Local-first / offline (risk boundary 2 + NFR-005)** | ✅ | WP0 internet research is authoring-time only; ordinary audit execution requires no network. `install-skills` does not phone home. |
| **Scientific grounding / no overclaiming (risk boundary 3 + C-003/C-004)** | ✅ | The rubric's entire purpose is to *catch* causal/diagnostic/significance overclaims; it introduces none of its own. |
| **PHI hygiene (risk boundary 5)** | ✅ | Fixtures are synthetic disclosure objects; no real health rows, no PHI in commits. |

No charter violations — Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```
kitty-specs/research-trace-audit-skill-01KSZC2J/
├── plan.md              # This file (/spec-kitty.plan output)
├── research.md          # Phase 0 — planning decisions + rationale (WP0 does the deep external research)
├── data-model.md        # Phase 1 — skill entities (no DB; conceptual + fixture shape)
├── quickstart.md        # Phase 1 — how a reviewer verifies the skill
├── contracts/           # Phase 1 — audit-result + rubric-criterion contracts
│   ├── audit-result-contract.md
│   └── rubric-criterion-contract.md
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/premura/skills/
├── __init__.py                       # install_skills() — touched ONLY by the contingent installer WP
├── parser-generator/                 # existing skill (reference convention)
│   └── SKILL.md
└── research-trace-audit/             # NEW — this mission
    ├── SKILL.md                      # agent-facing: when-to-invoke, required inputs, review flow, output shape
    ├── AUDIT_RUBRIC.md               # bounded criteria categories + the rule for adding a criterion
    └── fixtures/                     # synthetic Session Disclosure + final answer + expected verdict
        ├── pass.json
        ├── omitted-search-effort.json
        ├── hidden-refusal.json
        ├── surfaced-unavailable.json
        └── overclaim.json

tests/
└── test_install_skills_opencode_home.py   # ONLY if WP0 recommends adopt (contingent installer WP)
```

**Structure Decision**: Single project. The skill is a new sibling directory under the
existing `premura.skills` package so the shipped `install_skills()` discovers it automatically
(it walks every immediate child containing a `SKILL.md`). The skill is prose + fixtures with
no runtime Python; the only conditional code change is an additive installation target.

## Implementation Phasing (advisory — finalized by `/spec-kitty.tasks`)

This is guidance for task generation, not a work-package manifest. Per the gating decision,
WP0 is reviewed and accepted before WP1+ details are locked.

1. **WP0 — Research slice (GATES the rest).** FR-001…FR-005, NFR-004, SC-001. External-source
   study of how agent skills are written, how skills install/discover across Claude-style and
   OpenCode-style homes, and whether a write-once packaging approach is worth adopting →
   an **adopt / defer / reject** recommendation and Premura-specific authoring rules.
   Output ≤ 1,500 words excluding citations (NFR-004); ≥ 3 external sources or a stated reason
   for fewer (FR-002). Reviewed/accepted before WP1.
2. **WP1 — Fixtures + rubric.** FR-006…FR-011, C-002…C-005, NFR-002/003, SC-002/003/004.
   Author the 5 synthetic fixtures **with expected verdicts first**, then `AUDIT_RUBRIC.md`
   (bounded criteria + rule-for-adding) to satisfy them.
3. **WP2 — SKILL.md authoring.** FR-005, FR-007, FR-012, NFR-001, C-006. The agent-facing
   wrapper: when-to-invoke, required-inputs-in-under-2-minutes, review flow, output shape;
   keeps packaging guidance out of the audit logic (C-006).
4. **WP3 — Installation (Claude-style verified; OpenCode-style contingent).** FR-003/004,
   NFR-006, SC-005. Verify the existing `.claude/skills/` path installs the new skill; **if
   WP0 = adopt**, extend `install_skills()` to an OpenCode-style home, test-first.
5. **WP-DOCS — Live-doc sync.** Update `docs/operations/STATUS.md` ("Audit skill deferred" →
   shipped) and `docs/product/ROADMAP.md` ("Still deferred: audit skill"). This WP is called
   out explicitly so it is not dropped; it owns the live docs and commits them.

## Complexity Tracking

*No charter violations. Section intentionally empty.*
