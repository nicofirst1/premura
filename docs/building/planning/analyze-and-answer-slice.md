# Analyze-and-answer slice (graded analysis sessions over the session-log substrate)

> Status: spec + plan for the overnight m6 mission. Implements the
> "analyze-and-answer slice" named as deferred in
> [`docs/shared/ROADMAP.md`](../../shared/ROADMAP.md) (session-log section) and
> as "the *second* slice" in
> [`agent-interaction-audit-substrate.md`](agent-interaction-audit-substrate.md).
> Branch: `overnight/m6-analyze-and-answer` (from
> `overnight/m5-fixture-auto-generator`). Companion reading:
> [`DOCTRINE.md`](../../shared/DOCTRINE.md),
> [`STAGES.md`](../architecture/STAGES.md) (Stage 2/3 boundary),
> [`src/premura/engine/CONTRACT.md`](../../../src/premura/engine/CONTRACT.md)
> (no p-values, no "significant", descriptive bands, first-class refusals),
> `src/premura/harness/JUDGE_RUBRIC.md` and
> `src/premura/harness/IMPROVEMENT_PLAYBOOK.md` (their add rules), and the m5
> generator (`src/premura/harness/fixture_gen.py`).

## Why

The acceptance harness today grades exactly one task shape: "build an honest
parser." The product's actual end-to-end promise is "here's my data → load it
→ analyze it → answer my question," and nothing yet exercises — or audits —
the second half. This slice teaches the harness a second task kind: the
operator is given a deterministically seeded warehouse and a question, must
reach the data **only through the engine's analytical surfaces**, and must
return an answer that a deterministic grader can verify for honesty (no
forbidden statistical claims, per the engine contract) and grounding (the
numbers actually came from the tools). Everything is captured in the session
log through the existing sole-writer surfaces, so judged and improvable like
parser sessions.

## Scope (one sentence)

A deterministic, offline, graded analyze-and-answer task for the harness: a
question-kind registry with one worked kind, a structured `AnswerOutcome`, a
deterministic answer grader (honesty scan + grounding + refusal fidelity), a
harness seam that seeds a synthetic sandbox warehouse and runs an
`AnswerOperator` against a bounded engine-backed tool surface with full
session-log capture, scripted honest/dishonest reference operators, a judge
rubric + playbook extension via their own add rules, and a
`python -m premura.harness.answer_task` offline runner — the real-model
(Ollama) analyze operator and cross-session aggregation stay named-deferred.

## Functional requirements

- **FR-1 (question-kind registry, a level above).** A new
  `src/premura/harness/answer_task.py` defines `QuestionSpec` — id, human
  question text rendering, deterministic ground-truth computation (which
  registered engine analytical surface to call and with what canonical
  parameters), and a tolerance rule for grounding — behind a small registry
  keyed by question-kind id with a documented add-a-kind rule (module
  docstring), mirroring the drawer-strategy registry from m5. Tonight exactly
  one kind is implemented, exercising one registered engine analytical tool
  over a metric **selected deterministically from the seeded warehouse** (never
  a metric id hardcoded in code). An unknown question-kind id fails loudly.
- **FR-2 (structured answer).** `AnswerOutcome` carries the final answer text,
  the claimed estimate(s) as structured values, and tool-call provenance
  (which surface calls the operator made, with parameters). The grader checks
  grounding against the structured claims — it never parses numbers out of
  free text; the text is scanned only for forbidden claims. An operator that
  refuses carries a structured refusal (reason included) instead of estimates.
- **FR-3 (deterministic answer grader).** `grade_answer(...)` recomputes
  ground truth itself through the same engine surface (never trusting the
  operator's tool-call report) and returns a structured verdict from three
  checks: **honesty** — no forbidden statistical claims in the answer text,
  driven by a forbidden-claims pattern registry (p-values, "significant"/
  significance, causal language, population-norm comparisons — sourced from
  the engine contract's prohibitions) with a documented add-a-pattern rule;
  **grounding** — claimed estimates match the grader's recomputation within
  the question kind's tolerance rule; **refusal fidelity** — when the engine
  itself refuses (e.g. insufficient data), only an answer that mirrors that
  refusal passes, and when the engine computes a result, a refusal-shaped
  answer fails. Each failed check names itself precisely in the verdict.
- **FR-4 (harness seam).** A `run_answer_trial(...)` entry seeds a sandbox
  warehouse deterministically from a seed (reusing `fixture_gen` plus the
  existing ingest machinery where practical — synthetic by construction),
  renders the question, hands the operator a **bounded tool surface** that
  wraps the engine's registered analytical surfaces over that sandbox
  warehouse — the operator never receives a connection, path, or raw SQL —
  collects the `AnswerOutcome`, grades it, and reports a structured trial
  result. `AnswerOperator` is a small protocol; tonight ships a scripted
  honest reference operator (drives the real tool surface, answers from its
  results) and a scripted dishonest contrast operator (fabricates and/or emits
  forbidden claims) for tests.
- **FR-5 (session-log capture + scoreboard).** The trial records through the
  existing sole-writer store surfaces only: a session row, the question and
  answer as turns/steps, and the graded outcome, so `build_dossier` shows the
  full exchange. The result persists to the scoreboard under the existing
  open tier axis with an analyze-task tier value, marked synthetic (the
  seeded warehouse is synthetic by construction). No session-log schema change
  is expected; if one proves genuinely necessary it must be additive and
  flagged as a deviation.
- **FR-6 (rubric + playbook extension by their own rules).** Extend
  `JUDGE_RUBRIC.md` with analytical-honesty coverage following the rubric's
  own add rule and versioning convention, and `IMPROVEMENT_PLAYBOOK.md` with
  the matching area per its add-an-area rule. Because criterion ids are
  rubric-owned and never appear in code, this must require **no engine, judge,
  or scan code edits** — a test (or the reviewer) confirms the rubric/playbook
  parsers accept the extended documents unchanged.
- **FR-7 (CLI entry).** `python -m premura.harness.answer_task --seed N
  [--question-kind K]` runs the offline trial end to end with the scripted
  honest operator against a temp sandbox, prints a one-line summary (question
  kind, metric, verdict with per-check results), and exits nonzero on any
  failure, mirroring the m5 CLI pattern.

## Non-functional requirements

- **NFR-1 (boundary fidelity).** The Stage 2/3 boundary and engine contract
  are respected, not re-implemented: analysis happens only by calling the
  engine's registered surfaces; the harness adds no analytical computation of
  its own beyond invoking them; nothing in this slice computes or emits a
  p-value, significance claim, or population norm; existing engine guards are
  not weakened or bypassed.
- **NFR-2 (no new dependencies).** No new third-party packages
  (`test_no_new_third_party_dependency` stays green).
- **NFR-3 (no default-path behavior change).** Existing harness runs, parser
  trials, session-log consumers, and tests are unaffected; the sole-writer
  invariant on the session log is preserved; the new task runs only when
  explicitly invoked.
- **NFR-4 (altitude).** Question kinds, forbidden-claim patterns, and
  improvement areas are registries/documents with add rules — no enumerated
  question lists in code, no hardcoded metric ids, no `if kind == ...`
  ladders outside the registry seam.
- **NFR-5 (offline deterministic tests).** All tests run in the default suite
  (no `live_trial` marker, no Ollama, no network); the same seed yields the
  same seeded warehouse, question, ground truth, and verdict.

## Spec-named edge cases (each needs an end-to-end test)

1. **Dishonest claim** — the contrast operator's answer contains a forbidden
   claim (e.g. "significant"): honesty check fails, trial fails.
2. **Ungrounded number** — the contrast operator claims an estimate the engine
   never produced: grounding check fails, trial fails.
3. **Engine refusal, honest mirror** — a seed/spec whose data makes the engine
   refuse: the honest operator mirrors the refusal and the trial **passes**;
   a fabricated estimate on the same data fails.
4. **Unwarranted refusal** — the operator refuses although the engine
   computes a result: refusal-fidelity check fails, trial fails.

## Out of scope

The real-model (Ollama) analyze operator and its prompt/tool-loop work, any
MCP exposure of the session log, cross-session trend aggregation, multi-turn
or multi-question sessions, natural-language question parsing, model-generated
answer prose, acting on improvement proposals, and new analytical tools in the
engine — all stay named-deferred in ROADMAP.md.

## Plan — work packages

- **WP1 — contract + grader core (FR-1, FR-2, FR-3).** `QuestionSpec`,
  registry + one worked kind, `AnswerOutcome`, forbidden-claims registry,
  `grade_answer`; tests in `tests/test_answer_task.py`: honest answer passes,
  each edge case above at the grader level, unknown kind fails loudly,
  grader recomputes (a poisoned tool-call report does not fool it),
  determinism.
- **WP2 — seam + capture (FR-4, FR-5).** Sandbox seeding from `fixture_gen` +
  ingest, bounded tool surface, `AnswerOperator` protocol + both scripted
  operators, session-log capture, scoreboard persistence; end-to-end tests
  for the honest pass and all four spec-named edge cases through
  `run_answer_trial`, dossier shows the exchange, sole-writer test stays
  green.
- **WP3 — rubric/playbook + CLI + doc sync (FR-6, FR-7).** Rubric and
  playbook extensions per their own add rules with the no-code-edit proof;
  `_main()` with honest exit codes; CHANGELOG entry; ROADMAP/STATUS updated so
  the analyze-and-answer slice moves to shipped with the remaining deferrals
  (real-model analyze operator, cross-session aggregation) still named.

One Opus implementation agent builds all three WPs in order on this branch,
test-first (`/tdd`), committing at each green checkpoint; an independent Opus
reviewer then verifies FR/NFR coverage and runs all four gates (`ruff check`,
`ruff format --check`, changed-scope `mypy`, full `pytest`).

## Acceptance

On `overnight/m6-analyze-and-answer`: all four gates green; an end-to-end test
proves seed in → seeded sandbox warehouse → question rendered → scripted
honest operator answers through the bounded engine surface → grader passes →
session log holds the exchange → scoreboard entry written, plus failing
end-to-end paths for all four spec-named edge cases; with the new task never
invoked, the existing parser-trial and session-log tests pass unchanged.
