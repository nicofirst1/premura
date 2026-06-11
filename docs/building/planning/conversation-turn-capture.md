# Conversation-turn capture (session-log follow-on)

> Status: spec + plan for the `conversation-turn-capture` mission (overnight
> solo mission, branch `overnight/m2-conversation-turn-capture`). Named
> deferred follow-up in [ROADMAP.md](../../shared/ROADMAP.md) §session-log.
> Read alongside ADR 0011 and the session-log writer contract
> (`kitty-specs/session-log-substrate-01KT45S1/contracts/session-log-writer.md`).

## Why

The session log records the *shape* of a live-trial run (steps, provenance,
per-attempt telemetry) but not the *conversation*: the tool-loop operator's
chat history (`ToolLoopOperator._converse()`'s `messages` list) lives only in
Python memory and is discarded when the run ends. `STEP_KINDS` already names
`model_call`, but no code path records one. The judge-AI follow-on (next
mission) needs the actual turns to judge; today there is nothing to read.

This mission persists the per-turn transcript of a live-trial run into the
session log, through the existing sole-writer harness.

## Scope (one sentence)

Add a turn-capture surface to the session-log store and a transcript seam to
the live-trial harness so that any operator tier can expose its conversation
and the harness persists it — nothing else.

## Functional requirements

- **FR-1 (store surface).** `premura.session_log.store` gains a
  `record_turn(conn, *, session_id, step_id, turn_index, role, content,
  tool_name=None, model=None, token_count=None)` function writing one row to a
  new `log_turn` table, and a `TURN_ROLES` vocabulary
  `{system, user, assistant, tool}` enforced with `ValueError` at the
  boundary (same style as `RESULT_STATUSES`). `turn_index` is the 0-based
  position within the session's transcript; `(session_id, turn_index)` is
  unique. `step_id` is nullable and, when set, links the turn to the
  `log_step` node it occurred under (typically the root `agent_turn`).
  The vocabulary mirrors the chat-API role standard; the rule for extending
  it is the same as the existing vocabularies: add the value to the set and
  extend the vocab test, in the store module only.
- **FR-2 (transcript seam, a level above).** The live-trial seam defines a
  structural `TurnLike` protocol (`role: str`, `content: str`, optional
  `tool_name`, `model`, `token_count`) and an optional operator capability:
  an operator that exposes `transcript() -> Sequence[TurnLike]` after
  `operate()` gets its turns persisted by the harness. The harness detects
  the capability structurally (hasattr/protocol check) — no registry of
  tiers, no per-tier capture code. Operators without the capability behave
  exactly as today.
- **FR-3 (tool-loop tier feeds the seam).** `ToolLoopOperator` exposes its
  conversation history as `transcript()`, mapping its `messages` list 1:1 to
  `TurnLike` items (roles pass through; tool-result messages carry
  `tool_name`). The transcript reflects the *final* state of the
  conversation, including the system prompt and every assistant/tool turn.
- **FR-4 (one-shot tier feeds the seam).** The one-shot Ollama operator
  exposes its single prompt/response exchange as a two-turn transcript
  (`user` prompt turn, `assistant` response turn), so the judge AI reads
  every tier through the same surface.
- **FR-5 (harness persistence).** `_drive_live_trial` (the sole writer)
  persists the transcript after the run, under the run's root `agent_turn`
  step, in order, before `finish_session`. Capture failure on an otherwise
  successful run must not change the run verdict; it surfaces as a recorded
  `error`-status step, not an exception.

## Non-functional requirements

- **NFR-1 (sole writer holds).** Only the harness writes `log_turn`. No
  operator, sandbox, or ingest-subprocess code path may open the session-log
  file. Pinned by extending the existing single-writer test.
- **NFR-2 (local-only PHI stance).** `log_turn.content` stores full turn
  content (tool results may quote operator data — the session log is already
  the local, PHI-bearing store per ADR 0011). The existing invariant carries
  over verbatim: no code path syncs or exports the file. Tests use synthetic
  fixtures only; never commit real transcripts.
- **NFR-3 (no new dependency).** Extends the existing
  `test_no_new_third_party_dependency` expectation.
- **NFR-4 (schema is additive).** `schema.sql` change is `CREATE TABLE IF
  NOT EXISTS`; `init_schema` stays idempotent against existing local files.

## Out of scope

Judge AI (next mission), turn-level grading or scoring, capturing
mid-run/streaming (post-run flush is the v1 contract), token/latency
instrumentation beyond the optional nullable fields, any export or sync
surface, multi-model tournaments.

## Plan — work packages

- **WP1 — store surface.** `schema.sql` `log_turn` table + `record_turn` +
  `TURN_ROLES` in `store.py`; tests in `tests/test_session_log_store.py`
  style (round-trip, vocab rejection, uniqueness of
  `(session_id, turn_index)`, nullable `step_id`/optionals, idempotent
  re-init against a pre-existing file, single-writer extension).
- **WP2 — seam + tool-loop.** `TurnLike` protocol + structural capability
  detection + harness persistence in the live-trial seam; `transcript()` on
  `ToolLoopOperator`; tests with the injectable `ChatBackend` asserting the
  persisted rows match the conversation, plus a no-capability operator
  regression test and a capture-failure-does-not-flip-verdict test.
- **WP3 — one-shot tier + docs.** `transcript()` on the one-shot operator +
  its seam test; CHANGELOG entry; ROADMAP §session-log moves
  conversation-turn capture from the still-deferred list to shipped wording.

Each WP: Opus implementer commits at green checkpoints with tests, then an
independent Opus review (must run `ruff check`, `ruff format --check`,
`mypy`, full `pytest`). Mission is green when all three WPs pass on
`overnight/m2-conversation-turn-capture`.

## Acceptance

A live-trial run (offline, injectable backend) over the synthetic fixture
leaves `log_turn` rows that replay the full conversation in order, keyed to
the session and its root step; a run with a transcript-less operator leaves
zero `log_turn` rows and an unchanged verdict; the full check suite is green.
