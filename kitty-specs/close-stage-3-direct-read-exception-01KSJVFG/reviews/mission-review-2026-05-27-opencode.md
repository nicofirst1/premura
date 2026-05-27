# Mission Review — close-stage-3-direct-read-exception-01KSJVFG

**Reviewer:** OpenCode (mission-level, post-merge)
**Date:** 2026-05-27
**Merged implementation commit:** `8c3d766` (squash merge into `master`)
**Verdict:** **FAIL** → remediated in **PR #7** (`fix/stage3-fr004-operator-gate`)

This mission shipped its core change correctly (catalog/summary re-backed through
Stage 2; `query_warehouse` off the default surface; docs/ADR updated), but a
post-merge mission review found two blocking spec-to-code gaps that the per-WP
reviews missed. All findings were verified against `spec.md` before fixing.

## Findings and resolution

| # | Severity | Finding | Resolution (PR #7) |
|---|----------|---------|--------------------|
| 1 / DRIFT-1 | HIGH | **FR-004 unmet at the catalog surface.** Scenario 4 + FR-004 verification require the catalog tool to return an explicit `unavailable` entry for an unknown metric id. `list_metrics` took no id input (it enumerated `dim_metric`), so an unknown id was structurally impossible — and the WP02 cycle-1 fix *documented* the divergence in `test_list_metrics_omits_unregistered_metric_ids`. | `list_metrics` now accepts optional `metric_ids`; a supplied unknown id flows to `engine.list_metric_catalog` → explicit `unavailable` entry. Bad test replaced with `test_list_metrics_unknown_metric_id_returns_unavailable_entry` (+ mixed-ids + enumeration tests). |
| 2 / DRIFT-2 | HIGH | **Operator approval documented but not enforced.** The operator contract asserts `explicit_user_approval_required_for_agent_use: true`, but the code only embedded warning prose; the console script was directly runnable. | `main_operator` now refuses to start (never registers `query_warehouse`) unless launched with `--ack` or `PREMURA_OPERATOR_ACK`. Enforcement is now: surface separation **+** explicit launch ack. Disclosure to the end user is documented as a client/agent-layer responsibility a server can't enforce. (Maintainer decision: ack gate **+** honest docs.) |
| 3 / RISK-1 | MEDIUM | No e2e test for the `premura-mcp-operator` console script (only in-process builder test). | Added `test_stdio_operator_server_exposes_query_warehouse` (subprocess, `--ack`) plus in-process ack-gate tests (refuse-without-ack, flag-ack, env-ack). |
| 4 / DRIFT-3 | LOW | Docs claimed "no raw `hp.*` SQL" on the default surface, but `list_metrics` ran `SELECT metric_id FROM hp.dim_metric`. | Enumeration moved into `engine.list_metric_ids`; the default surface now issues **zero** raw SQL, making the "delegates entirely to Stage 2" docs literally true (no rewording needed). |
| RISK-2 | MEDIUM | FR-001's "routes through the engine" guarantee was not automated — a future direct fact-read could pass shape-only tests. | Added `test_catalog_and_summary_tools_route_through_engine` (spies assert the tools delegate to the engine helpers). |

**Validation after remediation:** `uv run pytest -q` → 166 passed (was 159).
Pre-existing items unchanged from `master`: `mypy` `_query.py:277`, hrv-test `E501`s.

Docs/contract touched: `contracts/operator-entrypoint.yaml` (added `policy.enforcement`),
`README.md`, `docs/architecture/STAGES.md`, `docs/operations/STATUS.md`, `docs/adr/0004-stage3-operator-entrypoint.md`.

## Process lessons (also held in local auto-memory)

1. **Per-WP reviews miss cross-WP / FR-level contract gaps — and a documented
   divergence is still a divergence.** The WP02 cycle-1 reviewer *noticed* the
   FR-004 problem and then rationalized it away ("`list_metrics` can't receive an
   unknown id by construction, so document it"). "Architecturally unreachable" is
   a red flag, not a resolution: if an FR requires a behavior, make the path
   reachable rather than asserting the non-compliant behavior in a test. A test
   that locks in non-compliant behavior is worse than no test. Always run a
   mission-level review even when every WP was approved.

2. **The spec-kitty `review-cycle-N` counter over-counts rejections.** Each
   `move-task --to planned` invocation writes a new numbered feedback file, even
   on redundant re-runs — WP02 had one real rejection but `review-cycle-1..6.md`.
   The authoritative count of rejections is the `in_review → planned` transitions
   in `status.events.jsonl`, not the file count. Instruct review/fix agents to run
   `move-task` exactly once to keep the counter (and the 3-strike arbiter
   threshold) honest.
