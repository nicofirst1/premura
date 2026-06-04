# Drift Audit — Usable Intake Dimensions task-planning risk review

> Method: [`docs/building/agents/implement-review-drift-audit.md`](../../building/agents/implement-review-drift-audit.md).
> This audit is run **pre-implementation / mid-mission** against the generated
> task artifacts for `usable-intake-dimensions-01KT950A`, because two task-level
> gaps look likely to admit drift later even if each WP is implemented and
> reviewed locally.

## Audited subject

| Field | Value |
|---|---|
| Mission | `usable-intake-dimensions-01KT950A` — Usable Intake Dimensions |
| Audit focus | Task decomposition + WP prompt coverage (pre-merge risk audit) |
| Reviewed HEAD | `952b105a569d349cf486f91b44999f63457dd5a3` |
| Artifacts audited | `spec.md`, `plan.md`, `data-model.md`, `contracts/`, `tasks.md`, all `tasks/WP*.md`, and the live code surfaces they target |
| Trigger | User request to check how the identified task-level drift risks could emerge and save the audit |

## Summary

Two drift risks stand out in the task artifacts:

1. **Parameterized intake signals have no owned runtime invocation path** on the
   current engine/MCP surfaces. WP04 and WP05 both assume caller-supplied
   `matcher` / `key` / `window_days` will flow through a "signal-backed tool"
   pattern that, in the live code, only supports zero-arg registered signals.
2. **WP02 requires intake-side unmapped-gap surfacing through metadata fields the
   shipped `IntakeBatch` seam does not currently have.** The tasks correctly want
   "unmapped source field declared as a gap" coverage, but the current parser
   surfaces that implement gap reporting (`unmapped_metrics`, `SkippedRow`) exist
   on `IngestBatch`, not on `IntakeBatch`.

Both are classic **between-the-scopes** risks: each WP could do a locally
reasonable thing and still drift because the contract edge between WPs and the
live runtime surfaces is not fully pinned.

## Unifying root cause

The task set is strong on **local intent** but still leaves two critical questions
to be resolved implicitly by implementers:

- *How do parameterized intake signal arguments actually get from the MCP tool
  boundary into the registered Stage 2 signal path the tasks say to reuse?*
- *Where does intake-side "gap surfaced honestly" metadata live on the real parser
  seam?*

Neither question is purely local to one file. They live **between** the mission
docs and the live runtime surfaces (`engine.compute`, `_run_signal`,
`IngestBatch` vs `IntakeBatch`). That is exactly the class of gap this audit
method is for.

---

## Finding 1 — Parameterized intake signals can drift because the current signal runtime path is zero-arg only

### 1. Introduction — where/how the gap entered

- The gap is introduced in the **task decomposition itself**, across **WP04** and
  **WP05**.
- WP04 requires two **parameterized** intake signals:
  `supplement_intake_adherence` with caller-supplied matcher + `window_days`, and
  `nutrition_intake_trend` with caller-supplied key + `window_days`
  (`tasks/WP04-intake-signals.md:58-60,64-77`).
- WP05 then says to expose them as thin MCP tools by following the existing
  signal-tool pattern in `mcp/server.py` (`tasks/WP05-mcp-intake-tools.md:39-49,
  56-63`).
- But the live runtime pattern they point at is:
  - `_run_signal(...)` -> `engine.compute(spec_name, conn)`
    (`src/premura/mcp/server.py:425-434`)
  - `engine.compute(...)` -> `spec.fn(conn)`
    (`src/premura/engine/__init__.py:353-374`)
- That path accepts **no signal arguments beyond the warehouse connection**. So the
  task prose currently asks later WPs to use a parameterized signal pattern that
  the live engine runtime does not yet provide.

This is not an implementer slip against a correct contract. The **task prompts
create the ambiguity** by naming the intended behavior but not the missing runtime
surface needed to make it possible.

### 2. Controls that should have fired

1. **Plan / data-model / contract design** should have pinned how parameterized
   intake signals are invoked.
2. **WP04 prompt** should have named the exact runtime surface for parameter flow.
3. **WP05 prompt** should have verified the "existing signal-tool pattern" it
   points at actually supports those parameters.
4. **Per-WP review** would re-run the author's tests, but only after an
   implementation choice had already been made.

### 3. Why each missed

- **Plan / data-model / contracts:** they correctly separate Stage 2 signal
  semantics from Stage 3 wrapper status, but they leave the invocation mechanism
  implicit. The planning docs say the signals are parameterized
  (`plan.md:66-73`; `contracts/intake-resolution-and-signals-contract.md:18-28`),
  but they do not name a concrete runtime surface such as "new parameterized
  compute entrypoint" or "direct helper functions outside the registry".
- **WP04 prompt:** it says "follow the parameterized-tool precedent
  (`correlate`)" (`tasks/WP04-intake-signals.md:58-60`), but `correlate` is not a
  registered Stage 2 signal run through `engine.compute`; it is an analytical-tool
  path with its own invocation surface. So the precedent is semantically similar
  but technically not the same runtime.
- **WP05 prompt:** it points at `_run_signal(...)` / `engine.compute(...)` as the
  existing pattern (`tasks/WP05-mcp-intake-tools.md:39-49`) even though that
  pattern currently only supports zero-arg registered signals. This invites a
  locally-correct-looking but globally-drifting implementation.
- **Per-WP review (future risk):** a reviewer can easily accept one of two
  locally green but mission-drifting outcomes:
  - the wrapper accepts `matcher` / `window_days` but the signal ignores them and
    behaves like a fixed-window signal with a caveat;
  - the wrapper bypasses the registered signal path ad hoc and calls a bespoke
    helper, so the mission "ships," but not via the reusable signal surface the
    tasks claimed.

### 4. The missing control

A **runtime-invocation ownership pin** for parameterized signal arguments,
firing at `/spec-kitty.tasks` and encoded in WP04/WP05:

- Name the concrete runtime surface by which `matcher` / `key` / `window_days`
  will reach the signal implementation.
- Make one WP own that surface explicitly, with a failing test that proves the
  parameter value actually changes the answer.
- In review, reject any implementation where the caller parameter is merely
  accepted and caveated away, or where WP05 silently bypasses the promised
  signal-runtime surface without a spec/contract amendment.

This is a **D5-style completeness** gap, but at the runtime-surface layer: the
task prose names the desired capability without pinning the concrete primitive
that can satisfy each clause.

### 5. Generalizable lesson → dimension

Mapped to **D5 — Gated-decision capability sufficiency**.

Why D5 fits:
- the tasks choose an **approach family** ("follow the existing signal-tool
  pattern") without proving that the chosen runtime primitive (`engine.compute` /
  `_run_signal`) covers the downstream clauses (parameterized caller inputs);
- the likely miss is that a missingness/fixed-window path still looks "handled"
  while the caller-parameter availability path is entirely absent.

### Evidence index

| Claim | Reference |
|---|---|
| WP04 says new intake signals are parameterized | `kitty-specs/usable-intake-dimensions-01KT950A/tasks/WP04-intake-signals.md:58-60,64-77` |
| WP05 says to follow existing signal-tool pattern | `kitty-specs/usable-intake-dimensions-01KT950A/tasks/WP05-mcp-intake-tools.md:39-49,56-63` |
| Existing signal-tool runtime path is `_run_signal -> engine.compute` | `src/premura/mcp/server.py:425-434` |
| `engine.compute` only calls `spec.fn(conn)` | `src/premura/engine/__init__.py:353-374` |
| Current built-in descriptive wrappers accept optional windows but do not thread them into Stage 2 compute | `src/premura/mcp/server.py:350-390` |
| Planning docs require parameterized intake signals | `kitty-specs/usable-intake-dimensions-01KT950A/plan.md:66-73`; `contracts/intake-resolution-and-signals-contract.md:18-28` |

---

## Finding 2 — Intake-side gap surfacing can drift because WP02 requires metadata the shipped `IntakeBatch` seam does not have

### 1. Introduction — where/how the gap entered

- The gap is introduced between **WP01**, **WP02**, and the shipped parser seam.
- WP02 correctly requires the reference parser to surface an **unmapped source
  field as a gap** and explicitly says the parser should declare unmapped fields as
  `unmapped_metrics` / `SkippedRow` rather than silently dropping them
  (`tasks/WP02-reference-intake-parser-and-fixtures.md:69-80`).
- The spec also requires that behavior for the reference parser edge case
  (`spec.md:70-72,95`).
- But the live parser seam is split:
  - `IngestBatch` carries `unmapped_metrics` and `skipped_rows`
    (`src/premura/parsers/base.py:327-347`)
  - `IntakeBatch` does **not** carry either surface
    (`src/premura/parsers/base.py:281-325`)
- The parser contract likewise documents gap-review metadata under `IngestBatch`
  while `IntakeBatch` only carries row/persistence fields
  (`src/premura/parsers/CONTRACT.md:52-82`).

So WP02 is asking for a correct honesty behavior against a metadata surface that
does not yet exist on the real intake seam.

### 2. Controls that should have fired

1. **Plan / data-model / parser-runtime contract** should have pinned where
   intake-side unmapped/skipped metadata lives.
2. **WP01** should have owned any necessary parser-seam expansion that WP02 needs.
3. **WP02 prompt** should have either targeted the live metadata surface or named
   the seam change it depends on.
4. **Per-WP review** would only see whatever local path the implementer chose.

### 3. Why each missed

- **Plan / data-model:** they correctly identify the need for honest gap
  surfacing in the fixture/parser proof, but they do not fully reconcile that need
  with the live intake type surface. The planning docs carry the *behavioral*
  requirement, but not the exact intake-side metadata contract needed to satisfy
  it.
- **WP01:** owns parser runtime support, but its prompt is scoped to output shape,
  call-site routing, and backward compatibility (`tasks/WP01-parser-runtime-intake-support.md:88-109`).
  It does not explicitly own "add intake-side gap metadata if WP02 needs it."
- **WP02 prompt:** names `unmapped_metrics` / `SkippedRow` directly
  (`tasks/WP02-reference-intake-parser-and-fixtures.md:69-80`) as if that surface
  already exists for intake. That makes the requirement look concrete while still
  leaving the real seam unresolved.
- **Per-WP review (future risk):** a reviewer could accept any of three locally
  reasonable but globally drifting fixes:
  - the parser silently drops the field because `IntakeBatch` has nowhere to put
    it;
  - the implementer invents an ad hoc intake-only notes/gap format not reflected
    in the contract;
  - the implementer routes intake parsing through observation-side metadata just
    to reuse `unmapped_metrics`, weakening the one-home rule.

### 4. The missing control

A **seam-capability pin** on the parser-side gap-reporting contract, firing in
WP01 before WP02 dispatches:

- If intake-side unmapped/skipped gap reporting is required by spec/fixtures,
  then the parser contract and runtime-support WP must explicitly define where that
  metadata lives for intake outputs.
- WP02 should depend on that named seam and assert it, rather than naming
  observation-side fields as if they already apply.

This is the same structural class as a D2 frozen-metadata risk, but more strongly
it is another **D5 coverage** miss: the tasks choose the approach "use the intake
seam" without pinning whether that seam can satisfy the honesty clause that the
next WP must implement.

### 5. Generalizable lesson → dimension

Mapped to **D5 — Gated-decision capability sufficiency**.

Why D5 fits:
- the gating/runtime-support WP chooses the parser/runtime path for intake, but
  the downstream FR clause "unmapped source field is declared as a gap" depends on
  metadata capability that path does not yet expose;
- the downstream WP can satisfy the obvious positive path (rows persist) while the
  honesty/gap-reporting clause remains unimplemented.

### Evidence index

| Claim | Reference |
|---|---|
| Spec edge case requires unmapped source field surfaced as a gap | `kitty-specs/usable-intake-dimensions-01KT950A/spec.md:70-72` |
| FR-008 requires reference parser + synthetic fixture proof | `kitty-specs/usable-intake-dimensions-01KT950A/spec.md:95` |
| WP02 requires unmapped fields surfaced via `unmapped_metrics` / `SkippedRow` | `kitty-specs/usable-intake-dimensions-01KT950A/tasks/WP02-reference-intake-parser-and-fixtures.md:69-80` |
| `IntakeBatch` has no `unmapped_metrics` / `skipped_rows` | `src/premura/parsers/base.py:281-325` |
| `IngestBatch` does have `unmapped_metrics` / `skipped_rows` | `src/premura/parsers/base.py:327-347` |
| Parser contract documents `IngestBatch` review metadata, but not equivalent `IntakeBatch` gap metadata | `src/premura/parsers/CONTRACT.md:52-82` |
| WP01 does not explicitly own intake-side gap metadata | `kitty-specs/usable-intake-dimensions-01KT950A/tasks/WP01-parser-runtime-intake-support.md:88-109` |

---

## Remediation status

| Item | Status |
|---|---|
| Parameterized intake signal invocation path explicitly owned and pinned | **OPEN** |
| Intake-side gap-reporting seam explicitly owned and pinned | **OPEN** |
| Durable control update | **OPEN** |

## Prevention — stop the class, not just this instance

1. **At `/spec-kitty.tasks`, require capability→primitive mapping whenever a task points to an existing runtime pattern.**
   If a WP says "follow the existing X pattern," it must also name the concrete
   primitive in live code and prove that primitive covers every downstream clause.
   If not, the task must explicitly own the missing runtime surface.

2. **When a downstream WP requires metadata on a seam, pin that metadata to the live seam before dispatch.**
   Do not let a downstream prompt name fields from a sibling seam by analogy.
   The upstream runtime/contract WP must either add the capability or the task
   set must amend the requirement.

3. **Strengthen review for task-generated prompts with a live-surface cross-check.**
   Before dispatching the first implementation WP, verify that every task's named
   runtime surface actually exists in the codebase with the required parameters /
   fields. This is a task-finalization review, not an implementer burden.

## Bottom line

These risks would not emerge because an implementer is careless. They would
emerge because the current task artifacts leave two cross-scope questions to be
resolved implicitly during implementation:

- *How do parameterized intake signal args reach the registered Stage 2 signal
  runtime?*
- *Where does intake-side gap-reporting metadata live on the real parser seam?*

If those are not pinned before or during implementation, locally green work can
still drift at mission level.
