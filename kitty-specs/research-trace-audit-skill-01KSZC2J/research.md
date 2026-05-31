# Phase 0 Research — Research Trace Audit Skill

> Scope note: this file records the **planning-time decisions** and their rationale. The deep,
> external-source-backed study of skill authoring and packaging is the mission's own **WP0
> deliverable** (FR-001…FR-005), not the planner's job. This document fixes the shape WP0
> operates within and explicitly hands the open external questions to WP0.

## Decision 1 — Skill artifact shape: prose `SKILL.md` + checked-in fixtures, no runtime Python

- **Decision:** Ship a Markdown skill (`SKILL.md` + `AUDIT_RUBRIC.md`) plus a `fixtures/`
  directory of synthetic Session-Disclosure-+-answer-+-expected-verdict cases. No runtime
  Python audit module.
- **Rationale:** Matches the existing `parser-generator` convention and the charter's
  agent-first, local-first stance. The audit is a *judgment an agent performs*, not a function
  a checker computes — encoding it as deterministic Python would (a) re-create the trace's
  semantics in code, risking the C-001 boundary, and (b) collapse a bounded rubric into a
  hardcoded list, violating Design Altitude. Reproducibility (NFR-002) is still verifiable:
  reviewer agents run the rubric against the checked-in fixtures and must agree on ≥ 4 of 5.
- **Alternatives considered:**
  - *Prose `SKILL.md` only (inline examples).* Rejected: SC-002's "5 representative fixtures
    reviewed" and NFR-002 reproducibility are hard to verify without checked-in, separable cases.
  - *`SKILL.md` + Python audit helper + pytest.* Rejected for v1: strongest regression guarantee
    but introduces runtime code that tends toward a frozen checklist (Design Altitude tension)
    and re-implements trace meaning. NFR-005 forbids runtime *network*, not runtime code, so
    this is a doctrine choice, not a hard constraint — revisitable in a later mission if
    fixtures prove insufficient.

## Decision 2 — Audit rubric is a bounded registry, not a banned-phrase list

- **Decision:** `AUDIT_RUBRIC.md` defines criteria **categories** (search-effort disclosure;
  refused / errored / unavailable / contradictory handling; overclaiming beyond analytical
  boundaries) and a documented **rule for adding a criterion** (see
  `contracts/rubric-criterion-contract.md`). The 5 fixtures are *exemplars* of categories,
  not the closed universe of checks.
- **Rationale:** Directly satisfies Directive 9 / DOCTRINE. An enumerated "flag these 7
  phrases" list is the anti-pattern the charter names explicitly; a rubric an agent fills in
  is the reference pattern. It also future-proofs the skill against new analytical tools whose
  overclaim modes don't exist yet.
- **Alternatives considered:** A fixed checklist of forbidden tokens (p-value, "significant",
  "causes", "diagnoses"…). Rejected — too narrow; agents route around it and it cannot cover
  novel overclaims.

## Decision 3 — Read-only consumption of the audit-consumer contract

- **Decision:** The skill maps each required input to a **structured field** of the Session
  Disclosure object (`raw_analytical_call_count`, `unique_hypothesis_count`, `surfaced`,
  `refusal_breakdown`, `calls`, per-`Call Record` `terminal_status`/`refusal_reason`). It must
  not parse `disclosure_text` prose for counts and must respect `calls_truncated` / summary
  counts rather than requiring every raw call.
- **Rationale:** FR-006, C-001, C-002, and the contract's own rule ("a consumer must derive its
  own counts from the structured fields, never by parsing the prose"). Keeps the trace the
  single source of truth for counts.
- **Alternatives considered:** Reading the rendered Markdown disclosure. Rejected by the
  contract itself.

## Decision 4 — WP0 gates; installation is split (Claude-style firm, OpenCode-style contingent)

- **Decision:** plan fixes the shape; rubric criteria and final install targets finalize after
  WP0 acceptance (FR-001). Claude-style `.claude/skills/` ships unconditionally via the existing
  `install_skills()` (no code change — it auto-discovers the new directory). Extending
  `install_skills()` to an OpenCode-style home is executed **only if WP0 recommends adopt**.
- **Rationale:** Honors FR-001's "reviewed before later work begins" and keeps blast radius
  small (DIRECTIVE_024). The existing installer already walks every child with a `SKILL.md`, so
  the new skill is picked up for free on the Claude path; multi-home is genuinely contingent on
  the research outcome (FR-004's adopt/defer/reject).
- **Alternatives considered:** Commit to multi-home now (pre-empts WP0); leave all install scope
  to WP0 (plan commits to too little). The split is the middle path.

## Anchor source for WP0 — the open Agent Skills standard (agentskills.io)

The maintainer surfaced [agentskills.io](https://agentskills.io/home) as a candidate reference.
It is the **open Agent Skills standard**: originally developed by Anthropic, released as an open
standard, now adopted across a large client list (Claude Code, OpenCode, Cursor, Gemini CLI,
OpenAI Codex, Goose, GitHub Copilot, VS Code, Kiro, and ~30 more). WP0 should treat it as the
primary anchor source (with the per-client `instructionsUrl` pages and the spec/quickstart):

- **Format (matches Premura already):** a skill is a folder containing a `SKILL.md` with at
  minimum `name` + `description` frontmatter plus instructions, optionally bundling `scripts/`,
  `references/`, `assets/`. Premura's existing `parser-generator/SKILL.md` is already
  conformant, and this mission's `research-trace-audit/` (SKILL.md + AUDIT_RUBRIC.md + fixtures/)
  fits the same shape — `fixtures/` and `AUDIT_RUBRIC.md` are just bundled resources.
- **Progressive disclosure:** discovery (name+description) → activation (full SKILL.md) →
  execution. This directly informs how the `description` should be written (NFR-001: required
  inputs findable fast) and why the rubric lives in a sibling file loaded on activation, not in
  the discovery blurb.
- **Reframes FR-004 (write-once / multi-home):** the standard's explicit value prop is
  "build a skill once and use it across any skills-compatible agent." So the *content* is
  write-once **by conformance to the standard**; the only per-home variation is the **install
  path** each client scans (e.g. Claude Code's `.claude/skills/` vs OpenCode's skill home).
  This makes "extend `install_skills()` with additional target paths" the natural write-once
  mechanism — **the leading hypothesis WP0 should validate**, not a foregone conclusion. WP0
  still owns the adopt/defer/reject call and must confirm each target home's actual scan path
  from its `instructionsUrl` docs and give a locally-verifiable check (NFR-006).
- **Reference index:** the site exposes `https://agentskills.io/llms.txt` (doc index),
  a `/specification` page, and a `/skill-creation/quickstart`; source/discussion at
  `github.com/agentskills/agentskills`. These satisfy FR-002's "≥ 3 external sources" on their
  own, but WP0 should still cite the individual client skill-docs it relies on for install paths.

## Open questions handed to WP0 (do not resolve at plan time)

1. The concrete OpenCode-style (and any other) local skill-home layout, and whether a
   write-once source with per-home installation is worth the complexity → **adopt/defer/reject**
   with tradeoffs (FR-004).
2. General skill-authoring best practices from current external sources (≥ 3, or a reason for
   fewer) and their Premura-specific translation (FR-002, FR-005).
3. A locally-verifiable check per supported installation target (NFR-006).

These are intentionally unresolved here so WP0 owns them; resolving them in this file would
make WP0 redundant and risk locking a plan the research contradicts.
