---
work_package_id: WP01
title: Authoritative Profile And Intake Contract Surface
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-006
- FR-007
- FR-008
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-model-intake-and-profile-context-01KSMN80
base_commit: d603375383ea8eae86c39c2ec54071636c5ca290
created_at: '2026-05-27T12:35:12.596654+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
shell_pid: "18350"
agent: "claude:opus:implementer:implementer"
history:
- timestamp: '2026-05-27T12:27:28Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/architecture/
execution_mode: code_change
owned_files:
- docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md
- docs/architecture/contracts/profile_and_intake_entities.yaml
- docs/architecture/contracts/profile_and_intake_examples.yaml
- docs/architecture/contracts/profile_and_intake_invariants.yaml
- docs/architecture/contracts/profile_and_intake_dependencies.yaml
tags: []
---

# Work Package Prompt: WP01 - Authoritative Profile And Intake Contract Surface

## Objective

Ship the authoritative repo-level contract surface for Premura's new profile and
intake domains.

This WP is the foundation for the whole mission. Later docs, tests, and future
implementation work packages should all depend on this surface rather than
re-deriving the model from the planning artifacts every time.

The key design constraint is simple:

- keep storage open,
- make meaning strict.

Do not choose a DuckDB layout, migration strategy, or persistence adapter here.
Define the contract that any future adapter must satisfy.

## Owned Surface

- `docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md`
- `docs/architecture/contracts/profile_and_intake_entities.yaml`
- `docs/architecture/contracts/profile_and_intake_examples.yaml`
- `docs/architecture/contracts/profile_and_intake_invariants.yaml`
- `docs/architecture/contracts/profile_and_intake_dependencies.yaml`

Do not modify files outside this list in this WP.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP01 --agent <name>`

## Context

The planning artifacts already define the intended model:

- `spec.md` defines the functional expectations: first-class domains, one-home
  classification, provenance/time semantics, dependency declaration, overlap
  rules, and follow-on clarity.
- `plan.md` fixes the implementation stance: the contract is strict, the storage
  adapter is flexible, and agent reviewers need machine-applicable guardrails.
- `data-model.md` and the planning-time `contracts/` files describe the intended
  entities, invariants, and dependency shape.

This WP converts that planning output into the repo's authoritative surface.

## Subtasks

### T001 - Add the authoritative contract document

**Purpose**

Create one prose document in `docs/architecture/` that explains the three new
domains, their meanings, and their boundaries against existing Premura surfaces.

**Required changes**

- Add `docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md`.
- Cover, in plain English:
  - what counts as baseline profile context
  - what counts as nutrition intake
  - what counts as supplement intake
  - how each differs from observation history and note history
  - how overlap cases work
  - why storage is intentionally not prescribed here
- Keep the prose aligned with the repo's plain-English style from `CONTEXT.md`.

**Constraints**

- Do not define database tables, migrations, ORM models, or APIs.
- Do not turn these domains into a fifth execution stage.
- Do not describe the contract as a runtime feature that users already have.

### T002 - Add the machine-readable entity contract

**Purpose**

Create the stable machine-readable source of truth for entity names and required
fields, so later tests and agent reviewers have something concrete to inspect.

**Required changes**

- Add `docs/architecture/contracts/profile_and_intake_entities.yaml`.
- Include the core entities from planning:
  - profile attribute
  - profile assertion
  - intake event
  - intake item
  - nutrition fact
  - supplement dose
  - dependency declaration
- For each entity, capture:
  - purpose
  - required fields
  - any indispensable semantic notes needed to avoid misuse

**Design guidance**

- Make the field names stable and explicit.
- Keep the file semantic, not storage-shaped.
- Prefer exactness over extensibility theater.

### T003 - Add machine-readable classification and overlap examples

**Purpose**

Make one-home classification and overlap handling explicit enough that later
reviewers can reject ambiguous implementations.

**Required changes**

- Add `docs/architecture/contracts/profile_and_intake_examples.yaml`.
- Include examples for:
  - birth date
  - biological sex
  - declared standing height
  - measured smart-scale height
  - meal energy
  - protein intake
  - supplement dose
  - narrative note
  - wearable total kcal
- For each example, name its canonical home.
- Include at least one overlap pair showing that similar real-world concepts can
  belong to different semantic homes.

**Constraints**

- Every example must map to exactly one home.
- Avoid vague labels like `context`, `misc`, or `metadata` as canonical homes.

### T004 - Add machine-readable positive invariants

**Purpose**

Give the repo a closed set of load-bearing rules that later implementation work
and agent review can treat as gates.

**Required changes**

- Add `docs/architecture/contracts/profile_and_intake_invariants.yaml`.
- Encode the positive invariants from planning, including:
  - one-home classification
  - semantic distinction between profile, intake, and observations
  - visible supersession/correction history
  - explicit dependency declaration
  - partial knowledge allowed, fabricated values forbidden
- Attach concrete violation examples to each invariant.

**Design guidance**

- Lead with positive statements of what must always be true.
- Use forbidden shortcuts only as examples of violations.
- Keep the invariants few and load-bearing.

### T005 - Add the dependency declaration contract

**Purpose**

Create the explicit shape future Stage 2 and Stage 3 work must use to declare
profile- and intake-domain prerequisites.

**Required changes**

- Add `docs/architecture/contracts/profile_and_intake_dependencies.yaml`.
- Define the required fields for a dependency declaration.
- Include examples such as:
  - BMI depending on profile context plus observation history
  - protein intake summary depending on nutrition intake
  - supplement adherence summary depending on supplement intake
- Make clear that opportunistic measurement presence is not a substitute for an
  explicit declaration.

**Constraints**

- This is a domain contract, not an API request schema.
- Do not invent transport routes or endpoint specs here.

## Validation Strategy

Primary checks for this WP:

```bash
python -c "import pathlib, yaml; [yaml.safe_load(pathlib.Path(p).read_text()) for p in [
  'docs/architecture/contracts/profile_and_intake_entities.yaml',
  'docs/architecture/contracts/profile_and_intake_examples.yaml',
  'docs/architecture/contracts/profile_and_intake_invariants.yaml',
  'docs/architecture/contracts/profile_and_intake_dependencies.yaml',
]]; print('yaml-ok')"
```

Expected outcomes:

- The prose contract exists and reads as the authoritative semantic boundary.
- The YAML files parse cleanly.
- The prose and machine-readable surfaces name the same domains and contract
  concepts.

## Definition Of Done

- A new authoritative contract doc exists under `docs/architecture/`.
- Machine-readable entity, example, invariant, and dependency files exist and are
  semantically aligned.
- The surface is storage-agnostic and strict on meaning.

## Risks And Watchouts

- The most likely failure mode is sneaking in storage choices while trying to be
  concrete.
- The second most likely failure mode is creating YAML that is technically
  machine-readable but too vague to constrain later work.
- Do not let the prose and YAML drift; they should reinforce each other.

## Reviewer Guidance

Review this WP as a contract-surface change, not as a persistence design.

Ask:

1. Could two agents still implement incompatible meanings while both claiming
   compliance?
2. Is every overlap case explicit enough to review mechanically later?
3. Does this surface help later tests fail on semantic drift?

## Activity Log

- 2026-05-27T12:27:28Z – gpt-5.4 – Prompt generated via /spec-kitty.tasks
- 2026-05-27T12:35:13Z – claude:opus:implementer:implementer – shell_pid=18350 – Assigned agent via action command
- 2026-05-27T12:39:36Z – claude:opus:implementer:implementer – shell_pid=18350 – Ready for review
