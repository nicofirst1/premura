# Design note (DRAFT): the session log — a loggable, testable, auditable substrate

> Status: **pre-spec exploration, realigned June 2026.** Not authoritative. This
> note captures the full shared understanding from the June 2026 grilling session
> about making Premura's runtime **fully loggable**, so that we can (1) test it
> end-to-end in a sandbox, (2) audit it for honesty, and (3) propose improvements
> back to the project. It records both the **whole vision** and the **deliberately
> thin first slice** we agreed to build first. No code decisions are locked; this
> exists so a future spec can start from shared language instead of re-deriving it.
>
> **Read this first:** the big vision is large; only **slice one** (§"Slice one —
> the exact line") is proposed for the next mission. Everything else is recorded so
> we do not lose it, and so the thin slice is built without foreclosing it.
>
> Companion reading: [`AGENTS.md`](../../../AGENTS.md) §"two rules",
> [`docs/shared/DOCTRINE.md`](../../shared/DOCTRINE.md),
> [`operating-agent-roles.md`](operating-agent-roles.md) (the orchestrator this
> log ultimately serves), [`docs/building/adr/0010-runtime-orchestrator-and-operating-roles.md`](../adr/0010-runtime-orchestrator-and-operating-roles.md),
> [`docs/building/architecture/STAGES.md`](../architecture/STAGES.md),
> [`research-trace-multiplicity-audit.md`](research-trace-multiplicity-audit.md),
> `src/premura/trace.py`, `src/premura/store/migrations/005_trace_audit.sql`,
> `src/premura/skills/parser-generator/`, `src/premura/parsers/CONTRACT.md`,
> issue #10 (end-to-end agent acceptance sandbox), issue #12 (adversarial
> narration eval).

## The realignment in one paragraph

There are **not** two separate efforts (a "capture substrate" and an
"orchestrator"). There is **one runtime — the orchestrator — and one rule that
runs through all of it: write down everything it does.** The written-down history
(the **session log**) is the foundation. The orchestrator is the eventual large
build; **loggability is a cross-cutting requirement baked in from day one**,
because without it none of testing, honesty-audit, or the improvement-hook is
possible. We will build the orchestrator over several slices. The **first slice
deliberately does not build the orchestrator** — it builds and proves the log +
sandbox + grader machinery around a single, bounded flow (building a parser),
which everything else later reuses.

## Why a session log exists — the three purposes

You cannot *grade* a run you cannot *capture*. Today Premura captures only a
narrow analytical-honesty ledger (the **research trace**), so an end-to-end run
leaves almost no record. The session log fills that gap and serves three goals:

1. **Testing end-to-end (the big one).** Make a throwaway copy of Premura in a
   temp folder. One AI plays "the human" (the **driver**). It spawns a *cheap,
   deliberately weak* AI to operate Premura. The driver hands over data and a
   goal, and we watch the whole thing play out start to finish. "End-to-end" has
   two shapes:
   - *Full path*: "here's my data → load it → analyze it → answer my question."
   - *Parser-only path*: "here's my data → build a parser for it → did it work?"
2. **Auditing for honesty.** The honesty rules we already ship (no fabrication,
   especially in analysis) can be checked *after the fact* against the log.
3. **End-of-session improvement hook.** When a real session ends, something
   reviews the log, writes possible improvements into the private JSON
   improvement queue, and asks the human: *"Want to help improve Premura? I can
   open an issue or a PR."*

This is an **audit/eval substrate, not a user feature.** It is explicitly **not** a
user-facing session-replay UI.

## Why a deliberately weak agent

The live trial should *start* with a **cheap, low-capability AI**, on purpose. A
weak agent surfaces the failures a strong one would paper over: if even a dim
agent cannot fabricate results or skip the honesty rules, the guardrails are
genuinely solid. (The schema already records `operator_model` / `driver_model`
so capability tiers can be compared later — issue #10's "capability-tier sweep".)

## Settled vocabulary

Plain-English names, chosen to satisfy `CONTEXT.md`'s no-jargon rule and to stay
distinct from the existing research trace. (These are now also in `CONTEXT.md`.)

- **Session log (new):** the general record of one operating session — every
  *step* the agent took — written to its own local file, consumed by audits and
  tests, never shown to the operating human. *(Old draft called this the
  "interaction audit substrate" / "audit store" — avoid.)*
- **Step:** one recorded unit of work in the session log (an agent turn, a model
  call, or a tool execution), shaped using the OpenTelemetry GenAI vocabulary.
  *(Old draft called this a "span" — avoid in prose.)*
- **Research trace (existing, unchanged):** the narrow, analytical-tools-only
  honesty ledger in `src/premura/trace.py`. Records the analytical tool calls and
  derives the *measured* multiplicity disclosure ("K findings among N
  hypotheses"). Strict, engine-pure, measured-not-self-reported contract.
- **Driver:** the AI that plays the human in a trial — supplies data and a goal,
  reacts to questions.
- **Repeatable check:** the test run with a *fake scripted agent* — same inputs,
  same result every time; safe to run on every code change.
- **Live trial:** the test run with a *real, cheap AI* operating Premura against
  real local data — realistic, different each run, occasional, **never blocks**
  code changes (matches issue #10: periodic, never blocking).
- **Sandbox:** a throwaway clone of Premura in a temp folder, with the warehouse
  and the session log pointed at temp files, torn down after the run.
- **Auto-grader:** the deterministic checker that reads **the session log** and
  returns pass/fail by the slice-one rules below.
- **Ingest provenance:** the Premura-internal facts about one ingest run that the
  harness cannot see — rows loaded, fields not mapped, rows skipped, and whether
  the parser met `parsers/CONTRACT.md`. Premura writes these into the log.

## One *raw capture*, not two — relationship to the orchestrator

`operating-agent-roles.md` (and ADR 0010) describe a runtime **orchestrator** that
routes a human's goal to bounded operating roles (`ingest`, `analysis`,
`human_facing`, `answer_audit`, `improvement_scan`) and "records every dispatch
and handoff" in a **compact** trace — explicitly *"compact references, not raw
health data"* (`operating-agent-roles.md` §"Traceability").

The intent of "one log, not two" is **one raw-capture mechanism** — we do not want
the orchestrator inventing a *second* rich capture beside this one. But the two
records have **different privacy contracts** and must not be conflated:

- **Session log (this note):** the full, rich, **PHI-bearing** capture (turns,
  tool calls, request/result summaries). **Local-only, never exported.**
- **Orchestrator handoff trace (`operating-agent-roles.md`):** a **compact,
  no-raw-health-data** record of role handoffs.

These are **not the same rows under the same contract.** The unresolved question —
deferred to when the orchestrator is specified — is whether the compact handoff
trace becomes a **projection/view over the session log** (compact fields derived
from the rich rows) or a **small sibling layer that references into it**. Either
way: the orchestrator's *rich* activity flows into the session log; its *compact*
handoff summary keeps its stricter contract. **Do not** fold either into the
research-trace tables. Slice one only needs to leave the log's shape general
enough to hold conversation turns and role-handoffs later — it does **not** decide
the projection-vs-sibling question, and `operating-agent-roles.md` must be aligned
with whatever that spec chooses.

## PROPOSED: parser-building at runtime (a contingent doctrine change)

> **Status: proposed, not settled.** This is the maintainer's *intended* direction
> from the June 2026 grilling, but it is **not yet a repo-wide decision** — the
> companion docs still say the opposite (below). Treat it as a contingent proposal
> until those docs are updated; do not write a spec that assumes it is settled.

The grilling surfaced a real tension. `DOCTRINE.md` and ADR 0010 currently say
parser extension is "not a runtime job" and "goes through review." The *proposed*
rule is:

> **At runtime:** if the human drops data Premura doesn't support, an agent builds
> a parser on the spot (using the `parser-generator` skill). **If it works, it
> works — it is used immediately, no reviewer needed.** A reviewer is only needed
> *later*, if the human chooses to **contribute that parser back** to the shared
> Premura project (the pull request).

In short, the proposal is: **build-and-use-now is allowed in a session;
keep-it-forever (a public PR) needs review** — the issue #10 thesis ("teach
Premura to read an unfamiliar dump") made concrete.

> **This is a real change to the runtime/dev-time boundary, not a wording nit.**
> It changes what runtime is allowed to do, so it directly contradicts three
> existing docs that currently place *all* codebase extension outside runtime:
>
> - `DOCTRINE.md` ("parser extension... goes through review"),
> - ADR 0010 (codebase extension is separate from runtime operation),
> - `operating-agent-roles.md` §"Dev-time boundary" (:23-27, :237-240): *"Parser
>   extension is not an operating role... the actual code change remains outside
>   the runtime orchestrator."*
>
> **The proposal is that runtime *may* build-and-use a parser; review gates only
> the public PR.** A spec author following the old docs would directly violate it,
> so the proposal **becomes a decision only when all three docs are updated
> together** in the same change. Until then it stays proposed: the spec that builds
> slice one must either carry that three-doc update or wait for it.
> (If the maintainer instead wants to keep the old boundary, this whole parser
> slice changes shape — flag it before spec-writing.)

Note that parser-building is *dev-time-shaped* work (writing code, running the
contract check) — the agent does it through file edits and the parser-generator
skill, **not** through Premura's MCP tools. This is why the log for a parser
session is mostly *ingest provenance* plus the harness's record of what the agent
did, **not** MCP tool-call steps.

## The session log — what it is and where it lives

- **A separate local file.** The session log is its own file, **never** the health
  warehouse file. Three reasons, all pointing the same way:
  1. *Privacy.* It will eventually hold the human's actual questions (sensitive),
     so "never sync, never upload" becomes one physical rule. **PHI-bearing →
     local-only, never exported.**
  2. *Sandbox isolation.* A separate file is trivial to point at a temp location
     and throw away.
  3. *A real bug it fixes.* DuckDB refuses two *concurrent* connections to one
     file, so `trace.py` currently does an open/close dance around every call
     (see `entrypoint.py`). A separate file removes *warehouse-vs-log* contention:
     the warehouse's read-only handle and the log's write handle are now different
     files.
- **Writes to the log are single-writer / serialized.** A separate file removes
  warehouse-vs-log contention, but it does **not** by itself license two
  *concurrent* writers to the log — that would just move the same problem onto the
  log file. Slice one keeps **one writer**: the **harness owns the session-log
  connection and is the sole writer.** Premura's ingest seam does **not** open the
  log itself — it *returns* its outcome (the loader's measured row counts, **plus**
  the parser-declared `unmapped_metrics` / `skipped_rows` that ride on
  `IngestBatch` — these are the parser's own metadata, **not** boundary-measured;
  see the source-of-truth table in §"Pass"), and the harness records that as a
  step. Concurrent log connections never occur. (When the orchestrator
  is built later, *it* becomes the single writer; the principle — one writer, or
  strictly serialized append phases — carries forward.)
- **OpenTelemetry GenAI *shape*, written by hand.** We adopt the OTel GenAI
  *vocabulary and tree shape* (a step tree: agent turn → model call → tool call,
  with standard attribute names) **but take no library and run no server.** We
  write plain rows into our own DuckDB file, exactly the idiom `trace.py` already
  uses.
  - *Why not use the OTel library?* Researched June 2026 (two web surveys). The
    library does not need a server (a ~20-line custom exporter can write to a
    file), **but** the libraries that auto-capture agent activity only hook the
    OpenAI/Anthropic *client SDKs* — they would **not** see Premura's own MCP
    tools, the agent editing files, or ingest provenance. So we instrument our own
    events by hand *either way*; the library buys us only async parent/child
    linking, which slice one (events recorded at single known points) does not
    need. The GenAI attribute names are also still "Development"-status and churn
    monthly. Hand-rolling matches `trace.py`, adds zero dependencies, and works
    offline in a sandbox.
  - *Why not a lighter library?* Surveyed (MLflow tracing, Logfire, Phoenix,
    Langfuse, AgentOps, Braintrust, Helicone, Lunary, Laminar, Lilypad, …). Every
    real alternative needs a running server, a cloud account, or a heavy
    multi-service stack; the one lighter option (`otel-file-exporter`) forces a
    clunky JSON format and loses DuckDB querying. **No lighter path exists.**
  - *Forecloses nothing.* If the future orchestrator's async agent loop ever makes
    the library worth it, drop in a small DuckDB exporter that writes into the
    *same* tables. Keep an "export to standard format" option as a future nicety.
  - *This decision deserves a short design-decision note* (`docs/building/adr/`)
    so it is not re-litigated.
- **The research trace is left exactly where it is.** Do **not** migrate the
  `trace.*` tables into the session log for slice one (or fold the two together).
  The research trace is engine-pure, measured, and contract-protected; keep two
  clean files side by side. Unifying them is an optional, much-later optimization.

## Testing is two layers

- **Repeatable check (always-on).** Build the machinery once — sandbox, log,
  auto-grader — and prove *it* works with a **fake scripted agent**. Same inputs,
  same result; runs on every code change.
- **Live trial (occasional).** Run a **cheap real AI** on top of the same
  machinery against real local data, to watch real behavior. Never a blocking
  gate.

So the *plumbing* is deterministic and CI-safe; the *real-AI trial* is periodic
and reuses that plumbing.

## Test input — synthetic fixtures, never real data

- **Real data is never committed.** Per `AGENTS.md`, real operator dumps / PHI
  never enter the repo or a commit.
- **Committed test input is a synthetic fixture:** a small file shaped like a real
  export (real column names, units, structure) with **made-up values**. This
  reuses the existing `CONTEXT.md` vocabulary ("sanitized source summary",
  "synthetic example").
- **The repeatable check bootstraps from the repo alone.** Slice one **commits a
  hand-authored synthetic fixture** — a tiny Fitbit-shaped file whose column names
  and units are *public* export structure (not PHI) and whose values are made up.
  The always-on repeatable check runs from this committed fixture, so **any
  contributor and CI can run it from a clean clone with no private dump and no
  prior live trial.** The real Fitbit dump and the auto-generator (below) are
  *additions* to this seed fixture, **never prerequisites for it.**
- **The Fitbit dump (`~/Downloads/MyFitbitData`)** is the chosen *real* target for
  the **live trial only** — run locally, never committed. It is a genuine
  unsupported target (Premura supports Garmin GDPR, Health Connect, Sleep as
  Android, BMT, lab PDFs — **not** Fitbit), and it is rich (12 categories, ~5,100
  CSVs, ~1,300 JSONs), which makes the honesty rail work hard: an honest parser
  maps what it can and **surfaces the rest as unmapped** rather than faking it.
- **Scope the trial to one category** (heart-rate suggested, since it lines up
  with the existing resting-HR analysis for the next slice) — *not* "parse all
  5,100 files."

### Synthetic-fixture auto-generation (the **next step**, not slice one)

A clean idea worth recording: once a parser works, use the *format it learned* to
emit a **fake-values version** of the file, which becomes the committed test
fixture. Flow: *real dump → live trial → working parser → derive a synthetic
sample → repeatable test uses the synthetic sample.* This avoids hand-authoring
fixtures and never commits real data — one rule instead of one fixture per vendor
("guide, don't enumerate").

- **Safety rule:** generate from the **structure only** (column names, types,
  plausible ranges), **never** by copying or statistically learning real values,
  so a "synthetic" file can never smuggle out real measurements.
- **Mechanics:** a parser reads vendor→canonical (one direction); emitting a fake
  file needs a tiny generator driven by the format the parser knows. The agent
  produces both during the trial (the parser + a small "make a sample like this"
  generator or format description).
- **Deferred:** turning "derive a clean synthetic fixture from any working parser"
  into a reusable capability is the next step. Note it would run *during a live
  trial*, which is local-only and **cannot** seed a CI fixture — which is exactly
  why slice one commits a hand-authored seed fixture (above) instead of depending
  on the trial's output.

## Slice one — the exact line

The smallest complete loop that proves the machinery, fully logged and gradeable.

### IN (what we build)

1. **The session log** — a separate local DuckDB file, OTel-shaped rows, written
   by hand. Holds:
   - *ingest provenance*, keyed to each ingest run. **Two origins, not one** — and
     the plan must not blur them (see §"Pass" for the source-of-truth table):
     - *loader-measured* (genuinely boundary-measured, ADR-0009 sense):
       `rows_inserted`, `rows_skipped_dup`, `rows_skipped_priority` from
       `LoadStats`; and the loader-enforced fact that every declared metric exists
       in `dim_metric.yaml` (the loader raises otherwise).
     - *parser-declared* (self-reported review metadata, **not** authoritative):
       `unmapped_metrics` / `skipped_rows` (today these live on `IngestBatch`,
       are produced by the parser, and are printed and discarded — we persist
       them, but as the parser's *claim*, not as truth).
   - *a simple record of what the agent did* during the parser build (the harness
     writes it — enough to follow along and reach a verdict; rich "where did it get
     stuck" analysis is a later audit over the same log).
2. **The sandbox + harness** — clone Premura to a throwaway folder, point the
   warehouse and the session log at temp files, run the trial, tear down.
3. **Two ways to drive it:** the *repeatable check* (fake scripted agent) and the
   *live trial* (cheap real AI against the real Fitbit dump, local, occasional).
4. **A deterministic auto-grader** that **recomputes** each grading rule from
   captured evidence plus the disposable sandbox warehouse — it never trusts a
   precomputed boolean for a rule it could check itself (see §"Pass" for the
   source-of-truth table).

### "Pass" — the runtime-validatable subset

The parser contract (`parsers/CONTRACT.md`) has **two tiers**, and slice one grades
only the runtime one. This mirrors the build-and-use-now vs. keep-it-forever rule
above.

**First, the source-of-truth table.** Not every fact is boundary-measured today —
the plan must be honest about which is which, or it bakes in a false guarantee.
Per the code (`store/loader.py`, `parsers/base.py`):

| Fact | Who produces it today | Authoritative? | How the grader gets a *trustworthy* value |
| --- | --- | --- | --- |
| `rows_inserted`, `rows_skipped_*` | loader (`LoadStats`) | **Yes** (boundary-measured) | read from log; cross-check vs. row counts in the sandbox warehouse |
| "declared metrics exist in `dim_metric`" | loader (raises if not) | **Yes** (boundary-enforced) | the ingest_run step's success/failure |
| `unmapped_metrics`, `skipped_rows` | **parser code** (review metadata on `IngestBatch`) | **No** — self-reported by the parser the agent just wrote | used only as the parser's *claim*; the verdict comes from reconciliation (below) |
| `declared_metrics`, emitted `metric_id`s | parser / the batch's rows | partial | **must be captured** so the grader recomputes "declared = emitted" itself |
| `contract_pass` | **nothing yet** — no checker exists in code | **No** | slice one must **build a minimal runtime checker**; the grader recomputes, not trusts |

The runtime-valid check, restated so each clause has a *trustworthy* source:

- **Graded here (recomputable by the grader):**
  - *rows actually loaded* — sandbox warehouse row count > 0 and consistent with
    logged `rows_inserted`.
  - *no `derived:` metric emitted* — scan the captured emitted `metric_id`s.
  - *`declared_metrics` = emitted `metric_id`s* — compare the two **captured** sets
    (so this must be persisted; see schema).
  - *declared metrics exist in `dim_metric`* — the ingest_run did not fail
    validation.
  - *parser loaded and produced a batch without raising* — this is what "implements
    the contract interface" reduces to at runtime; it is the ingest_run step's
    status, **not** a structural code inspection.
  - **honest about gaps (the reconciliation check, see below).**
- **NOT graded here (contribution review checklist, `CONTRACT.md` §"Reviewer
  checklist"):** the decision tree / standards-first order was followed; a
  fixture-driven test; a PR note per unmapped/skipped field; the same-PR ontology
  diff; clinically-standard aliases. *Why standards-first order is here:* there is
  no per-field record of which resolution step matched, so the grader cannot
  recompute it; the contract itself files it under the reviewer checklist
  (`CONTRACT.md:116`). Grading it later needs one more captured artifact — a
  **per-field resolution map** (each source field → resolved `metric_id` *and the
  rule that matched*) — out of scope for slice one.

So **`contract_pass` means "the grader recomputed the runtime-valid subset and it
held,"** never "the parser said so" and never "passed PR review."

**The honesty rule is graded by reconciliation, not by trusting the parser.** This
is the important correction: `unmapped_metrics` / `skipped_rows` are the parser's
*own* metadata, so a dishonest parser could simply omit a field it silently
dropped. The genuinely-measured check uses the **synthetic fixture as ground
truth** — *we* authored it, so we know its complete field set:

> A run is **honest about gaps** iff **every source field in the fixture** is
> accounted for: it either (a) became a canonical metric actually present in the
> sandbox warehouse, or (b) appears in the parser's declared `unmapped_metrics` /
> `skipped_rows`. **A source field that is neither loaded nor declared is a silent
> drop → fail.**

That reconciliation is computed by the grader from ground truth (fixture fields) +
boundary truth (warehouse contents) + the parser's claim — so the parser's claim
is *checked*, not *trusted*.

The three grading rules, then:

1. **It loaded** — recomputed from the sandbox warehouse.
2. **It met the runtime-valid subset** — recomputed as above.
3. **It was honest about gaps** — the reconciliation above.

**"Grade the log, not the warehouse" is a forcing function, not a blindfold.** The
rule forces *complete capture* (if it isn't captured, it can't be graded). It does
**not** forbid ground-truth checks: the grader reads the disposable sandbox
warehouse and the known fixture fields precisely so the verdict never rests on
self-report.

### OUT (deferred, not foreclosed)

- The **orchestrator** and its operating roles (the big runtime build).
- **Conversation-turn capture** (waits for the orchestrator; the log's shape
  leaves room for it).
- The **judge AI** that scores subtler honesty (slice one uses the deterministic
  grader only).
- The **improvement hook + JSON queue + "want to open a PR?"** flow.
- The **synthetic-fixture auto-generator** (the next step).
- The full **analyze-and-answer** path and its honesty audit (the *second* slice).

## OTel-shaped schema sketch (illustrative, not locked)

One `session` row per operating run; one `step` row per captured unit, parented
into a tree. Field names track the GenAI conventions where they exist; the
Premura-semantic provenance is recorded separately because the harness cannot see
it.

```
log_session(
  session_id, started_at, finished_at,
  operator_model, driver_model,            -- capability-tier comparison
  premura_version, isolation_tag,          -- sandbox run identity
  run_kind                                 -- repeatable_check | live_trial
)

log_step(
  step_id, session_id, parent_step_id,
  kind,                                     -- agent_turn | model_call | tool_call
  name,                                     -- e.g. gen_ai tool name
  tool_name, request_hash, request_summary, -- envelope, PHI-safe by default
  result_status,                            -- available | missing | stale |
                                            --   insufficient | refused | error
  result_hash, result_summary,
  started_at, finished_at
)

-- Ingest provenance. Mixed source-of-truth (see the §"Pass" table): the loader
-- counts are boundary-measured; the *_metrics_json fields are the parser's own
-- claim. Premura is the SOURCE; the harness WRITES them (single-writer rule).
-- The grader RECOMPUTES the verdict from these + the sandbox warehouse + the
-- fixture's known fields; it does not trust contract_pass as an input.
log_ingest_provenance(
  step_id, batch_id, parser_kind,
  rows_inserted, rows_skipped_dup, rows_skipped_priority,  -- loader-measured
  declared_metrics_json,                    -- captured so the grader can check
  emitted_metric_ids_json,                  --   "declared = emitted" itself
  unmapped_metrics_json,                    -- PARSER CLAIM (not authoritative)
  skipped_rows_json,                        -- PARSER CLAIM (not authoritative)
  contract_pass                             -- the GRADER's recomputed runtime
                                            --   subset result, written back;
                                            --   NOT a parser self-report, NOT
                                            --   the PR-review checklist
)
```

Note the source fields used by the honesty reconciliation are **not** stored here
— they come from the committed synthetic **fixture** (ground truth we authored),
compared against the sandbox warehouse contents at grade time. `contract_pass` is
the grader's *output*, persisted for the record, not an input it trusts.

**Representing dev-time work as steps (slice one).** The agent here mostly edits
files and runs checks rather than calling Premura's MCP tools, so those actions
are recorded as `tool_call` steps with explicit `tool_name`s — e.g. `edit_file`,
`run_tests`, `parser_contract_check`, `skill:parser-generator`, `ingest_run`. The
`tool_call` kind is general enough to hold them; what matters is the **named-tool
convention** (not a free-text blob), because later audits query by `tool_name` +
`kind`. The **verdict-bearing** step is `ingest_run`, whose detail lands in
`log_ingest_provenance`. (`parser_contract_check` exists only once slice one
builds the minimal runtime checker — there is no such checker in the code today.)

## Why this is doctrine-aligned

- **Guide, don't enumerate.** Capture is one rule ("every step is recorded"); the
  step shape is a *named external standard* (OTel GenAI), not a hand-rolled per-tool
  list; synthetic fixtures come from a *rule* (derive from a parser's known format),
  not a per-vendor list.
- **Agent-first.** The log exists so agents can test, audit, and improve agent
  operation; the human is the beneficiary, not the operator of a dashboard.
- **Honesty boundary preserved.** The measured research-trace contract is kept
  behind a clean seam (its own file), never diluted by general capture.

## Blocking decisions to settle *before* spec-writing

A reviewer flagged that the draft treated a few boundary decisions as settled
facts. These must be resolved (not just worded around) before this becomes a spec:

- **Runtime/dev-time boundary (proposed; must update three docs together).** The
  proposed "build-and-use a parser at runtime" rule contradicts `DOCTRINE.md`, ADR
  0010, **and** `operating-agent-roles.md` §"Dev-time boundary" as written. It is
  the maintainer's intended direction (runtime may build-and-use; review gates only
  the public PR) but stays **proposed until all three are updated in the same
  change.** If instead the old boundary holds, the parser slice changes shape —
  confirm before spec-writing.
- **Provenance source-of-truth (no false guarantee).** Per the §"Pass" table, only
  loader row counts and the `dim_metric` existence check are boundary-measured
  today; `unmapped_metrics` / `skipped_rows` are parser self-report and there is
  **no `contract_pass` checker in the code at all.** The spec must (a) capture
  `declared_metrics` + emitted `metric_id`s, (b) build a minimal runtime contract
  checker, and (c) grade honesty by **reconciliation against the fixture's known
  fields**, not by trusting the parser's metadata. Do not write the spec claiming
  these facts are already measured.
- **Orchestrator trace contract.** Decide whether the orchestrator's compact,
  no-raw-health handoff trace is a **projection over** the PHI-bearing session log
  or a **sibling layer referencing** it — and align `operating-agent-roles.md`. The
  two have different privacy contracts and must not be silently merged.

## Other open questions (resolve at spec time)

- **Conversation-turn capture mechanics.** How turns are recorded depends on the
  orchestrator surface in `operating-agent-roles.md` — defined later.
- **Retention / lifecycle.** For slice one the log lives in a throwaway sandbox, so
  retention is moot. For real runtime sessions later, the PHI-bearing log needs a
  purge policy.
- **CI graduation.** Whether any deterministic tier of the eventual audit becomes a
  hard CI gate, or all of it stays a periodic graded eval (issue #10's stance:
  periodic, never blocking). Slice one's repeatable check *can* run in CI; the live
  trial cannot.
