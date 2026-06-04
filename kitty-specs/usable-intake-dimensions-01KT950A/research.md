# Phase 0 Research: Usable Intake Dimensions

This research resolves the open architectural questions before work-package
generation. The dominant lesson from the recent drift audits is that planning has
to settle the cross-surface contracts now, not let implementation improvise them.

## D1 — Runtime intake parser support must be a real protocol/runtime change, not a skill-only doc update

- **Decision**: This mission must update the authoritative parser contract and
  runtime invocation path together, not just the parser-generator skill.
  Specifically, the mission needs a first-class parser output shape that can
  carry intake, plus runtime code that knows how to persist that output.
- **Rationale**: `src/premura/parsers/CONTRACT.md` already documents two seams
  (`IngestBatch` and `IntakeBatch`), but the actual parser protocol in
  `src/premura/parsers/base.py` still says `parse(path) -> IngestBatch`, and
  runtime call sites like `src/premura/cli.py` and
  `src/premura/harness/ingest_runner.py` only know the observation loader path.
  A skill-only update would create a contract mismatch and guarantee drift.
- **Alternatives considered**:
  - Leave runtime parser support unchanged and only document intake in the skill:
    rejected because it would make SC-004 false in practice.
  - Add a second intake-only parser mechanism beside the current protocol:
    rejected because it duplicates the parser surface and weakens the one-home
    rule.

## D2 — Parser/runtime support must cover intake-first sources without overcommitting the exact return shape

- **Decision**: The parser contract/runtime path must support observation-only and
  intake-only parser outputs as first-class cases, while keeping the two
  persistence seams distinct. The exact returned object shape should be chosen in
  implementation design using the smallest viable change, and should not
  structurally foreclose mixed observation+intake support when a source genuinely
  carries both.
- **Rationale**: The contract already says one source may genuinely contain both
  observation and intake data. The planning requirement is therefore not "replace
  `IngestBatch` with `IntakeBatch`" and not yet "commit to one wrapper object,"
  but "make intake output a first-class supported runtime case and route each
  output to the correct persistence seam." That keeps one-home separation intact
  without forcing a larger object design earlier than necessary.
- **Alternatives considered**:
  - Permit `parse()` to return either `IngestBatch` or `IntakeBatch` only:
    possibly workable as the smallest first step, but it needs careful review if
    mixed sources must be supported on the same runtime path later.
  - Force separate parsers per seam for one source: rejected because it would
    duplicate artifact parsing and make runtime build-and-use clumsier.

## D3 — Keep intake resolver payloads domain-generic; signal policy lives above them

- **Decision**: Each intake resolver should return a generic resolved payload for
  one declared key/matcher plus honest availability context, not a signal-shaped
  answer. Signals remain the place that interpret coverage, trend direction,
  caveats, and insufficiency.
- **Rationale**: The input-resolution seam is domain-aware resolution of declared
  inputs, not a universal answer layer. BMI already proves the pattern: the
  resolver gives declared inputs, while the signal owns answer semantics. Doing
  the same for intake preserves the seam's role and keeps future intake signals
  possible.
- **Alternatives considered**:
  - Make resolvers compute adherence/trend semantics: rejected because it would
    collapse Stage 2 layers and overfit the resolver to one consumer.
  - Return raw SQL rows only: rejected because it would leak storage shape upward
    and weaken the meaning contract.

## D4 — Generic day-one signal inputs: caller-declared keys/matchers, bounded windows, no fixed product list

- **Decision**: Both new signals stay generic in v1:
  - the nutrition signal accepts a caller-declared nutrition quantity key within
    `nutrition_intake`;
  - the supplement signal accepts a caller-declared supplement matcher over the
    stored supplement item labels/product/ingredient shape;
  - both accept bounded caller-supplied windows with repo defaults.
- **Rationale**: This matches the spec's altitude rule and avoids turning the
  first implementation into product policy via a tiny allowlist. It also makes
  FR-009 real: the next intake dimension follows the rule instead of extending a
  baked-in switch statement.
- **Alternatives considered**:
  - Hardcode a small nutrient/supplement subset: rejected because it violates the
    mission's level-above intent and would make the recommendation note less
    meaningful.

## D5 — Positive-path fixtures are required for every intake "when available" clause

- **Decision**: Each intake signal and MCP wrapper must ship a positive-path
  fixture where the requested intake data is present and the answer is surfaced,
  separate from the missing/stale/empty-domain fixtures.
- **Rationale**: This directly applies the D5 drift lesson from the PubMed audit.
  A missingness-only suite would let an always-empty or always-refused intake path
  look compliant.
- **Alternatives considered**:
  - Rely on missing/stale refusal tests plus one smoke test: rejected because it
    would not prove the availability half of the contract.

## D6 — Temporal basis must be local-calendar-day when available, and the fixture set must cross midnight

- **Decision**: Intake freshness/day/window semantics use local calendar day from
  the event timestamp plus `local_tz` when present; otherwise they fall back to
  Premura's existing naive-UTC convention. At least one acceptance fixture must
  cross local midnight so local day and UTC date differ.
- **Rationale**: This directly applies the D4 drift lesson. Intake questions like
  "logged on K of last N days" and "recent trend" are inherently day-basis
  answers; if compute and reported metadata derive from different bases, the
  answer becomes dishonest while still looking plausible.
- **Alternatives considered**:
  - Use UTC date everywhere: rejected because the warehouse already carries
    `local_tz` on intake events and the mission's user-facing semantics are about
    the operator's local logging days.
  - Leave the basis implicit: rejected because that is exactly how the earlier
    report-basis drift got through.

## D7 — The recommendation note is a deferred-abstraction decision, not a vague future-work paragraph

- **Decision**: The mission's final recommendation artifact must explicitly answer
  three things: whether a dedicated intake-dimension contract is needed now,
  what sketch it would take if built later, and what trigger condition would make
  it worth doing.
- **Rationale**: FR-010 is meaningful only if it records a decision boundary.
  Without a trigger condition, the mission would say "maybe later" and leave the
  abstraction question unresolved.
- **Alternatives considered**:
  - Treat the recommendation as optional prose in the plan: rejected because the
    spec names it as a deliverable and success criterion.
