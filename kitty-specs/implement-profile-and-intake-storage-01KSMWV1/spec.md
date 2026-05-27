# Feature Specification: Implement Profile And Intake Storage

**Mission**: implement-profile-and-intake-storage-01KSMWV1
**Created**: 2026-05-27
**Mission type**: software-dev
**Status**: Draft

## 1. Summary

Premura now has a clear meaning contract for three kinds of user-declared data:

1. **Profile context**: facts the operator states about themselves, such as
   birth date, sex, or standing height.
2. **Nutrition intake**: meals, drinks, calories, and nutrient amounts.
3. **Supplement intake**: supplement products, ingredients, and taken doses.

What is still missing is the first real implementation over that contract. The
system needs a proper place to store these three domains, and it needs the
first real operational path for getting the right data into them without
collapsing back into observation history.

This mission adds that first implementation layer. It gives each domain a real
home in Premura and adds the first write path for **profile context** through an
agent-mediated bounded interview followed by deterministic tool writes. For
**nutrition intake** and **supplement intake**, this mission establishes the
storage and persistence seam those future parser or plug-in missions should
target, but it does not ship hand-entry flows or one-off built-in importers.
The purpose is to let Premura hold profile and intake data correctly before
later missions build profile-aware or intake-aware health answers on top of it,
and before future parser work lands nutrition and supplement records in their
correct homes.

This mission does **not** add BMI, age-adjusted interpretation, or any other new
Stage 2 answer. It also does **not** ship a broad nutrition/supplement parser
surface; that remains part of the plug-in / parser path.

## 2. User Scenarios & Testing

### Primary actors

- **Operator** who wants the agent to capture stable profile facts once and keep
  them separate from wearable measurements.
- **Agent** that asks the operator for bounded profile information, writes those
  facts through deterministic tools, and later helps extend Premura for new
  nutrition or supplement sources.
- **Maintainer** who needs a clear, reviewable first implementation over the
  profile/intake contract.
- **Future contributor / agent** who will later build profile-aware or
  intake-aware reasoning or parser support on top of this stored data.

### Acceptance scenarios

1. **The agent captures bounded profile context.** Given an operator who wants
   to provide birth date, sex, and declared standing height, when the agent asks
   a bounded set of profile questions and writes the answers through Premura's
   deterministic write surface, then those values are stored as profile context
   rather than as observed measurements or free-form notes.
2. **The profile write path stays inspectable.** Given a later review of the
   stored profile records, when the maintainer inspects them, then it is visible
   which values came from an agent-mediated profile interview, when they became
   effective, and what write surface created them.
3. **Nutrition and supplement data have a real landing zone.** Given a future
   parser or plug-in that produces nutrition or supplement intake records, when
   those records are persisted, then they land in nutrition intake or supplement
   intake rather than in observation history or note history.
4. **Nutrition and supplement parser work no longer needs to reopen the model.** Given a future mission to support a vendor export, when a contributor reads the
   storage and persistence design from this mission, then they can target the
   correct domain without redesigning where meals or supplement doses belong.
5. **Follow-on signal work stays simpler.** Given a later mission that wants to
   compute BMI or produce age-adjusted interpretation, when a contributor reads
   the stored domains after this mission, then the profile prerequisites already
   have a stable home and do not need to be rediscovered.

### Edge cases

- A declared standing height and a measured height observation may both exist;
  they must remain distinguishable.
- A profile fact may later change, such as standing height being corrected or a
  birth date being fixed; the stored history must preserve what changed and when.
- A nutrition record may include only calories, or calories plus some but not
  all nutrients; future parser work must be able to persist partial but honest
  records.
- A supplement record may name only a branded product, only an ingredient, or a
  multi-ingredient product; the storage must preserve what was actually known.
- The write surface for profile context must be bounded enough that the agent
  does not improvise unsupported profile fields.

## 3. Functional Requirements

| ID | Requirement | Verification | Status |
|---|---|---|---|
| FR-001 | Premura SHALL provide a persistent first-class home for **profile context**, **nutrition intake**, and **supplement intake**, each distinct from observation history and note history. | Maintainer review confirms all three domains are persistable and remain separate from observations and notes. | Draft |
| FR-002 | Premura SHALL provide a deterministic write surface that lets an agent store bounded profile-context records for baseline personal attributes such as birth date, sex, and declared standing height. | Acceptance testing shows the agent can write at least three supported baseline profile attributes and retrieve them from the profile-context domain. | Draft |
| FR-003 | Premura SHALL keep the first profile-context capture path agent-mediated, so the operator can answer a bounded set of questions and the agent performs the actual write through deterministic tools. | Acceptance testing shows the operator can complete one bounded agent-mediated profile capture flow without direct database edits. | Draft |
| FR-004 | Premura SHALL preserve provenance and time semantics for all three domains, including whether a record came from agent-mediated profile capture or from future parser/plugin persistence and when it was recorded or became effective. | Review of sample records from each domain confirms provenance and time semantics are retained and inspectable. | Draft |
| FR-005 | Premura SHALL provide a persistence path for nutrition-intake records that future parser or plug-in work can target without using observation history or note history as a shortcut. | Maintainer review confirms a future nutrition parser can persist intake records into nutrition intake without reopening the storage model. | Draft |
| FR-006 | Premura SHALL provide a persistence path for supplement-intake records that future parser or plug-in work can target without using observation history or note history as a shortcut. | Maintainer review confirms a future supplement parser can persist intake records into supplement intake without reopening the storage model. | Draft |
| FR-007 | Premura SHALL preserve domain-specific meaning during storage and persistence, so profile context is not written as observation history, meal energy is not written as wearable measurement history, and supplement doses are not merged into nutrition intake. | Review of stored examples confirms each accepted record remains in its canonical home. | Draft |
| FR-008 | Premura SHALL bound the supported profile-context surface for this mission so the agent can only write the agreed stable profile facts rather than inventing open-ended profile fields. | Acceptance testing confirms unsupported profile fields are rejected or explicitly unsupported rather than silently accepted. | Draft |
| FR-009 | Premura SHALL keep nutrition and supplement source support out of this mission while making those later parser/plugin missions easier to build next. | Maintainer review confirms no built-in vendor-specific nutrition or supplement importer ships in this mission, while the storage and persistence seam is ready for follow-on parser work. | Draft |
| FR-010 | Premura SHALL keep later profile-aware health answers out of this mission while making them easier to build next. | Maintainer review confirms BMI and age-adjusted interpretation remain absent, while the stored domains provide the prerequisites those future missions need. | Draft |

## 4. Non-Functional Requirements

| ID | Requirement | Threshold / Verification | Status |
|---|---|---|---|
| NFR-001 | Domain placement must be correct for the supported flows. | In acceptance testing, 100% of accepted profile-context writes and sample nutrition/supplement persistence records land in exactly one correct domain. | Draft |
| NFR-002 | Provenance must be complete for accepted records. | In acceptance testing, 100% of accepted profile, nutrition, and supplement records retain source type and recorded/effective time semantics. | Draft |
| NFR-003 | The supported profile capture path must stay bounded and inspectable. | In acceptance testing, 100% of unsupported profile fields are rejected explicitly, and 100% of accepted profile writes can be traced back to the deterministic write surface. | Draft |
| NFR-004 | The mission must preserve Premura's local-first privacy posture. | Review and regression testing show 0 background network calls and 0 silent third-party data sharing in the supported profile-capture and persistence flows. | Draft |
| NFR-005 | First-pass profile capture must be usable through the default agent-mediated workflow. | In acceptance testing, the operator can complete one bounded profile capture flow through the agent in under 3 minutes without direct CLI or SQL use. | Draft |
| NFR-006 | Nutrition and supplement persistence must be ready for follow-on parser work without reopening the storage model. | Maintainer review can map at least 1 nutrition parser output example and 1 supplement parser output example into the persistence surface with 0 undocumented storage decisions. | Draft |

## 5. Constraints

| ID | Constraint | Status |
|---|---|---|
| C-001 | This mission is limited to storage for the three already-defined domains plus the first agent-mediated capture path for profile context. | Active |
| C-002 | Profile context capture in this mission is agent-mediated over deterministic tools; human-facing forms and direct database editing are out of scope as primary paths. | Active |
| C-003 | Nutrition and supplement source support remain parser/plugin-oriented follow-on work; no built-in vendor-specific nutrition or supplement importer ships in this mission. | Active |
| C-004 | BMI, age-adjusted interpretation, and other new profile-aware or intake-aware Stage 2 answers remain out of scope. | Active |
| C-005 | This mission must honor the one-home rules and invariants from the profile/intake meaning contract; it must not back-door profile or intake data into observation history. | Active |
| C-006 | The supported flows must remain single-user, local-first, and non-diagnostic. | Active |

## 6. Success Criteria

- SC-001: The operator can complete one agent-mediated bounded profile capture
  flow that stores at least 3 supported profile-context values in their correct
  domain.
- SC-002: Maintainer review confirms that at least 1 nutrition parser output
  example and 1 supplement parser output example have a clear persistence path
  into their correct domains without redesigning the model.
- SC-003: In unsupported profile-field tests, 100% of rejected fields are
  surfaced explicitly rather than silently accepted.
- SC-004: Maintainer review confirms that no accepted record from this mission
  is stored as ordinary observation history just because an older storage path
  already existed.
- SC-005: Future parser/plugin missions for nutrition and supplements no longer
  need to reopen where those records belong; they only need to implement source
  adaptation and persistence.

## 7. Key Entities

- **Profile context record**: one stored statement about a baseline personal
  attribute, such as birth date, sex, or declared standing height.
- **Nutrition intake event**: one eating or drinking occurrence anchored to a
  time or time range.
- **Nutrition intake item**: one food or drink consumed within an intake event.
- **Nutrition quantity**: one energy or nutrient amount attached to a nutrition
  intake event or item.
- **Supplement intake event**: one occurrence of taking a supplement at a given
  time.
- **Supplement item**: the product or ingredient that was taken.
- **Supplement dose**: the quantity taken for one supplement item.
- **Profile capture session**: one bounded agent-mediated interaction that asks
  for supported profile facts and persists the answers through deterministic
  tools.
- **Persistence input**: the normalized shape a future nutrition or supplement
  parser should provide so records can be stored in their canonical domains.

## 8. Assumptions

- Profile context should begin with agent-mediated bounded capture rather than a
  human-facing form or profile-file import.
- Future nutrition and supplement source support should continue to follow the
  plug-in / parser approach from vendor-shaped source artifacts rather than a
  built-in one-off importer for each source.
- The representative MyFitnessPal dump remains useful as a later parser test
  artifact, but not as a built-in importer requirement for this mission.
- Future missions will build BMI and age-adjusted interpretation on top of the
  stored profile-context domain rather than reopening the boundary question.

## 9. Scope

**In scope**: persistent storage for the three profile/intake domains; an
agent-mediated bounded capture path for stable profile facts; a deterministic
write surface for profile context; a persistence seam that future nutrition and
supplement parsers can target; and preservation of provenance and time semantics
across those flows.

**Out of scope**: human-facing forms as the primary capture path; profile-file
import; built-in nutrition or supplement importers; broader parser support for
third-party source artifacts; BMI; age-adjusted interpretation; any other new
Stage 2 or Stage 3 health answer; teaching copy; and any attempt to collapse
profile or intake records into observation history.
