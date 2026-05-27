# Feature Specification: Model Intake And Profile Context

**Mission**: model-intake-and-profile-context-01KSMN80
**Created**: 2026-05-27
**Mission type**: software-dev
**Status**: Draft

## 1. Summary

Premura already has a clear home for observed measurements, intervals, and
clinical notes, but it does not yet have a clear home for the operator context
and intake-domain data that future health reasoning will need. Today this gap
shows up in two ways:

1. Some useful Stage 2 work needs stable or slowly-changing personal context
   such as birth date, sex, or standing height, but those values do not fit the
   current "observed at a time with source provenance" model cleanly.
2. Nutrition intake and supplement intake are not first-class data domains, so
   future work risks treating food, nutrients, doses, and regimen context as
   ad-hoc notes or improvised measurements.

This mission defines one shared domain model and boundary for three related
domains:

1. **Baseline profile context** — stable or slowly-changing personal attributes.
2. **Nutrition intake** — food, drink, energy, and nutrient consumption.
3. **Supplement intake** — supplement products, ingredients, and doses taken.

The purpose is to make later ingest, signal-processing, and user-facing work
possible without hidden assumptions. This mission defines what belongs in each
domain, how each domain participates in provenance and updates, and how future
functions may depend on that data. It does **not** implement capture workflows,
new parsers, or new Stage 2 answers.

## 2. User Scenarios & Testing

### Primary actors

- **Maintainer** deciding where newly supported health data belongs in Premura's
  canonical model.
- **Future contributor / agent** adding a signal or workflow that needs baseline
  profile context, nutrition intake, supplement intake, or a combination of
  them.
- **Operator** who will later import or enter this data and needs its meaning,
  provenance, and update behavior to be explicit.

### Acceptance scenarios

1. **Each kind of data has one clear home.** Given examples such as birth date,
   biological sex, standing height, body weight from a smart scale, meal energy,
   daily protein intake, supplement dose, and a narrative clinical note, when a
   maintainer reviews the model, then each example maps to exactly one canonical
   domain with no ambiguity about whether it is profile context, intake, an
   observed measurement, or a note.
2. **Profile-dependent functions stop depending on hidden assumptions.** Given a
   future function such as BMI or age-adjusted interpretation, when a
   contributor reads the model, then it is explicit which baseline profile
   attributes are prerequisites and how missing prerequisites should be treated.
3. **Nutrition and supplement intake are first-class, not improvised.** Given a
   future workflow that needs meal-level nutrients or supplement doses, when a
   contributor reads the model, then they can represent the intake event, the
   consumed item, and the nutrient or dose quantities without pretending those
   are ordinary body measurements.
4. **Updates preserve meaning and provenance.** Given a correction to a profile
   value, a refined meal estimate, or a changed supplement record, when the
   maintainer reviews the model, then the model makes clear what counts as a new
   assertion, what counts as a correction, and what provenance must remain
   visible.
5. **Future work has a bounded follow-on path.** Given later missions for data
   entry, import, or signal logic, when the maintainer reads this spec, then the
   open work is limited to implementation and workflow choices rather than the
   underlying boundary question.

### Edge cases

- A person's standing height may exist both as a device-emitted observation and
  as a declared baseline attribute; the model must explain how those differ
  rather than collapsing them into one meaning.
- Age should not be treated as an independently edited attribute when it can be
  derived from birth date and the evaluation date.
- Nutrition records may be complete (macros and micros known) or partial (only
  total energy or meal label known); the model must support incomplete but still
  useful intake records.
- A supplement record may refer to a branded product, a single ingredient, or a
  multi-ingredient stack; the model must preserve what was actually known at the
  time of recording.
- Manual assertions and imported records must remain distinguishable so later
  reasoning can name their provenance honestly.

## 3. Functional Requirements

| ID | Requirement | Verification | Status |
|---|---|---|---|
| FR-001 | Premura SHALL define **baseline profile context**, **nutrition intake**, and **supplement intake** as explicit first-class data domains, distinct from observed measurements, intervals, and narrative notes. | Review of the resulting decision package confirms all three domains are named, defined, and separated from observations and notes. | Draft |
| FR-002 | Premura SHALL define classification rules that let a reviewer place each named example in this spec into exactly one canonical home: profile context, intake data, observed measurement/interval, or note. | Maintainer review of the named examples confirms each has one unambiguous home and no dual classification. | Draft |
| FR-003 | Premura SHALL define how stable, slowly-changing, and derived profile context are represented, including how permanent attributes, mostly-stable attributes, and derived-from-stable attributes differ. | Review confirms the model explicitly distinguishes at least one permanent attribute, one slowly-changing attribute, and one derived attribute and explains their different handling. | Draft |
| FR-004 | Premura SHALL define the minimum provenance and time semantics required for profile assertions, nutrition intake records, and supplement intake records, including how origin, effective time, and later corrections are represented. | Entity review confirms each first-class entity in these domains names its provenance requirements and time semantics. | Draft |
| FR-005 | Premura SHALL define how future signal-processing or interpretation functions may declare a dependency on profile context, nutrition intake, supplement intake, or combinations of them, so those dependencies are explicit rather than hidden. | Review of at least one profile-dependent example and two intake-dependent examples confirms the required dependencies can be named directly from the model. | Draft |
| FR-006 | Premura SHALL define how nutrition intake records can represent both event-level facts (for example a meal or drink) and quantitative nutrition facts (for example energy or nutrient amounts) without treating those quantities as ordinary body observations. | Review confirms the model distinguishes the intake occurrence from the quantities attributed to that occurrence. | Draft |
| FR-007 | Premura SHALL define how supplement intake records can represent both the consumed supplement item and the taken dose, while remaining open to single-ingredient and multi-ingredient products. | Review confirms the model supports both single-ingredient and multi-ingredient supplement examples without changing the boundary rules. | Draft |
| FR-008 | Premura SHALL define coexistence rules between these new domains and the existing observation history, including how a measured value and a declared context value of similar meaning remain distinguishable. | Review confirms the model explicitly addresses at least one overlapping case such as measured height vs declared standing height. | Draft |
| FR-009 | Premura SHALL document the deferred follow-on work needed after this mission, separating model decisions from later implementation work such as import, manual entry, and new Stage 2 behavior. | Review confirms the spec and aligned docs leave implementation follow-ons explicit rather than implicit. | Draft |

## 4. Non-Functional Requirements

| ID | Requirement | Threshold / Verification | Status |
|---|---|---|---|
| NFR-001 | The model SHALL be classification-complete for the examples it names. | 100% of the named examples in this spec can be placed into exactly one canonical home during maintainer review. | Draft |
| NFR-002 | The model SHALL be provenance-complete for its first-class entities. | 100% of the key entities defined in this spec state both origin/provenance semantics and time/effective-date semantics. | Draft |
| NFR-003 | The model SHALL preserve Premura's local-first privacy posture. | Review finds 0 requirements that require background network exchange, silent third-party sharing, or external interpretation services. | Draft |
| NFR-004 | The model SHALL be future-ready for dependent reasoning. | Maintainer review can explain at least 1 profile-dependent example and at least 2 intake-dependent examples using the model without adding any unstated assumptions. | Draft |

## 5. Constraints

| ID | Constraint | Status |
|---|---|---|
| C-001 | This mission defines the domain model and boundary only; it does not implement import paths, manual-entry flows, new Stage 2 functions, or new UI workflows. | Active |
| C-002 | The existing observation history and narrative-note history remain explicit domains in their own right; this mission must not collapse all health data into one undifferentiated context store. | Active |
| C-003 | The resulting model must remain single-user and local-first, consistent with Premura's existing product stance. | Active |
| C-004 | The model must address baseline profile context, nutrition intake, and supplement intake together as one coherent boundary, rather than solving only one of them and leaving the others implicit. | Active |

## 6. Success Criteria

- SC-001: A reviewer can classify every named example in this spec into one and
  only one canonical home, with no unresolved ambiguity.
- SC-002: Future contributors can describe the prerequisites for BMI or another
  profile-dependent function without relying on hidden context or opportunistic
  measurements.
- SC-003: Future contributors can describe one nutrition-dependent and one
  supplement-dependent reasoning flow using first-class intake records rather
  than ad-hoc notes or improvised body measurements.
- SC-004: Every first-class entity in the model names both its provenance and
  its time semantics.
- SC-005: The post-mission follow-on work is limited to implementation and
  workflow choices, not to re-deciding where profile and intake data belong.

## 7. Key Entities

- **Baseline profile attribute**: a stable or slowly-changing operator-context
  value such as birth date, biological sex, or declared standing height.
- **Profile assertion**: one recorded statement of a baseline profile attribute,
  including who supplied it, when it became effective, and where it came from.
- **Intake event**: one eating, drinking, or supplement-taking occurrence that
  anchors what was consumed and when.
- **Intake item**: one food, drink, or supplement product consumed within an
  intake event.
- **Nutrition fact**: an energy or nutrient quantity attached to an intake item
  or intake event.
- **Supplement dose**: the taken quantity of a supplement item, preserving what
  was known about the product or ingredient at record time.
- **Provenance record**: the origin metadata that distinguishes imported,
  manually asserted, corrected, or derived data across these domains.

## 8. Assumptions

- Premura remains a single-user system whose operator is also the data subject.
- Later implementation work may support both imported artifacts and manual entry
  for profile and intake data, even though this mission does not choose specific
  capture workflows yet.
- Age is better treated as derived context than as an independently edited
  baseline attribute.
- Measured observations and declared context values may coexist when they serve
  different purposes, as long as the model keeps their meanings explicit.

## 9. Scope

**In scope**: defining the shared boundary and canonical entities for baseline
profile context, nutrition intake, and supplement intake; defining their
provenance and time semantics; defining how future functions depend on them;
and documenting the resulting follow-on work for implementation missions.

**Out of scope**: new parser support; manual-entry UX; new Stage 2 or Stage 3
features; clinical interpretation behavior; user-facing teaching copy; and any
attempt to treat profile or intake data as if this mission had already shipped
their full capture workflows.
