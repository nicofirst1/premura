# Research Plan: Grounded Extensible Engine Research

**Branch**: `master` (target) | **Date**: 2026-05-24 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/grounded-extensible-engine-research-01KSD0D1/spec.md`
**Mission ID**: `01KSD0D18NBW0FG039P6Y78VP6` (mid8: `01KSD0D1`)
**Mission type**: `research`

## Summary

Produce a decision-ready research package for Premura's Stage 2 engine that answers two coupled questions at once: what kinds of signal functions are scientifically grounded enough to belong in the engine, and how contributors or coding agents should add those functions without weakening trust.

The deliverable is not code. It is a compact research output that: maps the current Stage 2 intent already committed in repo docs and code; defines a plain-English taxonomy for health directions, question shapes, and engine function families; states an accept/defer/reject rubric for proposed functions; defines a contributor contract and reviewer gate; evaluates the current `SignalSpec` / registry seam; identifies the baseline-profile dependency tied to issue `#6`; ranks the next 3 to 7 quick-win Stage 2 functions; and recommends the next mission sequence plus the doc files to align after acceptance.

Two assumptions drive this plan:

- The simplest correct path is **doc-first research**, not a half-implementation of a plugin system or new signal code.
- The current Stage 2 seam is useful enough to analyze, but too narrow to treat as the finished contributor contract.

## Research Context

**Language / runtime under study**: Python 3.11 project with the Stage 2 seam in `src/premura/engine/`.
**Current Stage 2 contract already shipped**: `SignalSpec`, `REGISTRY`, `compute`, `list_by_domain`, `check_inputs_available`, `list_unavailable`, and built-in lab-ratio signals in `src/premura/engine/lab_ratios.py`.
**Authoritative repo boundaries**: `docs/architecture/STAGES.md` says Stage 2 stays deterministic, local, and responsible for validity, missing-data policy, derived signals, and signal selection.
**Known debt to account for**: `docs/architecture/STAGES.md` records that today's MCP tools still read warehouse tables directly as a temporary exception while Stage 2 remains thin.
**Existing ontology support**: `src/premura/dim_metric.yaml` and `docs/architecture/UPDATE_STRATEGY.md` already define validity windows, missing-data policy, and the `derived:` namespace reserved for engine outputs.
**Product framing to preserve**: `docs/history/product/VISION.md`, `docs/product/ROADMAP.md`, `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`, and `docs/operations/STATUS.md` all position Stage 2 as the deterministic layer that turns warehouse rows into answerable signals and supports later MCP/UI teaching work.

## Charter Check

The plan stays inside the current charter:

- **Scientific grounding is mandatory**: recommendations must cite either repo docs or explicit outside evidence and must avoid overconfident medical claims.
- **Local-first / offline by default**: no recommended Stage 2 function may depend on background network access or LLM behavior.
- **Stage fidelity**: Stage 2 remains deterministic Python; Stage 3 remains the model-facing tool boundary; Stage 4 remains interview and teaching.
- **Docs stay synchronized**: the research output must name which docs need follow-up alignment once conclusions are accepted.

Because this mission is research-only, no code-quality gate run is required for completion; the quality bar here is traceability, clarity, and decision usefulness.

## Project Structure

### Mission artifacts

```
kitty-specs/grounded-extensible-engine-research-01KSD0D1/
├── spec.md                         # Authoritative mission spec
├── plan.md                         # This file
├── tasks.md                        # Work-package breakdown created next
├── findings.md                     # Final research output for this mission
└── meta.json                       # Mission identity record
```

### Primary source set for this mission

```
docs/architecture/
├── STAGES.md                       # Stage boundaries and the temporary direct-read exception
└── UPDATE_STRATEGY.md              # Derived-signal invalidation and rebuild policy

docs/product/
├── VISION.md                       # Long-term product trajectory and health directions
├── ROADMAP.md                      # Shipped Stage 2/3 slices and next analytical questions
└── FULL_APP_DEVELOPMENT_PLAN.md    # Phase-level sequencing and current Stage 2 framing

docs/operations/
└── STATUS.md                       # What is actually shipped today

docs/adr/
└── 0002-mcp-local-warehouse-boundary.md   # Locked Stage 2 -> Stage 3 boundary assumption

src/premura/
├── engine/
│   ├── __init__.py                 # Public Stage 2 API surface
│   ├── _registry.py                # SignalSpec registration seam
│   └── lab_ratios.py               # First concrete Stage 2 signal functions
├── parsers/CONTRACT.md             # Useful comparison point for a contributor-facing contract
└── dim_metric.yaml                 # Current metric categories, validity windows, missing-data policy
```

## Research Order

The mission breaks cleanly into five dependent tracks. The order matters because later tracks should build on the evidence gathered in earlier ones, not re-litigate it.

### Track 1 - Map what is already committed

Goal: separate stable intent, known debt, and open questions across current docs and code.

Steps:

1. Read the Stage 2 commitments in `STAGES.md`, `STATUS.md`, `ROADMAP.md`, `FULL_APP_DEVELOPMENT_PLAN.md`, and the current engine package.
2. Build a three-column inventory: **stable intent**, **known debt / temporary exceptions**, **open design questions**.
3. Record any terminology drift so the final output uses one consistent plain-English vocabulary.

Output:

- The repo-baseline section of `findings.md` that satisfies FR-001.

### Track 2 - Define the Stage 2 taxonomy

Goal: make Stage 2 discussable in one shared language that separates user goals from engine behavior.

Steps:

1. Start from the health directions already named in `VISION.md` and `STAGES.md`.
2. Normalize them into a practical first-wave set for Premura rather than an exhaustive health ontology.
3. For each direction, list the recurring user-question shapes Premura should answer first: current status, trend, change after an event, comparison to a baseline, cross-signal interpretation, and similar patterns.
4. Map each question shape to one or more engine function families, explicitly keeping Stage 2 logic separate from Stage 3 statistics tooling and Stage 4 teaching behavior.

Output:

- The directions / question-shapes / function-families sections that satisfy FR-002.

### Track 3 - Define the grounding and contribution gate

Goal: decide what makes a proposed engine function acceptable and how a contributor proves it.

Steps:

1. Compare the existing parser contract (`src/premura/parsers/CONTRACT.md`) with the current engine seam to identify what a Stage 2 contributor contract should borrow and what must differ.
2. Define the minimum evidence package for a new Stage 2 function: rationale, intended question, required inputs, output shape, caveats, uncertainty handling, test expectations, and reviewer notes.
3. Write an accept / defer / reject rubric for scientific grounding, with worked examples including at least one clear reject and one clear defer case.
4. Compress the review gate into 10 or fewer pass/fail checks so it stays usable in routine review.

Output:

- The grounding rubric, contributor contract, and reviewer gate that satisfy FR-003, FR-004, FR-005, and NFR-003.

### Track 4 - Evaluate the current seam and the baseline-profile dependency

Goal: say which current Stage 2 pieces survive into the future model and which do not.

Steps:

1. Evaluate `SignalSpec`, the registry model, `compute`, `list_by_domain`, input-availability checks, revisions, and the `derived:` persistence pattern.
2. Mark each seam element as **keep**, **change**, or **defer**, with one sentence explaining why.
3. Identify which useful Stage 2 functions require stable profile context such as height, birth date, sex, or similar attributes.
4. Separate those profile attributes from ordinary observed measurements and tie the unresolved storage/update model to GitHub issue `#6`.

Output:

- The seam-evaluation section for FR-006 and the profile-dependency section for FR-007.

### Track 5 - Rank the next functions and follow-on missions

Goal: end with concrete next steps rather than only framework language.

Steps:

1. Generate a candidate set biased toward commonly available data already visible in `STATUS.md` and `dim_metric.yaml`.
2. Score candidates against user value, input availability, scientific clarity, caveat burden, Stage 2 fit, and dependency on profile attributes.
3. Rank 3 to 7 quick-win functions and tag each with confidence level: `strong`, `moderate`, or `exploratory`.
4. Translate the shortlist into the recommended next mission order: which work becomes implementation, which remains research, and which gets deferred.
5. Name the docs that should be updated after acceptance so repo intent, contribution guidance, and stage boundaries stay aligned.

Output:

- The quick-win shortlist, next-mission sequence, and doc-alignment appendix that satisfy FR-008, FR-009, FR-010, NFR-002, NFR-004, and NFR-005.

## Evidence Rules

Every top-level recommendation in `findings.md` must be traceable to one of two source classes:

1. **In-repo sources**: the docs and code listed above.
2. **Explicit outside evidence**: cited papers, guidelines, or reputable technical references used to justify the scientific-grounding rubric or a candidate function's plausibility.

This mission should prefer existing repo evidence when the question is about Premura's boundaries or direction, and outside evidence when the question is whether a function is scientifically grounded enough to recommend.

## Complexity Control

The simplest acceptable output is a single coherent `findings.md`, not a miniature governance system.

Deliberate non-goals during planning:

- No executable engine plugin architecture.
- No new `SignalSpec` fields unless the research conclusion explicitly shows they are necessary.
- No broad rewrite of `VISION.md`, `ROADMAP.md`, or `STAGES.md` inside this mission.
- No attempt to turn every promising health question into a first-wave Stage 2 function.

## Risks And Mitigations

| Risk | Why it matters | Mitigation in this plan |
|---|---|---|
| Taxonomy drifts into UI or MCP behavior | The mission is about Stage 2; blurred boundaries would weaken later implementation work. | Track 2 explicitly maps question shapes to Stage 2 function families and rejects Stage 3/4 concerns that do not belong there. |
| The grounding rubric becomes vague prose | Future contributors would still not know what counts as acceptable. | Track 3 requires explicit accept/defer/reject criteria plus worked examples and a <=10-check reviewer gate. |
| Quick wins skew toward interesting but data-hungry ideas | The next mission would help few users. | Track 5 scores candidates against data availability seen in `STATUS.md` and current ontology coverage. |
| Profile-attribute needs get hidden inside the shortlist | Later implementation work would silently depend on unresolved storage design. | Track 4 forces a dedicated profile-data section tied to issue `#6`. |
| Repo intent and shipped behavior disagree | The final recommendation could chase an imagined architecture instead of the real codebase. | Track 1 starts from shipped docs and code, and `findings.md` must separate stable commitments from known debt. |

## Verification For This Planning Step

Planning is complete when:

- `plan.md` names the concrete source set, research tracks, outputs, and decision rules.
- The plan clearly stays research-level and does not smuggle in implementation scope.
- The plan ends in a decision-ready output, not an open-ended literature survey.
- No unresolved clarification markers remain in the plan.

## Next Phase

`/spec-kitty.tasks` should break this research plan into work packages. Suggested split:

- **WP01** - Repo baseline inventory (stable intent, debt, open questions).
- **WP02** - Taxonomy draft (directions, question shapes, function families).
- **WP03** - Grounding rubric + contributor contract + reviewer gate.
- **WP04** - Current seam evaluation + baseline-profile dependency analysis.
- **WP05** - Quick-win ranking + follow-on mission order + doc-alignment list.
- **WP06** - Final synthesis into `findings.md` with source-backed citations.

WP06 depends on WP01 through WP05. WP03 depends on WP01 and WP02. WP05 depends on WP01, WP02, and WP04.
