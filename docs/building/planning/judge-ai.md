# Judge AI (session-log follow-on)

> Status: spec + plan for the `judge-ai` mission (overnight solo mission,
> branch `overnight/m3-judge-ai`). Named deferred follow-up in
> [ROADMAP.md](../../shared/ROADMAP.md) §session-log. Builds directly on the
> `conversation-turn-capture` mission
> ([spec](conversation-turn-capture.md)) and reads alongside ADR 0011 and the
> session-log writer contract.

## Why

The live-trial harness grades a run *mechanically*: the grader recomputes
`contract_pass` from warehouse facts, and the scoreboard records pass/fail.
Nothing evaluates the operator's *process* — whether the model worked toward
the goal, used its tools economically, recovered from failures, or claimed
things the grader facts contradict. The session log now holds everything
needed to judge that (steps, provenance, per-attempt telemetry, and — since
`conversation-turn-capture` — the full per-turn transcript), but nothing
reads it. The improvement hook (next mission) needs a structured, persisted
judgment to act on; today there is nothing to act on.

This mission adds an AI judge: a harness-side evaluator that assembles a
read-only dossier of a recorded session, asks a local model to assess it
against a bounded rubric, and persists the structured judgment back into the
session log through the same sole-writer surface.

## Scope (one sentence)

Add a judgment surface to the session-log store, a read-only session dossier,
and a rubric-driven local-model judge with an injectable transport, wired as
an opt-in post-run step of the live-trial harness — nothing else.

## Functional requirements

- **FR-1 (store surface).** `premura.session_log.store` gains a
  `record_judgment(conn, *, session_id, judge_model, rubric_version,
  status, criteria, overall_band=None, rationale=None, raw_output=None)`
  function writing one row to a new additive `log_judgment` table, plus two
  closed vocabularies enforced with `ValueError` at the boundary (same style
  as `TURN_ROLES`): `JUDGMENT_STATUSES = {complete, unparseable,
  model_unavailable}` and `CRITERION_BANDS = {strong, adequate, weak,
  not_applicable}`. `criteria` is a mapping of criterion id → `{band,
  rationale}` stored as JSON; every band value is validated against
  `CRITERION_BANDS`, but the criterion *ids* are not enumerated in code —
  they belong to the rubric (FR-3). `overall_band` uses the same band
  vocabulary. A judgment attempt is always recorded honestly: on
  `unparseable`/`model_unavailable`, `criteria` is empty, `raw_output`
  preserves what the model actually said (if anything), and `overall_band`
  is NULL. The rule for extending either vocabulary is the existing one:
  add the value to the set and extend the vocab test, in the store module
  only.
- **FR-2 (read-only dossier).** A `premura.session_log` read surface
  assembles one session into a judge-readable dossier: session metadata
  (models, run kind), the grader's recomputed facts (`contract_pass`, row
  counts), per-attempt telemetry, and the full transcript in `turn_index`
  order. It opens the log strictly read-only and exists so the judge (and
  the future improvement hook) never reach into tables ad hoc. A dossier for
  a session with no recorded turns says so explicitly rather than failing.
- **FR-3 (bounded rubric, a level above).** The judge's criteria live in a
  versioned rubric document packaged with the harness (precedent: the
  research-trace-audit skill's `AUDIT_RUBRIC.md`), with a small closed set
  of criterion categories — process honesty (claims vs. grader facts), goal
  adherence, tool-use economy, and failure recovery — **plus the explicit
  rule for adding a criterion**: a new criterion is added by editing the
  rubric (id, question, band anchors) and bumping `rubric_version`; no
  schema or store change is ever needed. Code never enumerates the criteria;
  it validates bands and records whatever criterion ids the rubric defined.
- **FR-4 (judge core).** `premura.harness` gains a `judge_session(...)`
  entry point that builds the prompt from dossier + rubric, calls a local
  model through an injectable transport seam (same pattern as the tool-loop
  `Transport`), parses the model's structured verdict, validates it (bands
  against `CRITERION_BANDS`, criterion ids against the rubric), retries a
  malformed response a bounded number of times, and persists exactly one
  `log_judgment` row per invocation with the honest `status`. The judge
  *evaluates* the grader's facts but can never alter them: `contract_pass`,
  the scoreboard, and the trial verdict are out of its write reach.
- **FR-5 (harness wiring, opt-in).** The live-trial harness gains an
  opt-in post-run judge step (config flag, default off) that runs after
  `finish_session` over the just-recorded session. Judge failure of any
  kind — model unavailable, unparseable output, a bug — must not change the
  trial verdict or raise out of the harness; it lands as an honest
  `log_judgment` status row (or, if even recording fails, a logged warning).

## Non-functional requirements

- **NFR-1 (sole writer holds).** Only the harness writes `log_judgment`.
  The judge is harness-side code and writes through `store.record_judgment`
  only. Pinned by extending the existing single-writer test.
- **NFR-2 (local-only PHI stance).** The dossier (and therefore the judge
  prompt) contains the full PHI-bearing transcript. The judge may only call
  a **local** model backend — the existing local-only enforcement of the
  live-trial seam carries over verbatim to the judge's transport. No code
  path syncs or exports the dossier, the prompt, or the judgment. Tests use
  synthetic fixtures only.
- **NFR-3 (no new dependency).** Stdlib transport, same as the existing
  Ollama paths; extends the existing no-new-third-party-dependency
  expectation.
- **NFR-4 (schema is additive).** `CREATE TABLE IF NOT EXISTS` only;
  `init_schema` stays idempotent against existing local files.
- **NFR-5 (offline CI).** Committed tests use a scripted transport — no
  Ollama, no network. Any real-model judge test is marked `live_trial` and
  excluded from CI, same as the existing seam tests.
- **NFR-6 (descriptive bands, no scores).** The judgment vocabulary is
  descriptive bands and rationales — no numeric scores, no pass/fail
  language that could be confused with the mechanical grader verdict.

## Out of scope

The improvement hook (next mission — it *consumes* judgments, nothing here
acts on one), the fixture auto-generator, the analyze-and-answer slice,
turn-level or per-step scoring, judging anything other than recorded
live-trial sessions, multi-model tournaments or judge ensembles, any cloud
or frontier model requirement, re-judging history migrations.

## Plan — work packages

- **WP1 — store surface + dossier.** `schema.sql` `log_judgment` table +
  `record_judgment` + the two vocabularies in `store.py`; the read-only
  dossier assembly; tests in `tests/test_session_log_store.py` style
  (round-trip, vocab rejection for status and bands, honest
  error-status rows with empty criteria, JSON criteria fidelity, idempotent
  re-init against a pre-existing file, single-writer extension, dossier
  ordering and no-turns case, dossier read-only).
- **WP2 — rubric + judge core.** The versioned rubric document (closed
  criterion categories + the add-a-criterion rule); prompt assembly;
  injectable transport; verdict parsing/validation with bounded retry;
  `judge_session(...)`; offline tests with a scripted transport (well-formed
  verdict persisted faithfully; malformed → bounded retry → `unparseable`
  row preserving `raw_output`; unavailable backend → `model_unavailable`
  row; unknown criterion id or band rejected; criteria ids come from the
  rubric, not code).
- **WP3 — harness wiring + docs.** Opt-in post-run judge step in the
  live-trial harness (default off; failure never flips the trial verdict —
  regression test); CHANGELOG entry; ROADMAP §session-log moves the judge
  AI from the still-deferred list to shipped wording (improvement hook et
  al. stay deferred).

One Opus implementer builds all three WPs in order on
`overnight/m3-judge-ai`, committing at green checkpoints with tests, then an
independent Opus review (must run `ruff check`, `ruff format --check`,
`mypy`, full `pytest`). Mission is green when all WPs pass and the review is
positive.

## Acceptance

An offline judge run (scripted transport) over a synthetic recorded session
leaves exactly one `log_judgment` row whose criteria replay the scripted
verdict under the rubric's criterion ids; a malformed-model run leaves an
honest `unparseable` row with the raw output preserved and an unchanged
trial verdict; a live-trial run with the judge flag off leaves zero
`log_judgment` rows; the full check suite is green.
