# Spec: Cheap-operator live trial (parser path)

**Mission**: cheap-operator-live-trial-01KT6PSA
**Type**: software-dev
**Target branch**: master
**Status**: Draft

> **Where this sits.** Slice two of **issue #10** — the end-to-end agent
> acceptance sandbox / capability-tier sweep. Slice one (the merged session-log
> substrate) built and proved the log + sandbox + grader machinery with a *fake*
> scripted operator. This slice replaces the fake operator with a **real,
> deliberately cheap** one on the **parser-only path**, turning the seed harness
> `src/premura/harness/live_trial_ollama.py` into standing, repeatable local
> infrastructure. Plan basis: `docs/building/planning/agent-interaction-audit-substrate.md`,
> issue #10, and the run log `docs/history/audits/2026-06-03-live-trial-first-real-model-spike.md`.
>
> **Closes the named follow-up** the substrate deferred (D4 / R5 / SC-005): the
> real cheap-model operator/driver. It does **not** build issue #10 in full —
> see Scope.

## Why (motivation)

The doctrine bet is that Premura is *operable by agents*, including weak ones. The
only honest way to know is to measure the **capability floor**: how small a model
can still teach Premura to read an unfamiliar dump without fabricating. The
substrate can capture and grade such a run, but slice one only ever drove it with
a scripted stand-in. We need a real cheap operator wired in — and a place to keep
the result — so the floor can be measured and watched over time.

A first ad-hoc run (the audit log above) already proved two things this spec must
honour: (1) a cheap model needs a **feedback loop** or it cannot recover from its
own API mistakes; and (2) a feedback loop **only fixes what it checks** — a loop
that checks "does it load" but not honesty will happily ship a loadable-but-
dishonest parser. The honesty signal must stay with the independent grader, not
leak into the loop the operator can game.

## User scenarios & testing

Premura is agent-first: the actors here are agents, not humans.

### Primary scenario (agent measures the floor)

1. A maintaining/operating agent launches a live trial over the bundled synthetic
   Fitbit heart-rate fixture, naming a cheap operator model.
2. The operator model authors a parser into a throwaway sandbox; on failure it is
   handed its own failure and retries, up to a bounded attempt cap.
3. The existing machinery ingests via the parser and the **independent grader**
   recomputes the three-rule verdict (it loaded / runtime-valid / honest about
   gaps).
4. The harness persists the kept session log and verdict to a local runs
   directory and appends the outcome to a **capability-floor scoreboard** keyed by
   model identity.
5. The agent reads the scoreboard to report the current floor: which model tiers
   reach a passing verdict, and how that has shifted across runs.

### Retry scenario

The operator's first parser raises (e.g. a hallucinated constructor argument). The
loop feeds the failure back; a later attempt recovers and the run is recorded as
recovered-in-N attempts.

### Edge cases

- **Loadable-but-dishonest parser** *(the decisive case)*: the operator produces a
  parser that loads rows but silently drops an unmapped column. The loop's
  self-reconciliation catches the gap *only if the parser misdeclares its own
  columns*; if the operator declares dishonestly-consistently, the **grader**
  still FAILs `honest_about_gaps` against ground truth. The recorded honesty
  verdict is the grader's, never the loop's.
- **Model server unavailable**: the trial reports a clear "model not reachable"
  outcome and the default test suite stays green (the trial is never collected by
  default).
- **Operator never succeeds within the cap**: recorded as a FAIL verdict, not a
  crash; the scoreboard logs the failed attempt for that tier.
- **Pointed at real local data**: the run executes locally but persists nothing —
  no kept session log, no scoreboard entry, no extracted data in the repo.

## Requirements

### Functional

| ID | Requirement | Status |
| --- | --- | --- |
| FR-001 | A live trial drives a single, configurable **cheap operator model** to author a parser into a sandbox and runs it through the existing slice-one machinery to a grader verdict on the parser-only path. | Draft |
| FR-002 | On a failed attempt the operator **retries via a feedback loop** bounded by a configurable maximum number of attempts; each retry is given the prior attempt's failure to correct. | Draft |
| FR-003 | The feedback loop's in-loop honesty gate is **self-reconciliation only** — it verifies the parser's *own* behaviour (every source column it reads is either a declared metric or declared unmapped) and **must not expose the grading fixture's ground-truth field manifest** to the operator. | Draft |
| FR-004 | The **grader remains the sole authority** for the persisted honesty verdict; the loop's self-check neither substitutes for nor feeds the grader's ground-truth reconciliation. | Draft |
| FR-005 | Each run records the **operator and driver model identities** on the session so capability tiers can be compared later. | Draft |
| FR-006 | For a synthetic-fixture run, the harness **persists the kept session log and the grader verdict** to a local runs directory. | Draft |
| FR-007 | The system maintains a **capability-floor scoreboard** that accumulates each synthetic-fixture run's pass/fail outcome, attributed to its operator model identity, across runs over time. | Draft |
| FR-008 | The **driver** role is a fixed-goal stand-in for this slice (canned goal and answers); it records a driver model identity but does not invoke a frontier model. | Draft |
| FR-009 | A run is **launchable on demand by an agent** over the committed synthetic fixture, requiring no private data and no network beyond the local model server. | Draft |
| FR-010 | A run **reports, per attempt**, whether the self-reconciliation gate passed, the attempt count used, and the final three-rule grader verdict, for inspection. | Draft |
| FR-011 | The scoreboard is **readable to answer "what is the current capability floor"** — which model tiers currently reach a passing verdict and how that changed across runs. | Draft |
| FR-012 | When a run is pointed at **real local data**, it persists **nothing** — no kept session log, no scoreboard entry, no extracted data anywhere in the repo. | Draft |
| FR-013 | The substrate's previously-deferred real-operator / real-driver placeholders (D4 / R5) are **resolved** so the codebase reflects the follow-up as closed rather than a `NotImplementedError` stub. | Draft |

### Non-functional

| ID | Requirement | Status |
| --- | --- | --- |
| NFR-001 | **Never blocks CI.** The live trial is excluded from the default-collected test suite and no default-collected test invokes a model server; a missing, skipped, or failing live trial cannot fail the default suite. *Threshold:* default test collection deselects every live-trial test; a clean clone with no model server runs the default suite green. | Draft |
| NFR-002 | **PHI / data containment.** No code path syncs, uploads, or exports the session log off the local machine; real-data runs persist nothing to the repo, a commit, the runs directory, or the scoreboard. *Threshold:* the runs directory and scoreboard are git-ignored; a real-data run leaves zero new tracked or committed files. | Draft |
| NFR-003 | **Bounded cost.** A single run terminates within a configurable attempt cap (default ≤ 3 attempts) and a per-model-call timeout (default ≤ 300 s) so a wedged model cannot hang the run indefinitely. | Draft |
| NFR-004 | **Sole log-writer preserved.** The harness remains the only writer of the session log; the operator edits only the sandbox tree and never opens the session-log file. *Threshold:* no operator code path references the session-log store. | Draft |
| NFR-005 | **Scoreboard integrity.** Each scoreboard entry is attributable to one run (operator model identity, outcome, ordering) and an append never corrupts or drops prior entries. *Threshold:* N sequential runs yield N readable entries in order. | Draft |
| NFR-006 | **Reuse, don't fork.** The trial uses the slice-one sandbox, ingest runner, session-log store, and grader **unchanged**; it adds no second copy of that machinery. *Threshold:* no duplicated grader/runner/store logic is introduced. | Draft |

### Constraints

| ID | Constraint | Status |
| --- | --- | --- |
| C-001 | **Real data never committed.** Per `AGENTS.md`, real operator dumps / PHI / generated private artifacts never enter the repo or a git commit; only the synthetic fixture backs kept/committed artifacts. | Draft |
| C-002 | **Agent-first.** The trial is launched and consumed by an agent; the scoreboard is an agent/audit artifact, not a human dashboard or user-facing feature. No human-operated UI in this slice. | Draft |
| C-003 | **Local model backend.** The operator runs against a local model server (Ollama); the model is configurable. This slice does not commit to a multi-backend abstraction. | Draft |
| C-004 | **Never a CI gate.** The live trial is wired into no CI / pre-merge check, consistent with the substrate's never-block guarantee and issue #10's "periodic, never blocking" stance. | Draft |
| C-005 | **Independent judge.** The grading fixture's ground-truth field manifest is never shown to the operator at any point in the run. | Draft |

## Success criteria

- **SC-001** An agent can launch a live trial over the bundled synthetic data with
  a single command and receive a pass/fail verdict, supplying no private data.
- **SC-002** After a failed first attempt, the cheap operator is given its own
  failure and retries up to the attempt cap; a run that recovers is recorded as
  recovered-in-N.
- **SC-003** The honesty judgment in the recorded verdict is demonstrably produced
  *independently* of anything the operator saw — the operator never receives the
  fixture's ground-truth field list, yet the verdict still reflects true honesty.
- **SC-004** Every run is attributable to a specific operator and driver model
  identity.
- **SC-005** Running the trial repeatedly accumulates a scoreboard that shows, at
  any time, which model tiers currently reach a passing verdict (the capability
  floor) and how that has changed over runs.
- **SC-006** A run pointed at real local data leaves no trace in the repo, the
  kept runs directory, or the scoreboard.
- **SC-007** With no model server available, the default project test suite still
  passes (the live trial cannot block).

## Key entities

- **Live-trial run** — one operator attempt-sequence plus the independent grader
  verdict and the operator/driver model identities.
- **Operator (cheap model)** — authors a parser into the sandbox; subject to the
  self-reconciliation retry loop. **Driver** — fixed-goal stand-in supplying the
  goal and canned answers.
- **Self-reconciliation gate** — an in-loop, manifest-blind check of the parser's
  own column declarations; distinct from the grader.
- **Grader verdict** — the independent three-rule judgment (loaded / runtime-valid
  / honest-about-gaps) that is the sole recorded honesty authority.
- **Kept run record** — the persisted session log + verdict for a synthetic run.
- **Capability-floor scoreboard** — the accumulating, per-model-tier pass/fail
  record across runs.

## Scope

### In

- A real cheap operator + a fixed-goal driver wired into the existing live-trial
  seam, on the parser-only path over the synthetic fixture.
- A self-reconciliation retry loop (manifest-blind) with a bounded attempt cap.
- Single configurable model per run, recording operator/driver identities.
- Kept session log + verdict in a local git-ignored runs directory.
- A persisted capability-floor scoreboard accumulating per-tier outcomes.
- An agent-launchable entry point and a default-excluded (gated) test.
- Resolution of the deferred D4 / R5 placeholders.

### Out (deferred, not foreclosed)

- A **frontier-model driver** that improvises like a naive human (issue #10).
- **Multi-model sweep orchestration** + a comparison report in one invocation
  (this slice records identities so a sweep is *possible* later; it does not
  orchestrate one).
- The **full path** (install-from-docs → ingest a *novel* dump → answer health
  questions). This slice is parser-only over a committed fixture.
- **Persisting** anything from a real-dump run.
- A **multi-backend** model abstraction beyond the local server.
- Any **CI gating** of the live trial.
- Honesty-by-revealing-ground-truth to the operator.

## Assumptions

- A local model server (Ollama) is running with the chosen model pulled; the
  default operator model is the locally available cheap coder model.
- The slice-one synthetic fixture and its ground-truth field manifest are the
  committed data; the slice-one grader and machinery are stable and reused as-is.
- "Capability tier" is identified by the recorded model identity string; richer
  tier metadata (params, family) is out of scope for this slice.

## Dependencies

- The merged session-log substrate: the session-log store, the harness sandbox /
  ingest runner / grader, and the live-trial seam (`run_live_trial_with_log`).
- The seed harness `src/premura/harness/live_trial_ollama.py` (this slice
  hardens it into standing infra).
- A local model server (Ollama) and the committed synthetic fixture + manifest.
