# Research Notes: Stage 2 Input Resolution And BMI

## Decision 1: Keep the Stage 2 / Stage 3 split

**Decision**: Keep the next mission inside Stage 2 and do not combine it with
the first Stage 3 analytical tools.

**Rationale**: The agreed mission is to build the honest input-resolution seam
that later Stage 3 analytical tools can depend on. Adding Stage 3 statistics now
would blur the acceptance boundary and make it harder to tell whether the new
resolver pattern itself is correct.

**Alternatives considered**:

- Combine Stage 2 input resolution with the first Stage 3 tool in one mission.
  Rejected because the user confirmed the mission should remain Stage 2 only.

## Decision 2: Correct the abstraction unit

**Decision**: Frame the new foundation as a **domain-aware input-resolution
seam**, not a universal prepared-series layer.

**Rationale**: The repo's own semantic split (observation history, profile
context, nutrition intake, supplement intake) means a universal series-shaped
abstraction would push against the architecture. The tmp-file research also
converged on the same correction: the generalization target is declared input +
resolution as of an anchor time, not "everything becomes a series."

**Alternatives considered**:

- Build a prepared-series contract first. Rejected because it is too biased
  toward current observation metrics and too weak for future profile/intake work.

## Decision 3: Ship only the resolvers backed by real rows now

**Decision**: Implement only observation resolution and profile-as-of resolution
in this mission.

**Rationale**: Observation history and profile context already have concrete
stored rows and shipped capture/read semantics. Nutrition and supplement domains
are real in the contract and storage, but Premura does not yet ingest real
parser-produced rows for them. Shipping those resolvers now would design against
examples rather than against data.

**Alternatives considered**:

- Implement all four domain resolvers now. Rejected as premature abstraction.
- Ignore nutrition/supplement in the declaration contract for now. Rejected
  because the future domains matter to the design and should remain representable
  in the contract.

## Decision 4: Explicit unresolved behavior is part of the design

**Decision**: Keep `nutrition_intake` and `supplement_intake` valid in the
declared dependency surface and return an explicit unresolved or missing-input
outcome for them until real resolvers ship.

**Rationale**: This keeps the contract future-aware without pretending that the
code can already resolve those domains. It also prevents the failure mode where a
future contributor silently reads those domains through observation-history
shortcuts.

**Alternatives considered**:

- Exclude the future domains from the declaration surface entirely. Rejected
  because it hides known future work from the contract.

## Decision 5: BMI is the singular first proof consumer

**Decision**: Use BMI as the first cross-domain Stage 2 consumer.

**Rationale**: BMI is buildable now from shipped profile capture plus existing
weight observations, and it is the smallest consumer that genuinely forces
cross-domain dispatch. It proves the resolver idea better than a pure
observation-history consumer would.

**Alternatives considered**:

- `latest_lab_value_status` as a first consumer. Rejected because it exercises
  only the observation branch.
- Nutrition or supplement summaries. Rejected because real parser-produced rows
  are not available yet.

## Decision 6: Resolver dispatch should be open now

**Decision**: Introduce a small in-tree resolver registry pattern in this
mission.

**Rationale**: Once the second resolver lands, hardcoded dispatch becomes the
wrong default. Mirroring the existing static signal-registry pattern keeps the
change small and prepares the codebase for future supported domains without
inventing external plugin discovery now.

**Alternatives considered**:

- Keep a hardcoded `if domain == ...` chain for now. Rejected because this is
  the cheapest moment to set the right pattern.
- Build dynamic or out-of-tree resolver discovery now. Rejected as unnecessary
  and outside current repo rules.

## Decision 7: Record the growth rules in docs now

**Decision**: Update the docs in this mission to include:

- a domain-vs-shape review rubric
- the trigger for extending `RESULT_FAMILIES`

**Rationale**: The next failure mode after this mission would be not code, but
future contributors misclassifying new datasets or stretching the answer-family
set accidentally. Writing the review rules down now is low-cost and load-bearing.

**Alternatives considered**:

- Leave those rules implicit until a later mission. Rejected because the mission
  is already changing the architectural boundary and should document that change
  where future contributors will look.
