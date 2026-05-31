# Quickstart: Session Research Trace and Multiplicity Disclosure

This quickstart describes the intended behavior for implementers and reviewers.

## Run The Mission Slice Locally

1. Open a trace session through the MCP boundary.
2. Run multiple analytical calls in that session, including exact retries and at least one refused call.
3. Mark one or more recorded calls as surfaced.
4. Request the session disclosure.
5. Verify the disclosure reports raw call count, unique hypothesis count, surfaced count or unavailable status, refusal breakdown, and stable call/result references.

## Expected Example Flow

```text
research_trace_open(client_label="opencode")
-> {"status": "opened", "session_id": "..."}

correlate(..., session_id="...")        # response carries a top-level `trace` object beside the engine envelope
change_point(..., session_id="...")
correlate(same request as before, session_id="...")   # exact retry: raw calls +1, N unchanged

research_trace_mark_surfaced(session_id="...", call_id="...", role="summary", rationale="Used in the final answer as the main pattern found")

research_trace_disclosure(session_id="...")
-> "1 user-facing findings among 2 unique hypotheses examined; raw analytical calls: 3" plus the refusal breakdown
```

As implemented: each analytical tool takes an optional `session_id` parameter; passing the id from `research_trace_open` records the call and attaches a top-level `trace` object (`session_id`/`call_id`/`terminal_status`/`result_id`) beside the unchanged engine envelope. With no `session_id`, the envelope is byte-identical and no trace row is written. The fields in `contracts/mcp-trace-tools.md` hold.

## Review Checklist

- The analytical engine has no trace imports and produces byte-identical envelopes with tracing on and off.
- Trace tables are under `trace.*`, not `hp.*`.
- Trace writes are append-only through the public surface.
- Exact retries increase raw calls but not `N`.
- Refused analytical calls count toward `N` and appear in the refusal breakdown.
- Non-analytical calls do not increase raw analytical calls or `N`.
- Missing surfaced marks produce surfaced `unavailable`, not `0` and not a guessed count.
- The disclosure never says `significant results` or frames `N` as statistical tests.
- The audit-consumer contract can derive all counts without parsing prose.

## Requirement → test coverage (validation map)

The shipped behavior is pinned by these tests (real names, in the lane worktree):

- **Raw analytical-call count vs unique hypotheses (N).** `tests/test_trace_store.py::test_exact_retry_increases_raw_not_n`, `::test_distinct_identities_increase_n`, `::test_hypothesis_identity_normalizes_defaults`, `::test_correlate_identity_is_direction_and_lag_sensitive`; at the MCP boundary `tests/test_mcp_trace_recording.py::test_exact_retry_increases_raw_but_not_unique`, `::test_distinct_hypotheses_increase_unique_count`.
- **Refusals count toward N and break down.** `tests/test_trace_store.py::test_refused_call_counts_and_breaks_down`, `::test_refused_call_requires_a_reason`; `tests/test_mcp_trace_recording.py::test_refused_analytical_call_is_recorded_and_counted`.
- **Surfaced unavailable fallback (no marks → unavailable, never a guessed 0).** `tests/test_trace_store.py::test_no_marks_surfaced_unavailable`, `::test_surfaced_marks_set_k_and_carry_roles`; `tests/test_mcp_trace_tools.py::test_disclosure_empty_session_is_available_not_found`; `tests/test_mcp_trace_tools.py::test_disclosure_never_says_significant_results`.
- **Engine purity (NFR-001) — byte-identical envelopes with tracing on vs off; no trace row without a session.** `tests/test_mcp_trace_recording.py::test_change_point_envelope_byte_identical_traced_vs_untraced`, `::test_correlate_envelope_byte_identical_traced_vs_untraced`, `::test_analytical_call_without_session_writes_no_trace_row`, `::test_list_metrics_and_metric_summary_are_not_recorded`.
- **`trace.*` / `hp.*` separation (NFR-002) — trace tables live only under `trace.*`, add no `hp.*` provenance tables, store no raw health rows.** `tests/test_trace_migration.py::test_trace_tables_are_only_under_trace_schema`, `::test_trace_migration_adds_no_new_hp_provenance_tables`, `::test_existing_hp_tables_survive`; `tests/test_trace_store.py::test_result_summary_never_stores_raw_health_series`.
- **MCP default / operator surfaces (trace tools on default; operator inherits + `query_warehouse`).** `tests/test_mcp_trace_tools.py::test_trace_tools_on_default_surface`, `::test_operator_surface_inherits_trace_tools_plus_query_warehouse`, `::test_disclosure_does_not_expose_query_warehouse_on_default_surface`; `tests/test_mcp_server.py::test_build_server_registers_expected_tools` / `::test_operator_server_registers_expected_tools` (default = 16 tools, operator = 17).
- **Audit-consumer contract is derivable without parsing prose.** `tests/test_trace_store.py::test_disclosure_call_references_satisfy_audit_contract`, `::test_json_and_markdown_exports`, `::test_no_self_reported_count_surface_exists`.

## Validation Commands

Run these before review handoff (from the lane worktree, against its own venv):

```bash
uv run --project . ruff check .
uv run --project . ruff format --check .
uv run --project . mypy src/premura
uv run --project . pytest -q
```

If pre-existing failures appear outside the changed scope, call them out explicitly in the review handoff.

### Recorded gate outcomes (WP04, 2026-05-31)

- `pytest -q`: **631 passed** (0 failures), incl. the full trace suite above.
- `ruff check .`: 12 errors — **all pre-existing and out of scope** (parser/engine/signal test files: `test_engine_correlate_contract.py`, `test_engine_policy_correlate.py`, `test_mcp_correlate.py`, `test_mcp_signal_tools.py`, `test_parsers/test_sleep_as_android.py`). Identical count on `master`; none in the trace files.
- `ruff format --check .`: would reformat 43 files. 40 of these are **pre-existing repo-wide drift** also present on `master`; the 3-file delta the trace mission added (`src/premura/trace.py`, `tests/test_trace_store.py`, `tests/test_trace_migration.py`) is **not `ruff format`-clean** — a real gate gap owned by the code WPs (WP01/WP02), not editable from this docs/validation WP.
- `mypy src/premura`: 14 errors — **all pre-existing and out of scope** (parsers `health_connect.py`/`garmin_gdpr.py`/`sleep_as_android.py`/`bmt.py`/`base.py`, `engine/_localtime.py` dateutil stubs, `engine/_query.py`). Identical count on `master`; none in `src/premura/trace.py` or `src/premura/mcp/entrypoint.py`.
