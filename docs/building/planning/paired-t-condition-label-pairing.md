# Condition-label pairing for the paired-difference family — spec + plan

> Status: mission spec (overnight m8, 2026-06-12). Single source of truth for
> this mission. Authored by the orchestrator after recon of
> `src/premura/engine/CONTRACT.md`, `paired_t_test.py`, `paired_inputs.py`,
> ADR-0009, and `docs/shared/DOCTRINE.md`.

## Why

`docs/shared/ROADMAP.md` names the deferred item: *"`paired_t_test`'s broader
**condition-label pairing** (anchor-date pairing only ships now)"*. The engine
CONTRACT (§ deferred-extension rule) already prescribes what shipping it
requires: **a new pairing contract, new trace-identity fields, and new refusal
rules**, and forbids smuggling it into the simple anchor-date request shape.
This mission ships exactly that reviewed extension and nothing more.

## Stance (decisions binding on the implementation)

1. **The engine stays stateless, deterministic, offline.** Condition episodes
   are **caller-declared in the request** — the operating agent learns "on
   magnesium June 1–15, again July 3–10" from the operator and declares it,
   exactly as the anchor date is declared today. There is **no warehouse
   storage** of condition periods in this mission (named-deferred, below).
2. **A sibling registered tool, not a second shape inside `paired_t_test`.**
   The CONTRACT forbids extending the anchor-date request shape, and the
   `@analytical_tool` registration declares one `input_shape` and one
   `question_type` per tool. The capability lands as the sixth registered
   tool, `condition_paired_t_test`, built on a new prepared-input seam.
   `paired_t_test` itself is **not modified**.
3. **Condition labels are operator vocabulary, never a code enum.** The label
   is a non-empty string the operator chose ("on_magnesium",
   "post_surgery_rehab"). No condition list, no label registry, no validation
   against a vocabulary — guide, don't enumerate. The contract constrains the
   *shape* (one label per request, declared episodes, fixed pairing rule),
   not the *content*.
4. **Same honesty rules as the whole family.** No p-value, no confidence
   interval, no "significant", no causal language. Descriptive dispersion
   band only. Forbidden quantities refused **before** computation with
   `unsupported_parameter`, mirroring `correlate` and `paired_t_test`.
5. **No scanning.** One label, one declared episode set, one declared window
   pair, one declared expected direction per request. Lists of labels,
   candidate episode sets, or window lists are refusals, not iterations.
   Multiplicity across requests is the session trace's job (ADR-0009).

## The pairing contract (the ONE fixed documented rule)

Given a prepared series and a request
`(condition_label, episodes, before_days, after_days, expected_direction)`:

- An **episode** is a declared closed local-calendar-day range
  `[start_day, end_day]`, `end_day >= start_day`. Episodes must be declared
  explicitly and must not overlap one another (overlap = declaration error =
  refusal of the whole request).
- Each episode contributes **one pair**:
  - **off value** = mean of usable observations on days in
    `[start_day - before_days, start_day)` that fall **outside every declared
    episode**;
  - **on value** = mean of usable observations on days in
    `[start_day, min(start_day + after_days - 1, end_day)]`;
  - **difference = on − off** (the analog of after − before).
- Day keying and last-write-wins per local calendar day follow the existing
  `paired_inputs.py` conventions.
- An episode whose before-window intersects another declared episode, or that
  lacks at least one usable observation in either window, is **excluded with
  a per-episode disclosure** (episode start + machine-readable reason). No
  silent salvage, no invented values.
- The paired unit is the **episode**. Mean difference and the descriptive
  dispersion band are computed over the per-episode differences. Fewer than
  **2 usable episodes** after exclusions → refusal (dispersion undefined or
  meaningless below that).

## Functional requirements

- **FR-1 — contract vocabulary.** A new reviewed
  `AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE` value, plus the
  matching policy-layer `QuestionType` value and `QuestionRule` entries for
  exactly the metric families that allow `PAIRED_DIFFERENCE` today (same
  admissibility posture; no new family judgments invented tonight).
- **FR-2 — request/input shapes + preparation seam.** Frozen dataclasses
  `ConditionEpisode` and `ConditionLabelPairedRequest`, a prepared
  `ConditionLabelPairedInput`, and a
  `prepare_condition_label_paired_input(series, request)` seam in the
  paired-inputs module family, enforcing the pairing contract above and
  producing refusals (not exceptions) for contract violations, mirroring
  `prepare_before_after_paired_input`. Unknown kwargs (e.g. `anchor_date`,
  `p_value`, `labels=[...]`) must fail loudly, as the frozen-dataclass tests
  do today.
- **FR-3 — the tool.** `condition_paired_t_test` in its own engine module,
  registered via `@analytical_tool` with
  `question_type=CONDITION_PAIRED_DIFFERENCE`, a distinct `result_kind`,
  confound keys drawn ONLY from the existing closed `ConfoundKey` vocabulary
  (no new keys — reuse the `paired_t_test` set where semantics carry over),
  and `revision` starting at `"1"`. Estimate must report: mean difference,
  observed/expected direction + match flag, label echoed,
  `episode_count_declared`, `episode_count_used`, per-episode exclusions
  (start + reason), window parameters, method revision. Uncertainty payload:
  the descriptive dispersion band over per-episode differences with
  `interval_kind="descriptive_dispersion_band"`. Two required caveats,
  reworded for this contract: (a) describes the average on-vs-off difference
  across the operator's own declared labeled periods — the label is
  operator-declared, not a verified condition, and only splits the windows;
  (b) a difference and its spread, not a verdict — direction match is
  agreement with the declared expectation, nothing more.
- **FR-4 — registration surface.** Module appended to
  `_BUILTIN_ANALYTICAL_MODULES` and name to `_BUILTIN_ANALYTICAL_NAMES` in
  `engine/analytical.py`; the pinned public-surface test updates its expected
  set to six tools. New names re-exported from `premura.engine` alongside the
  existing prepared-input exports.
- **FR-5 — MCP exposure.** A thin wrapper in `mcp/server.py` (same pattern as
  the existing `paired_t_test` wrapper at its line ~672: prepare series from
  the warehouse, build the prepared input via the new seam, dispatch by name,
  return the envelope verbatim), registered in the entrypoint and `__all__`.
- **FR-6 — trace identity.** The tool declares its normalized hypothesis
  identity for the session research trace exactly the way `paired_t_test`
  declares its own (find and mirror that declaration): metric, label,
  episode ranges, windows, expected direction, method revision. ADR-0009
  anticipated these fields ("grouping/event, windows, contrast, params").
- **FR-7 — contract doc amendment.** `engine/CONTRACT.md`: the
  "exactly five tools" sentence becomes six; the deferred-extension paragraph
  is rewritten to describe the now-shipped condition-label pairing contract
  (this section's rule, refusals, and identity fields), keeping anchor-date
  `paired_t_test` unchanged and keeping all forbidden-quantity rules intact.
- **FR-8 — live-doc sync.** CHANGELOG entry (concise — m6's ~70-line entry
  was flagged as verbose); ROADMAP's deferred line updated (condition-label
  pairing shipped; remaining deferreds restated below); STATUS.md tool
  inventory updated (single-home rule: counts only there).

## Refusal classes (each refusal-reason distinct and tested)

R1 upstream-refused series propagates; R2 fewer than 2 episodes declared;
R3 overlapping declared episodes; R4 invalid episode (end before start) or
invalid windows (non-positive days) — at construction or as refusal,
mirroring the existing seam's split; R5 scan request (multiple labels /
candidate episode lists / window lists / p-value or significance request →
`unsupported_parameter`); R6 fewer than 2 usable episodes after exclusions;
R7 constant differences (dispersion degenerate); R8 stale evidence —
mirror the existing rule in `paired_t_test`. Refusals carry no estimate.

## Spec-named edge cases — each REQUIRES an end-to-end test

- **E1** Before-window contamination: 3 declared episodes where episode 2's
  before-window overlaps episode 1 → episode 2 excluded with disclosure,
  result computed from the other 2; the exclusion appears in the estimate.
- **E2** Exclusions drop usable below floor: 2 declared episodes, one has an
  empty on-window → refusal R6, and the refusal payload/disclosure names the
  exclusion that caused it.
- **E3** Scan attempt: a request carrying a list of labels (or a
  `p_value=True`-style kwarg at the MCP boundary) → `unsupported_parameter`
  refusal at the boundary, before any computation.
- **E4** Episode truncated by `after_days`: an episode longer than
  `after_days` uses only the first `after_days` on-days — verified
  numerically (the on-mean excludes later in-episode observations).

## Non-functional requirements

- **NFR-1** Determinism: byte-identical envelopes on repeated calls (existing
  test pattern). **NFR-2** Engine isolation: no network, no MCP import, no
  warehouse access from the engine module (existing test pattern).
- **NFR-3** Forbidden-language sweep over every string the tool can emit,
  reusing the `_FORBIDDEN_PATTERNS` family from `test_engine_paired_t_test.py`.
- **NFR-4** `paired_t_test.py` and `paired_inputs.py`'s existing public
  behavior byte-for-byte unchanged (new code lives in new modules/functions;
  shared helpers may be imported, not edited-in-place, unless a pure re-export
  is needed).

## Named-deferred (out of scope tonight, recorded in ROADMAP)

- Warehouse storage of condition periods (an intake/capture follow-up — needs
  its own agent-mediated capture design per DOCTRINE).
- Multi-label contrasts, episode auto-detection, any scanning.
- Broader significance-testing coverage (already deferred in ROADMAP).

## Plan (three WPs, sequential on this branch, /tdd each)

- **WP1 — contract + seam.** FR-1, FR-2, refusal classes R1–R6 at the seam
  level. Tests mirror `test_engine_before_after_pairs.py` patterns (incl.
  unknown-kwarg TypeErrors). Green checkpoint commit.
- **WP2 — the tool.** FR-3, FR-4, R7–R8, E1–E2, E4, NFR-1–NFR-4. Test family
  mirrors `test_engine_paired_t_test.py` (registration, dispatch, fields,
  determinism, refusals incl. ≥6 distinct reasons, forbidden-language sweep,
  confound flags, isolation) + updates the pinned six-tool surface test.
  Green checkpoint commit.
- **WP3 — exposure + docs.** FR-5, FR-6, FR-7, FR-8, E3 at the MCP boundary.
  MCP tests mirror `test_mcp_finished_tool_set.py` (delegation, verbatim
  envelope, refusal shape, boundary rejections). Green checkpoint commit.

Gates for conclusion: `uv run ruff check`, `uv run ruff format --check`,
`uv run mypy` (changed scope per CONTRIBUTING.md), `uv run pytest` — all
green on this branch, plus an independent review APPROVE.
