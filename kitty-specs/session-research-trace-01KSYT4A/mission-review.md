# Mission Review Report: `session-research-trace-01KSYT4A`

**Reviewer**: OpenCode / GPT-5.5  
**Date**: 2026-05-31  
**Mission**: `session-research-trace-01KSYT4A` — Session Research Trace and Multiplicity Disclosure  
**Baseline commit used**: `6391216`  
**Mission merge commit**: `b0e86be`  
**HEAD at review**: `3c496b406c7ed107178e789a0fcd9e87f3f20873`  
**WPs reviewed**: WP01..WP04

Meta note: `meta.json` does not include `baseline_merge_commit`, so I used `6391216` as the pre-implementation baseline visible in git history. All WPs are `done`.

Focused validation run during review: `uv run pytest tests/test_trace_store.py tests/test_mcp_trace_recording.py tests/test_mcp_trace_tools.py tests/test_trace_migration.py -q` -> **58 passed**.

---

## FR Coverage Matrix

| FR ID | Description | WP Owner | Test File(s) | Test Adequacy | Finding |
|---|---|---:|---|---|---|
| FR-001 | Open/identify research session | WP01/WP03 | `tests/test_trace_store.py`, `tests/test_mcp_trace_tools.py` | ADEQUATE | — |
| FR-002 | Record analytical invocations | WP01/WP03 | `tests/test_mcp_trace_recording.py`, `tests/test_trace_store.py` | PARTIAL | DRIFT-1 |
| FR-003 | Record at MCP boundary | WP03 | `tests/test_mcp_trace_recording.py` | ADEQUATE | — |
| FR-004 | Result refs/refusal reasons | WP01/WP03 | `tests/test_trace_store.py`, `tests/test_mcp_trace_recording.py` | PARTIAL | DRIFT-3 |
| FR-005 | Normalized hypothesis identity | WP02 | `tests/test_trace_store.py` | ADEQUATE | — |
| FR-006 | Compute N unique hypotheses | WP02 | `tests/test_trace_store.py`, `tests/test_mcp_trace_recording.py` | ADEQUATE | — |
| FR-007 | Refusals count toward N | WP02 | `tests/test_trace_store.py`, `tests/test_mcp_trace_recording.py` | ADEQUATE | — |
| FR-008 | Exclude retries/non-analytical/pre-question validation | WP02 | `tests/test_mcp_trace_recording.py` | PARTIAL | DRIFT-1 |
| FR-009 | Mark surfaced calls | WP02/WP03 | `tests/test_trace_store.py`, `tests/test_mcp_trace_tools.py` | PARTIAL | DRIFT-2 |
| FR-010 | Compute K from surfaced-marked calls | WP02/WP03 | `tests/test_trace_store.py` | PARTIAL | DRIFT-2 |
| FR-011 | Surfaced unavailable fallback | WP02 | `tests/test_trace_store.py`, `tests/test_mcp_trace_tools.py` | ADEQUATE | — |
| FR-012 | Read/export disclosure | WP02/WP03 | `tests/test_trace_store.py`, `tests/test_mcp_trace_tools.py` | ADEQUATE | — |
| FR-013 | Audit-consumer contract | WP04 | `contracts/audit-consumer-contract.md`, `tests/test_trace_store.py` | ADEQUATE | — |
| FR-014 | Generated exports, not canonical | WP02/WP04 | `tests/test_trace_store.py`, `tests/test_mcp_trace_tools.py` | ADEQUATE | — |
| FR-015 | Unknown session returns not-found | WP02/WP03 | `tests/test_trace_store.py`, `tests/test_mcp_trace_tools.py` | ADEQUATE | — |
| FR-016 | Live docs updated | WP04 | docs diff and status event review evidence | ADEQUATE | — |

---

## Drift Findings

### DRIFT-1: Pre-question validation failures are recorded and counted

**Type**: PUNTED-FR / LOCKED-COUNTING-SEMANTICS VIOLATION  
**Severity**: HIGH  
**Spec reference**: `FR-008`, `AS-3`

**Evidence**:

- `kitty-specs/session-research-trace-01KSYT4A/spec.md:80-83`: pre-question validation failures “MUST NOT count toward N or the raw analytical-call count.”
- `src/premura/mcp/entrypoint.py:132-140`: `_dispatch_analytical_with_trace` calls `trace.start_recorded_call(...)` before dispatch and, if recording starts, proceeds into dispatch.
- `src/premura/mcp/entrypoint.py:142-149`: if dispatch raises, it finalizes the already-started trace row as `terminal_status=error`.
- `src/premura/mcp/server.py:621-622`: empty `metric_id` raises `ValueError("metric_id must not be empty")`, which is caller-facing parameter validation before an analytical question reaches evidence/admissibility.
- `tests/test_mcp_trace_recording.py:165-180`: covers non-analytical exclusions, but only for `list_metrics` / `metric_summary`; it does not cover traced invalid analytical requests.
- Existing validation tests at `tests/test_mcp_analytical_tools.py:237-246` and `tests/test_mcp_correlate.py:285-298` cover invalid parameters without trace sessions, not their exclusion from trace counts.

**Analysis**:

The wrapper records before the validation that determines whether a request became a valid analytical question. For a traced `change_point(metric_id="  ", session_id=...)`, the trace row is created first, the server raises a validation `ValueError`, and the wrapper finalizes the row as `error`. That error row then contributes to raw call count and `N` because disclosure counts all `trace.tool_call` rows via `COUNT(*)` and `COUNT(DISTINCT hypothesis_identity)` in `src/premura/trace.py:879-890`.

This violates the spec’s explicit exclusion of “validation failures before a request becomes an analytical question.” It inflates the multiplicity denominator with malformed calls.

### DRIFT-2: Duplicate surfaced marks can make K exceed N

**Type**: NFR-MISS / COUNTING-INVARIANT VIOLATION  
**Severity**: HIGH  
**Spec reference**: `FR-009`, `FR-010`, `NFR-006`

**Evidence**:

- `kitty-specs/session-research-trace-01KSYT4A/spec.md:132-134`: K is “count of surfaced-marked calls.”
- `kitty-specs/session-research-trace-01KSYT4A/spec.md:149-150`: disclosure counts must satisfy `raw_calls ≥ N ≥ K` except when K is unavailable.
- `src/premura/store/migrations/005_trace_audit.sql:99-106`: `trace.surfaced_mark` has only `mark_id` as primary key; there is no uniqueness constraint on `call_id`, `(session_id, call_id)`, or `(session_id, call_id, role)`.
- `src/premura/trace.py:805-814`: `mark_surfaced(...)` always inserts a new mark row after same-session validation; it does not detect an existing mark for the same call.
- `src/premura/trace.py:953-969`: `_surfaced_summary` sets `count=len(marks)`, counting mark rows rather than distinct surfaced calls.
- `tests/test_trace_store.py:308-337`: tests two surfaced marks on two different calls; it does not test duplicate marks on the same call.

**Analysis**:

A single recorded analytical call can be marked surfaced twice with different rationales or roles. Disclosure then reports `K=2` for one unique hypothesis (`N=1`). That violates the required invariant `raw_calls ≥ N ≥ K` and misstates “user-facing findings” by counting mark rows, not surfaced calls.

This is not just an edge-case presentation issue. It breaks the core promise of the mission: the disclosure is supposed to be a measured, internally consistent search-effort summary.

### DRIFT-3: Completed call records can be finalized again and mutated

**Type**: NFR-MISS / APPEND-ONLY CONTRACT VIOLATION  
**Severity**: MEDIUM  
**Spec reference**: `NFR-003`, `FR-004`

**Evidence**:

- `kitty-specs/session-research-trace-01KSYT4A/spec.md:147`: the trace “MUST be append-only: no update or delete of a recorded call/result/mark in normal operation,” verified through public surface tests.
- `src/premura/trace.py:616-624`: `finish_recorded_call(...)` is a public trace service function.
- `src/premura/trace.py:655-668`: `finish_recorded_call(...)` performs `UPDATE trace.tool_call SET finished_at_utc = ?, terminal_status = ?, refusal_reason = ?, error_kind = ? WHERE call_id = ?`.
- There is no guard checking whether `finished_at_utc` or `terminal_status` was already set.
- `tests/test_trace_store.py:257-279`: tests refusal-reason and error recording, but does not test double-finalization or immutability of a completed call.

**Analysis**:

The implementation allows the same `PendingCall`/`call_id` to be finalized multiple times, changing terminal status and terminal metadata. If the second finalization is `available`, it can also append additional result references for the same call. This makes completed call records mutable through the public trace service.

The mission plan allowed an initial “start then finish” write shape, but the spec requires append-only behavior and public-surface immutability for recorded rows in normal operation. A second finalization should be rejected or otherwise made impossible.

---

## Risk Findings

### RISK-1: Invalid `session_id` runs analysis unrecorded

**Type**: BOUNDARY-CONDITION  
**Severity**: MEDIUM  
**Location**: `src/premura/mcp/entrypoint.py:132-140`  
**Trigger condition**: Agent passes a typo/expired/nonexistent `session_id` to an analytical tool.

**Evidence**:

- `src/premura/mcp/entrypoint.py:132-134`: start recording with supplied `session_id`.
- `src/premura/mcp/entrypoint.py:134-140`: if `start_recorded_call` returns `TraceError`, the wrapper still dispatches the analytical tool and attaches the trace error beside the result.
- `src/premura/trace.py:587-592`: unknown sessions return `TraceError(status="not_found")`.

**Analysis**:

The analytical result is still produced even though the requested trace session did not exist and no row was recorded. This is not silent in the response because a top-level `trace` error is attached, but it creates a sharp operational footgun: an agent intending to run a measured session can typo the session id and still get unmeasured results.

The spec only explicitly covers unknown sessions for disclosure/export, so I’m classifying this as a risk rather than a drift. Still, it weakens the “measured, not self-reported” safety rail in normal agent operation.

### RISK-2: Stale module docstring under-describes the actual MCP surface

**Type**: DOC-DRIFT / MAINTENANCE RISK  
**Severity**: LOW  
**Location**: `src/premura/mcp/entrypoint.py:5-9`

**Evidence**:

- `src/premura/mcp/entrypoint.py:5-9`: says default surface exposes catalog, summary, six signal tools, and “the two Stage 3 analytical tools (`change_point` / `smoothed_average`).”
- Actual code registers `correlate` at `src/premura/mcp/entrypoint.py:350-404`.
- Actual code registers three trace tools at `src/premura/mcp/entrypoint.py:458-520`.
- Live docs are correct: `docs/operations/STATUS.md:37-38` says default=16 and operator=17.

**Analysis**:

This does not break runtime behavior and live reference docs are accurate, but the module-level docstring is now stale. Future agents reading the code may undercount the surface or miss the trace tools.

---

## Silent Failure Candidates

| Location | Condition | Silent result | Spec impact |
|---|---|---|---|
| `src/premura/trace.py:545-562` | Warehouse fingerprint catalog query fails | Falls back to `duckdb-<version>-schema-noinv` | Weakens FR-001 reproducibility context, but non-blocking because session still carries a fingerprint string |
| `src/premura/mcp/entrypoint.py:134-140` | `session_id` not found while tracing analytical call | Runs analytical dispatch anyway with only wrapper `trace` error | Risk to measured-session integrity |
| `src/premura/trace.py:717-722` | Result is not a mapping or has no whitelisted summary keys | Stores no compact summary, only result hash | Acceptable under FR-004 because result hash remains the stable reference |

---

## Security Notes

| Finding | Location | Risk class | Recommendation |
|---|---|---|---|
| No blocking security finding | New mission code | N/A | New code adds no network/subprocess/auth path. SQL writes use parameter binding. Main integrity issues are trace-accounting bugs, not external security risks. |

---

## Final Verdict

**FAIL**

### Verdict rationale

The mission substantially implements the intended architecture: `trace.*` schema exists, `premura.trace` is MCP/engine-agnostic, trace tools are on the MCP surface, analytical envelopes remain trace-independent, and focused trace tests pass. However, two release-blocking fidelity issues remain. First, pre-question validation failures are recorded and counted, directly violating FR-008. Second, duplicate surfaced marks can make `K > N`, directly violating the core disclosure invariant in NFR-006 and corrupting the “K user-facing findings among N unique hypotheses examined” claim. A third medium issue allows completed calls to be re-finalized through the public trace API, weakening append-only audit integrity. These are not documentation nits; they affect the mission’s central measured-disclosure guarantee.

### Open items

- Fix FR-008 behavior so validation failures before an analytical request reaches data/admissibility do not create counted trace rows.
- Deduplicate or constrain surfaced marks so K counts distinct surfaced calls and cannot exceed N.
- Prevent double-finalization of recorded calls, or otherwise make completed call terminal metadata immutable.
- Decide whether invalid `session_id` should refuse analytical execution rather than returning unrecorded analytical results.
- Update `src/premura/mcp/entrypoint.py` module docstring to reflect 16 default tools, including `correlate` and trace tools.
