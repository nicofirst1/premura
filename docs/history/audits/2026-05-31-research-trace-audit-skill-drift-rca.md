# Drift Root-Cause Audit — `research-trace-audit-skill-01KSZC2J`

> Dated audit record. Produced with the method in
> [`docs/agents/implement-review-drift-audit.md`](../../agents/implement-review-drift-audit.md).

| | |
|---|---|
| **Mission** | `research-trace-audit-skill-01KSZC2J` (mission #13) |
| **Merge commit** | `52ca5d8` (squash merge to `master`) |
| **Mission-review verdict** | PASS WITH NOTES |
| **Audit date** | 2026-05-31 |
| **WPs** | WP01 research gate → WP02 fixtures+rubric → WP03 SKILL.md → WP04 install verify → WP05 docs sync |

## Unifying root cause

All three drifts survived in the **gaps between scopes**, not inside any WP's
local work. Per-WP review verified local correctness and *data-contract*
consistency well (it even cross-checked the `trace.py` producer for
`calls_truncated`), but the loop has **no step** that verifies:

- fidelity to a **production system surface** (D1),
- reconciliation of **frozen task metadata** after a gating WP flips scope (D2),
- or a **mission-level measurable requirement** that no single WP owns (D3).

A drift that is internally consistent and locally correct passes every per-WP
gate and only surfaces at mission-review. The three findings are three faces of
that one blind spot.

## Summary

| # | Drift | Dimension | Severity | Status |
|---|---|---|:--:|---|
| 1 | Fictional `tool_name: association_scan` in fixtures + SKILL.md + AUDIT_RUBRIC.md | D1 cross-system identifier fidelity | MEDIUM | **Fixed** `b82f934` |
| 2 | WP04 `owned_files` names `test_install_skills_multi_home.py`; actual file is `test_install_skills_research_trace_audit.py` | D2 frozen-metadata reconciliation | LOW | Open |
| 3 | NFR-002/SC-002 "two reviewers agree ≥4/5" never evidenced | D3 measurable NFR/SC ownership | LOW–MED | Open |

---

## Finding 1 — Fictional analytical tool name (RISK-1, D1)

**Drift.** The shipped fixtures, `SKILL.md`, and `AUDIT_RUBRIC.md` used
`tool_name: association_scan` — a tool the live MCP surface can never emit. The
real analytical tools are `change_point`, `smoothed_average`, `correlate`
(`src/premura/mcp/entrypoint.py:7-14,335,367,423`); `correlate` is the
association tool.

**Introduction.** WP02 (commit on lane-a; carried into merge `52ca5d8`). The gap
was *created by omission upstream*, not by an implementer ignoring guidance:
- WP02 prompt authorizes "synthetic trace fields" and enumerates the required
  *structured* fields but never names `tool_name` as value-constrained nor points
  at the live tool registry —
  `kitty-specs/research-trace-audit-skill-01KSZC2J/tasks/WP02-fixtures-and-bounded-rubric.md:79-102,149-154`.
- The input contract lists `tool_name` as a required Call Record field with **no
  enumeration / registry reference** —
  `kitty-specs/session-research-trace-01KSYT4A/contracts/audit-consumer-contract.md:38`.
- The rubric-criterion contract names "association / change / smoothed" only as
  *semantics*, never as literal tool identifiers —
  `contracts/rubric-criterion-contract.md:18`.

**Controls passed, and why each missed.**
- *WP02 prompt validation* — only required comparing fixture fields to the
  audit-consumer contract, which itself does not pin `tool_name` (`:149-154`).
- *Contract* — types `tool_name` as a bare string; a value that is merely
  shaped right cannot be caught (`audit-consumer-contract.md:38`).
- *WP02 review (all 4 identical cycles)* — raised only the `calls_truncated`
  inconsistency; the reviewer cross-referenced the `trace.py` *producer* for that
  field but never cross-referenced `tool_name` against `entrypoint.py`
  (`tasks/WP02-fixtures-and-bounded-rubric/review-cycle-{1..4}.md`).
- *WP03 review* — approved with no saved review artifact; example line inherited
  the fiction (`SKILL.md:91`).

**Missing control (D1).** A cross-system fidelity check: every fixture/rubric/
SKILL `tool_name` ∈ the live MCP analytical tool registry
(`entrypoint.py` `change_point`/`smoothed_average`/`correlate`). It should fire in
(a) the WP02 prompt validation block, (b) the audit-consumer Call Record contract
(pin `tool_name` to the registry), and (c) the WP02 review checklist.

**Why mission-review caught it.** It read the artifacts *against the live
entrypoint* — a `tool_name` no `@mcp.tool()` defines stood out. That cross-system
reference is exactly what no per-WP step performed.

**Generalizable lesson.** *Synthetic test fixtures invent identifiers the live
system cannot emit, and no review step validates fixtures against the production
registry.* Extends the known "per-WP reviews miss cross-WP contract gaps" lesson
to cross-*system* gaps: trace each contract field whose value is a real-system
identifier all the way to the production code that emits it, not just to a schema
that types it `string`.

**Remediation.** Fixed in `b82f934` — uniform `association_scan` → `correlate`
(13 sites); the `correlate` paired-sample-floor refusal also matches the fixtures'
"too few paired samples" refusals, so fidelity improved. No verdict changed.

---

## Finding 2 — WP04 owned_files metadata drift (RISK-2, D2)

**Drift.** WP04's frozen frontmatter `owned_files` (and `lanes.json`
`write_scope`) name `tests/test_install_skills_multi_home.py` plus a change to
`src/premura/skills/__init__.py`. The implementer created
`tests/test_install_skills_research_trace_audit.py` and made **zero** installer
changes; the actual filename appears in no task/lane metadata.

**Introduction & invalidation.** WP04 was an explicitly **contingent** WP gated
on WP01's adopt/defer/reject outcome
(`plan.md:32-33,139-141`; `WP04-installation-verification-and-contingent-installer.md:26-28,36-38`).
Its `owned_files` were frozen *optimistically assuming `adopt`* at tasks-finalize
(commit `aafb87d`, 18:21:33). WP01 research landed **after**
(`d43976a` 18:28; approved `c34d53a` 18:30) and **rejected** the installer
extension — "Installer: REJECT a separate OpenCode target … no new Python target,
no `test_install_skills_opencode_home.py`"
(`research/wp0-skill-research.md:111-112,138-142`). The gating decision
invalidated WP04's pre-written scope ~7 minutes after it was frozen.

**Controls passed, and why each missed.**
- *tasks-finalize* froze the metadata before the gate resolved; task artifacts
  are immutable afterward — `lanes.json:15-21` carries the same stale names.
- *No reconciliation step* exists between "gating WP approved" and "dependents
  dispatched."
- *WP04 review* logged the filename mismatch as a justified DIRECTIVE_010
  documented deviation (`WP04-…-installer.md:190`) — treated it as a deviation to
  wave through, not a metadata-correction trigger; per-WP review has no mandate to
  rewrite frozen frontmatter or `lanes.json`.

**Missing control (D2).** A reconciliation gate firing *after a gating WP is
approved and before its dependents dispatch*, re-validating the dependents'
`owned_files`/`write_scope` against the adopt/defer/reject outcome.

**Generalizable lesson.** *Frozen task metadata for research-gated/contingent WPs
goes stale the moment the gating WP changes scope, and nothing reconciles it;
review treats the resulting deviation as a justified exception instead of a signal
to correct the source-of-truth metadata.*

**Remediation.** Open. Options: (a) update WP04 frontmatter `owned_files` +
`lanes.json` to the real file; (b) add a mission-review addendum noting the
accepted deviation. Non-blocking — only matters to ownership-based tooling.

---

## Finding 3 — Unevidenced reproducibility requirement (D3)

**Drift/gap.** NFR-002/SC-002 — "two independent reviewer agents reach the same
top-level judgment for ≥4 of 5 fixtures" (`spec.md:68,114`) — was never
operationalized or committed as an artifact. The only verification was
single-reviewer fixture re-derivation.

**Introduction.** The measurable claim was never decomposed into any WP's owned
deliverable:
- It appears as WP02's prose "Independent Test" (`tasks.md:79`) and as
  `contracts/audit-result-contract.md:36-37` narrative — but **NFR-002 / SC-002
  are absent from every WP's `requirement_refs`** (WP01 FR-001…005; WP02
  FR-006/008/009/010/011 — `WP02-fixtures-and-bounded-rubric.md:6-11`; WP03
  FR-005/007/011/012; WP04 FR-003/004; WP05 FR-012).
- WP02's subtasks, Validation (`:149-154`), and Definition of Done (`:200-205`)
  require *one* reviewer to re-derive each verdict — never *two independent*
  reviewers recording agreement.
- The plan lumped NFR-002/SC-002 into "WP1" with no measurable owner
  (`plan.md:50-51,133`); the quickstart framed the two-reviewer check as a manual
  verification activity, not a committed artifact (`quickstart.md:38-48`).

**Controls passed, and why each missed.**
- *Per-WP reviews* verified local criteria (fixture hygiene, frontmatter,
  install) — not the mission-level metric.
- *Merge gate* force-moved all WPs to done; a mission-level NFR with no owning WP
  and no artifact had nothing to block on (`status.events.jsonl`).

**Missing control (D3).** A decomposition gate at `/spec-kitty.tasks` requiring
every measurable NFR/SC to (a) appear in a WP's `requirement_refs` and (b) name a
committed evidence artifact in that WP's DoD; plus a mission-acceptance gate
demanding the artifact before PASS.

**Generalizable lesson.** *Measurable NFRs/SCs not mapped into any WP's
`requirement_refs` and not tied to a committed evidence artifact produce no
evidence; reviews then confirm qualitative satisfaction of local criteria, not the
stated metric, and the gap surfaces only at mission-review as "PASS WITH NOTES."*

**Remediation.** Open. Producing the evidence is cheap: dispatch two independent
reviewer agents to apply `AUDIT_RUBRIC.md` to all five fixtures and commit the
recorded verdicts + ≥4/5 agreement as the artifact.

---

## Evidence index

- Production registry: `src/premura/mcp/entrypoint.py:7-14,335,367,423`.
- Contracts: `kitty-specs/session-research-trace-01KSYT4A/contracts/audit-consumer-contract.md:38`;
  `kitty-specs/research-trace-audit-skill-01KSZC2J/contracts/rubric-criterion-contract.md:18`,
  `contracts/audit-result-contract.md:36-37`.
- WP prompts: `tasks/WP02-fixtures-and-bounded-rubric.md:6-11,79-102,149-154,200-205`;
  `tasks/WP04-installation-verification-and-contingent-installer.md:26-28,36-38,190`.
- Review artifacts: `tasks/WP02-fixtures-and-bounded-rubric/review-cycle-{1..4}.md`; `status.events.jsonl`.
- Planning: `plan.md:32-33,50-51,133,139-141`; `quickstart.md:38-48`; `tasks.md:79`; `lanes.json:15-21`.
- Research gate: `research/wp0-skill-research.md:111-112,138-142`.
- Commits: tasks frozen `aafb87d`; WP01 landed/approved `d43976a`/`c34d53a`; merge `52ca5d8`; RISK-1 fix `b82f934`.
