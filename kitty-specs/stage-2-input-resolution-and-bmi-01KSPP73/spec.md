# Feature Specification: Stage 2 Input Resolution And BMI

**Mission**: stage-2-input-resolution-and-bmi-01KSPP73
**Created**: 2026-05-28
**Mission type**: software-dev
**Status**: Draft

## 1. Summary

Premura has already shipped a first grounded Stage 2 slice: six descriptive or
comparative answers over observation history, routed into Stage 3 as MCP tools.
What it still lacks is the next honest foundation for cross-domain reasoning.

The repo now has distinct semantic domains for observation history, baseline
profile context, nutrition intake, and supplement intake. Future health answers
must not quietly collapse those meanings back into one observation-shaped path
just because some current questions happen to look like time-series analysis.

This mission adds the first domain-aware input-resolution seam inside Stage 2.
It lets a Stage 2 answer declare exactly which inputs it needs, resolve shipped
domains honestly as of an anchor time, and refuse clearly when a declared domain
is not yet supported by real rows. The first validating consumer is BMI, because
it is the smallest answer Premura can ship today that genuinely crosses domains:
declared profile context plus observed body weight.

This mission also sets the structural pattern for later growth without opening
too much surface too early. It adds the resolver registry shape now, records the
review rule for when a new semantic domain is genuinely needed, and records the
trigger for extending Stage 2 answer families later without opening them in this
mission.

This mission remains Stage 2 only. It does not add Stage 3 statistical tools,
literature tooling, or nutrition/supplement analytical consumers yet.

## 2. User Scenarios & Testing

### Primary actors

- **Operator** who wants Premura to answer a cross-domain health question
  honestly from already-shipped data.
- **Agent** that asks Premura for a health answer through deterministic Stage 2
  behavior rather than improvising across raw domains.
- **Maintainer** who needs a stable, reviewable pattern for future Stage 2 work
  that may depend on more than one semantic domain.
- **Future contributor / agent** who will later add new domains, new resolvers,
  or new Stage 2 consumers without reopening the same boundary debate.

### Acceptance scenarios

1. **BMI resolves across domains honestly.** Given a user with a declared
   standing height and at least one usable body-weight observation, when Premura
   computes BMI as of a chosen anchor time, then it reads declared height from
   profile context, weight from observation history, and produces one grounded
   Stage 2 answer.
2. **BMI refuses cleanly when profile context is missing.** Given a user with
   body-weight observations but no declared standing height, when Premura tries
   to compute BMI, then it does not guess from a convenient measurement or use
   hidden fallbacks; it returns an explicit missing-input outcome.
3. **BMI refuses cleanly when observation input is stale or absent.** Given a
   user with declared standing height but no usable weight observation for the
   requested anchor time, when Premura tries to compute BMI, then it returns an
   explicit unavailable or stale-input outcome rather than pretending it knows
   the answer.
4. **Future unsupported domains fail honestly.** Given a future Stage 2 consumer
   that declares `nutrition_intake` or `supplement_intake` dependencies before
   Premura ships real resolvers for those domains, when input resolution runs,
   then it returns an explicit unresolved or missing-input outcome rather than
   silently treating those domains as observations.
5. **A new resolver can be added without rewriting existing ones.** Given a
   future mission that introduces another supported domain, when a maintainer
   reads the shipped resolver pattern from this mission, then they can add the
   new resolver without changing the behavior of the existing observation or
   profile resolvers.
6. **Future domain proposals are forced through the right review question.**
   Given a future contributor who wants to add a new kind of user data, when they
   read the updated docs, then they can tell whether they need a genuinely new
   semantic domain or only a new shape inside an existing one.
7. **Future answer-family growth stays review-gated.** Given a future proposal
   whose natural answer is not numeric or time-anchored, when a maintainer reads
   the updated Stage 2 contract, then they can tell that the answer-family set
   stays closed until a deliberate follow-on mission extends it.

### Edge cases

- A user has a measured height observation but no declared standing height; BMI
  must not silently substitute the measurement for the declared prerequisite.
- A user has declared height and multiple historical weights; BMI must resolve
  the weight that is valid for the requested anchor time rather than an arbitrary
  latest row with no freshness check.
- A user has no weight at all, or only stale weight, and the answer must fail
  explicitly.
- A future domain is declared in the dependency surface but still has no real
  shipped resolver.
- A future dataset looks unusual because of temporal shape alone (episodic,
  sparse, denser sampling) but is not actually a new semantic domain.
- A future dataset is genuinely a new semantic domain and should not be forced
  into observation history merely because it is numeric.

## 3. Functional Requirements

| ID | Requirement | Verification | Status |
|---|---|---|---|
| FR-001 | Premura SHALL provide a Stage 2 input-resolution seam that resolves declared dependencies from the supported semantic domains rather than assuming all future inputs are observation-series data. | Acceptance testing shows declared dependencies are resolved through domain-aware logic rather than one generic observation-only path. | Draft |
| FR-002 | Premura SHALL support input resolution for observation history in this mission. | Acceptance testing shows observation-based declared inputs can be resolved for a Stage 2 consumer at a chosen anchor time. | Draft |
| FR-003 | Premura SHALL support input resolution for baseline profile context in this mission, including resolution of the latest valid declared value as of an anchor time. | Acceptance testing shows declared profile inputs can be resolved for a Stage 2 consumer at a chosen anchor time. | Draft |
| FR-004 | Premura SHALL ship BMI as the first cross-domain Stage 2 consumer using the new input-resolution seam. | Acceptance testing shows BMI can be produced when both declared height and usable weight exist. | Draft |
| FR-005 | Premura SHALL refuse BMI honestly when any declared prerequisite is missing, stale, or otherwise unusable, without hidden substitution from another domain. | Negative-path acceptance testing shows BMI returns an explicit refusal or missing-input outcome in all missing/stale prerequisite cases. | Draft |
| FR-006 | Premura SHALL keep nutrition-intake and supplement-intake domains valid in the declared dependency surface even though this mission does not ship their real resolvers. | Maintainer review confirms those domains are still expressible in declarations after this mission. | Draft |
| FR-007 | Premura SHALL return an explicit unresolved or missing-input outcome when a declared dependency targets a valid but not-yet-resolvable domain in this mission. | Acceptance testing shows declared nutrition-intake and supplement-intake dependencies fail honestly rather than being silently coerced into another domain. | Draft |
| FR-008 | Premura SHALL provide a resolver registration pattern that lets future supported domains be added without rewriting existing domain dispatch behavior. | Maintainer review confirms a future resolver can be added through the shipped registration pattern without modifying existing resolver logic. | Draft |
| FR-009 | Premura SHALL document a domain-vs-shape review rubric so future contributors can tell when a new kind of data requires a new semantic domain versus a new shape inside an existing domain. | Maintainer review confirms the rubric is present and can classify at least one example of each case. | Draft |
| FR-010 | Premura SHALL document when the Stage 2 answer-family set should be deliberately extended, while keeping that set closed in this mission. | Maintainer review confirms the Stage 2 contract includes explicit trigger conditions for extending answer families later. | Draft |
| FR-011 | Premura SHALL update the affected docs so the next analytical foundation is described as domain-aware input resolution rather than a universal prepared-series layer. | Maintainer review confirms the named docs align on the updated boundary and the Stage 2-only scope. | Draft |

## 4. Non-Functional Requirements

| ID | Requirement | Threshold / Verification | Status |
|---|---|---|---|
| NFR-001 | Cross-domain input resolution must stay honest. | In acceptance testing, 100% of missing, stale, or unsupported declared inputs surface an explicit refusal or missing-input outcome rather than a silent fallback. | Draft |
| NFR-002 | The BMI consumer must be reproducible. | For 100% of fixed acceptance-test fixtures, repeated runs with unchanged data produce the same BMI result or the same explicit refusal outcome. | Draft |
| NFR-003 | The shipped resolver pattern must remain locally inspectable. | Maintainer review can trace 100% of supported-domain resolution behavior from the declared dependency surface to the responsible resolver without hidden network calls or dynamic discovery. | Draft |
| NFR-004 | This mission must preserve Premura's local-first privacy posture. | Acceptance and regression testing show 0 background network calls and 0 silent third-party data sharing in the new input-resolution and BMI flows. | Draft |
| NFR-005 | The new docs must be usable as a future review aid. | A maintainer can classify at least 3 future examples using the new domain-vs-shape rubric and answer-family trigger text without needing unwritten guidance. | Draft |
| NFR-006 | Interactive use must remain practical for the first consumer. | On the maintainer's representative local datasets, at least 95% of BMI requests complete in under 5 seconds. | Draft |

## 5. Constraints

| ID | Constraint | Rationale | Status |
|---|---|---|---|
| C-001 | This mission is limited to Stage 2 work. | Keeps the mission aligned with the agreed scope and avoids silently adding Stage 3 analytical tooling. | Active |
| C-002 | The only real resolvers shipped in this mission are observation-history resolution and profile-as-of resolution. | Prevents speculative intake-domain implementation before real parser-produced rows exist. | Active |
| C-003 | Nutrition-intake and supplement-intake analytical consumers remain out of scope for this mission. | Those consumers depend on real intake data that Premura does not yet ingest. | Active |
| C-004 | The first validating consumer for this mission is BMI. | BMI is the smallest buildable consumer that genuinely crosses domains using shipped data. | Active |
| C-005 | The mission must not reopen the semantic boundary that separated observations, profile context, nutrition intake, and supplement intake into distinct domains. | Preserves the meaning contract and storage decisions already shipped. | Active |
| C-006 | The mission must not open the Stage 2 answer-family set in this implementation slice. | Keeps family growth review-gated rather than accidental. | Active |
| C-007 | The mission must not add Stage 3 statistical tools, PubMed tooling, or literature-grounding behavior. | Preserves the current sequencing: Stage 2 foundation first, broader Stage 3 later. | Active |

## 6. Success Criteria

- SC-001: A user with declared height and usable weight can receive a BMI answer
  through Stage 2 in under 5 seconds in at least 95% of acceptance-test runs.
- SC-002: In 100% of acceptance-test cases where declared height is missing,
  stale, or unsupported, BMI returns an explicit refusal or missing-input
  outcome rather than silently substituting from another domain.
- SC-003: In 100% of acceptance-test cases where a declared dependency targets
  nutrition-intake or supplement-intake, Premura returns an explicit unresolved
  or missing-input outcome rather than pretending those domains are already
  resolvable.
- SC-004: Maintainer review confirms a future third resolver can be added
  through the shipped resolver registration pattern without rewriting the
  existing observation and profile resolvers.
- SC-005: Maintainer review confirms the updated docs clearly explain the new
  Stage 2 boundary, the domain-vs-shape rubric, and the trigger for extending
  answer families later.

## 7. Key Entities

- **Declared dependency**: one explicit statement of which semantic domain,
  exact key, and failure mode a Stage 2 consumer requires.
- **Input resolver**: the Stage 2 behavior that resolves one declared dependency
  honestly from the correct supported domain as of an anchor time.
- **Anchor time**: the time reference used to decide which value or slice of data
  is valid for a given consumer request.
- **Resolved observation input**: the observation-domain result returned for a
  declared observation dependency, including freshness or absence semantics.
- **Resolved profile input**: the profile-domain result returned for a declared
  profile dependency, including latest-known-as-of semantics.
- **Unsupported domain resolution outcome**: the explicit unresolved or
  missing-input result returned when a valid future domain is declared but no
  concrete resolver ships yet.
- **BMI consumer**: the first Stage 2 answer that depends on both profile
  context and observation history.
- **Resolver registry**: the registration surface that maps supported semantic
  domains to their concrete resolver implementations.
- **Domain-vs-shape rubric**: the written review rule that distinguishes a
  genuinely new semantic domain from a new temporal or structural shape inside an
  existing domain.
- **Answer-family trigger**: the written rule for when Premura should open a
  mission to extend the closed Stage 2 answer-family set.

## 8. Assumptions

- The tmp-file research and follow-up discussion are the authoritative source
  for the conclusion that the next Stage 2 foundation should be framed as
  domain-aware input resolution rather than as a universal prepared-series
  layer.
- BMI is the right first consumer because it is cross-domain and buildable today
  from the shipped profile-capture path plus existing weight observations.
- Nutrition-intake and supplement-intake domains matter to the future design,
  but their real Stage 2 resolvers should wait until Premura ingests real rows
  for those domains.
- A resolver registration pattern is worth shipping now because this mission
  introduces more than one resolver and should not lock the project into a
  growing hardcoded dispatch chain.
- The answer-family set should remain closed unless a later mission proves a new
  family is genuinely required.

## 9. Scope

**In scope**: Stage 2 declared-input resolution for observation history and
profile context; anchor-time-aware resolution behavior; BMI as the first
cross-domain consumer; explicit unresolved behavior for declared but not-yet-
resolvable intake domains; a resolver registration pattern; and docs updates
covering the new boundary, the domain-vs-shape rubric, and the answer-family
extension trigger.

**Out of scope**: Stage 3 statistical tools; PubMed or literature tooling;
nutrition-intake analytical consumers; supplement-adherence consumers; concrete
nutrition or supplement resolvers; opening the answer-family set; and any
attempt to collapse profile, intake, and observation meanings into one generic
observation-shaped analytical path.
