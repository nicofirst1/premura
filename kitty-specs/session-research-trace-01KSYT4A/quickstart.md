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

correlate(..., session_id="...")
change_point(..., session_id="...")
correlate(same request as before, session_id="...")

research_trace_mark_surfaced(session_id="...", call_id="...", role="summary", rationale="Used in the final answer as the main pattern found")

research_trace_disclosure(session_id="...")
-> "1 user-facing finding among 2 unique hypotheses examined" plus raw call count and refusals
```

Exact tool signatures may differ, but the behavior and fields in `contracts/mcp-trace-tools.md` must hold.

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

## Validation Commands

Run these before review handoff:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/premura
uv run pytest -q
```

If pre-existing failures appear outside the changed scope, call them out explicitly in the review handoff.
