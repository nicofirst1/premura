# Tasks: Grounded Extensible Engine Research

**Mission**: `grounded-extensible-engine-research-01KSD0D1`
**Mission ID**: `01KSD0D18NBW0FG039P6Y78VP6`
**Generated**: `2026-05-24T13:02:16Z`
**Planning Branch**: `master`
**Merge Target**: `master`
**Feature Dir**: `/Users/nbrandizzi/repos/personal/premura/kitty-specs/grounded-extensible-engine-research-01KSD0D1`

## Branch Context

- Current branch at task generation: `master`
- Planning/base branch: `master`
- Final merge target: `master`
- Branches match expected planning context: `true`
- Branch strategy: planning artifacts were generated on `master`; execution worktrees are allocated later per computed lane from `lanes.json`, and all completed work merges back into `master`.

## Work Package Overview

| WP | Title | Priority | Dependencies | Prompt | Estimated Prompt Size |
|---|---|---|---|---|---|
| WP01 | Repo Baseline Inventory | High | None | `tasks/WP01-repo-baseline-inventory.md` | ~280 lines |
| WP02 | Stage 2 Taxonomy | High | WP01 | `tasks/WP02-stage2-taxonomy.md` | ~270 lines |
| WP03 | Grounding And Contribution Gate | High | WP01, WP02 | `tasks/WP03-grounding-and-contribution-gate.md` | ~340 lines |
| WP04 | Current Seam And Profile Dependency | High | WP01 | `tasks/WP04-current-seam-and-profile-dependency.md` | ~280 lines |
| WP05 | Quick-Win Ranking And Alignment | High | WP01, WP02, WP04 | `tasks/WP05-quick-win-ranking-and-alignment.md` | ~330 lines |
| WP06 | Final Findings Synthesis | High | WP01, WP02, WP03, WP04, WP05 | `tasks/WP06-final-findings-synthesis.md` | ~300 lines |

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Compile the authoritative repo source set for Stage 2 and record which documents and code surfaces are in scope for the research baseline. | WP01 |  | [D] |
| T002 | Separate current Stage 2 intent into stable commitments, known debt, and open design questions. | WP01 |  | [D] |
| T003 | Capture terminology drift and normalize the plain-English vocabulary the mission will use. | WP01 |  | [D] |
| T004 | Draft the repo-baseline research artifact that satisfies FR-001 and can feed the later synthesis step. | WP01 |  | [D] |
| T005 | Normalize the first-wave health directions Premura should reason about in Stage 2. | WP02 |  | [D] |
| T006 | Enumerate the recurring user-question shapes Stage 2 should answer first within those directions. | WP02 |  | [D] |
| T007 | Map question shapes to engine function families while keeping Stage 2 separate from Stage 3 and Stage 4 behavior. | WP02 |  | [D] |
| T008 | Draft the taxonomy research artifact with examples and traceable links back to repo sources. | WP02 |  | [D] |
| T009 | Compare the parser contribution contract with the current engine seam and identify what a Stage 2 contribution contract should borrow or reject. | WP03 |  |
| T010 | Draft the scientific grounding rubric with explicit accept, defer, and reject criteria. | WP03 |  |
| T011 | Draft the contributor submission contract for new engine functions, including required rationale, inputs, outputs, caveats, and reviewer notes. | WP03 |  |
| T012 | Compress the reviewer gate into 10 or fewer pass/fail checks. | WP03 |  |
| T013 | Add worked examples that show at least one accept case, one defer case, and one reject case. | WP03 |  |
| T014 | Audit the current Stage 2 seam elements already shipped in code and docs. | WP04 |  |
| T015 | Mark each seam element as keep, change, or defer with a brief rationale. | WP04 |  |
| T016 | Identify which useful engine functions depend on baseline personal profile attributes and why those inputs are not ordinary observed measurements. | WP04 |  |
| T017 | Connect the unresolved baseline-profile storage/update problem to issue `#6` and draft the dedicated dependency analysis artifact. | WP04 |  |
| T018 | Build a candidate pool of quick-win engine functions biased toward common data already visible in shipped sources and ontology coverage. | WP05 |  |
| T019 | Score candidates against user value, input availability, scientific clarity, caveat burden, Stage 2 fit, and profile-data dependency. | WP05 |  |
| T020 | Rank 3 to 7 quick-win functions and tag each with confidence level. | WP05 |  |
| T021 | Recommend the next mission sequence, separating follow-on implementation work, follow-on research, and deferred questions. | WP05 |  |
| T022 | Name the docs that should be updated after acceptance and explain the role of each update. | WP05 |  |
| T023 | Create the final `findings.md` structure with an executive summary and citation approach that can absorb the outputs of WP01 through WP05. | WP06 |  |
| T024 | Merge the prior research artifacts into one coherent findings document that covers FR-001 through FR-010 end to end. | WP06 |  |
| T025 | Run a coverage and consistency pass against the spec, checklist, and mission success criteria, tightening any weak sections. | WP06 |  |
| T026 | Review the final findings package for plain-English vocabulary, traceability, and strict Stage 2 boundary fidelity. | WP06 |  |

## Work Packages

### WP01 - Repo Baseline Inventory

- Prompt: `tasks/WP01-repo-baseline-inventory.md`
- Goal: produce the source-backed baseline inventory that separates what Premura has already committed about Stage 2 from what remains debt or open design space.
- Priority: High
- Independent validation: the WP outputs a clear baseline artifact that names stable commitments, known debt, open design questions, and terminology choices with repo citations.
- Dependencies: None.
- Owned files: `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/01-repo-baseline.md`
- Estimated prompt size: ~280 lines

Included subtasks:
- [x] T001 Compile the authoritative repo source set for Stage 2 and record which documents and code surfaces are in scope for the research baseline. (WP01)
- [x] T002 Separate current Stage 2 intent into stable commitments, known debt, and open design questions. (WP01)
- [x] T003 Capture terminology drift and normalize the plain-English vocabulary the mission will use. (WP01)
- [x] T004 Draft the repo-baseline research artifact that satisfies FR-001 and can feed the later synthesis step. (WP01)

Implementation sketch:
1. Read the Stage 2 documents and shipped engine code named in `plan.md`.
2. Build a three-way inventory: stable commitments, temporary debt, and open questions.
3. Note terminology mismatches and choose one plain-English vocabulary set that follows `CONTEXT.md`.
4. Write the baseline artifact in `research/01-repo-baseline.md` with citations that later WPs can reuse.

Parallel opportunities:
- None inside the WP. The baseline needs one coherent pass over the source set before downstream work can safely build on it.

Risks:
- Mixing aspirational roadmap language with shipped behavior could distort later recommendations.
- Missing the known Stage 3 direct-read exception would make later gate design less grounded.

Reviewer focus:
- Confirm the artifact cleanly separates stable intent from debt and open questions.
- Confirm the language stays consistent with the repo's plain-English vocabulary rules.

### WP02 - Stage 2 Taxonomy

- Prompt: `tasks/WP02-stage2-taxonomy.md`
- Goal: define the shared Stage 2 language for health directions, user-question shapes, and engine function families.
- Priority: High
- Independent validation: the WP outputs a taxonomy artifact that names directions, question shapes, and function families with examples and clean Stage 2 boundaries.
- Dependencies: WP01.
- Owned files: `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/02-stage2-taxonomy.md`
- Estimated prompt size: ~270 lines

Included subtasks:
- [x] T005 Normalize the first-wave health directions Premura should reason about in Stage 2. (WP02)
- [x] T006 Enumerate the recurring user-question shapes Stage 2 should answer first within those directions. (WP02)
- [x] T007 Map question shapes to engine function families while keeping Stage 2 separate from Stage 3 and Stage 4 behavior. (WP02)
- [x] T008 Draft the taxonomy research artifact with examples and traceable links back to repo sources. (WP02)

Implementation sketch:
1. Start from the directions already named in `VISION.md` and `STAGES.md`.
2. Normalize them into a practical first-wave set rather than an exhaustive ontology.
3. Map recurring question shapes to function families and explicitly exclude Stage 3 statistics-tool or Stage 4 teaching concerns.
4. Write the taxonomy artifact in `research/02-stage2-taxonomy.md` with concrete examples.

Parallel opportunities:
- None worth splitting. Direction choice, question-shape normalization, and function-family mapping should be kept in one consistent pass.

Risks:
- The taxonomy could drift into UI or MCP concerns instead of staying in Stage 2.
- The direction set could become too broad to guide real follow-on work.

Reviewer focus:
- Confirm the taxonomy is practical and bounded.
- Confirm each function family clearly belongs to Stage 2 rather than Stage 3 or Stage 4.

### WP03 - Grounding And Contribution Gate

- Prompt: `tasks/WP03-grounding-and-contribution-gate.md`
- Goal: define what counts as a scientifically grounded engine function and what contributors must provide for review.
- Priority: High
- Independent validation: the WP outputs a grounding rubric, a contributor contract, a reviewer gate of 10 or fewer checks, and worked examples for accept/defer/reject decisions.
- Dependencies: WP01, WP02.
- Owned files: `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/03-grounding-and-contribution-gate.md`
- Estimated prompt size: ~340 lines

Included subtasks:
- [ ] T009 Compare the parser contribution contract with the current engine seam and identify what a Stage 2 contribution contract should borrow or reject. (WP03)
- [ ] T010 Draft the scientific grounding rubric with explicit accept, defer, and reject criteria. (WP03)
- [ ] T011 Draft the contributor submission contract for new engine functions, including required rationale, inputs, outputs, caveats, and reviewer notes. (WP03)
- [ ] T012 Compress the reviewer gate into 10 or fewer pass/fail checks. (WP03)
- [ ] T013 Add worked examples that show at least one accept case, one defer case, and one reject case. (WP03)

Implementation sketch:
1. Use the baseline inventory and taxonomy to decide what the engine is actually trying to admit.
2. Compare the parser contract's strengths with the current engine seam so the new contract borrows only what fits Stage 2.
3. Draft the scientific grounding rubric, then derive the contributor contract and the reviewer gate from it.
4. Add worked examples that prove the rubric is usable, not just aspirational prose.

Parallel opportunities:
- T012 can begin after T010 and T011 have rough drafts, but the WP is best treated as one cohesive pass because the rubric, contract, and gate must align.

Risks:
- The rubric may collapse into vague prose instead of a decision rule.
- The reviewer gate may become too long to use routinely.
- The contributor contract may accidentally imply a plugin mechanism that the mission is not actually choosing.

Reviewer focus:
- Confirm the gate is compact and executable.
- Confirm the worked examples include meaningful defer and reject cases, not only easy accept cases.

### WP04 - Current Seam And Profile Dependency

- Prompt: `tasks/WP04-current-seam-and-profile-dependency.md`
- Goal: evaluate the current Stage 2 seam element by element and make the profile-data dependency explicit instead of leaving it hidden in future function ideas.
- Priority: High
- Independent validation: the WP outputs a keep/change/defer assessment of current seam elements plus a dedicated baseline-profile dependency analysis that points to issue `#6`.
- Dependencies: WP01.
- Owned files: `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/04-engine-seam-and-profile-dependency.md`
- Estimated prompt size: ~280 lines

Included subtasks:
- [ ] T014 Audit the current Stage 2 seam elements already shipped in code and docs. (WP04)
- [ ] T015 Mark each seam element as keep, change, or defer with a brief rationale. (WP04)
- [ ] T016 Identify which useful engine functions depend on baseline personal profile attributes and why those inputs are not ordinary observed measurements. (WP04)
- [ ] T017 Connect the unresolved baseline-profile storage/update problem to issue `#6` and draft the dedicated dependency analysis artifact. (WP04)

Implementation sketch:
1. Walk the shipped Stage 2 surface in `src/premura/engine/` and the related architecture docs.
2. Evaluate each seam element against the research mission's goals and mark it keep, change, or defer.
3. Identify where height, birth date, sex, and similar attributes enter the picture for useful early functions.
4. Write the combined seam/profile artifact in `research/04-engine-seam-and-profile-dependency.md` and make the dependency on issue `#6` explicit.

Parallel opportunities:
- None. The seam evaluation and the profile dependency analysis inform each other and should be written together.

Risks:
- The seam evaluation could drift into implementation design rather than contract-level guidance.
- Profile-attribute needs could be buried in examples instead of elevated as an explicit dependency.

Reviewer focus:
- Confirm every current seam element gets a clear disposition.
- Confirm the profile-data dependency is explicit and linked to issue `#6`.

### WP05 - Quick-Win Ranking And Alignment

- Prompt: `tasks/WP05-quick-win-ranking-and-alignment.md`
- Goal: turn the research framework into a concrete first-wave shortlist, a follow-on mission order, and a doc-alignment plan.
- Priority: High
- Independent validation: the WP outputs a ranked set of 3 to 7 quick-win functions, each with confidence, caveats, dependencies, and a recommendation for what should happen next.
- Dependencies: WP01, WP02, WP04.
- Owned files: `kitty-specs/grounded-extensible-engine-research-01KSD0D1/research/05-quick-win-ranking-and-alignment.md`
- Estimated prompt size: ~330 lines

Included subtasks:
- [ ] T018 Build a candidate pool of quick-win engine functions biased toward common data already visible in shipped sources and ontology coverage. (WP05)
- [ ] T019 Score candidates against user value, input availability, scientific clarity, caveat burden, Stage 2 fit, and profile-data dependency. (WP05)
- [ ] T020 Rank 3 to 7 quick-win functions and tag each with confidence level. (WP05)
- [ ] T021 Recommend the next mission sequence, separating follow-on implementation work, follow-on research, and deferred questions. (WP05)
- [ ] T022 Name the docs that should be updated after acceptance and explain the role of each update. (WP05)

Implementation sketch:
1. Build a candidate pool from the data the project already ingests or clearly anticipates.
2. Score the candidates with one explicit rubric so the ranking is transparent.
3. Convert the shortlist into follow-on mission order and doc-alignment actions.
4. Write the ranking and alignment artifact in `research/05-quick-win-ranking-and-alignment.md`.

Parallel opportunities:
- T022 can begin once the likely recommendation direction is clear, but keeping the ranking and alignment work together is preferable because doc updates should reflect the chosen next steps.

Risks:
- The shortlist may skew toward mathematically easy ideas that are weakly grounded.
- The mission-order recommendations may bury the profile-data dependency or overcommit to functions with sparse inputs.

Reviewer focus:
- Confirm the shortlist is decision-ready rather than just a brainstorm.
- Confirm at least two candidates are useful with commonly available non-lab data.

### WP06 - Final Findings Synthesis

- Prompt: `tasks/WP06-final-findings-synthesis.md`
- Goal: assemble the prior research slices into the single decision-ready `findings.md` that this mission ultimately promises.
- Priority: High
- Independent validation: `findings.md` covers FR-001 through FR-010, names the profile-data follow-on, includes the ranked shortlist, and stays readable in plain English with traceable citations.
- Dependencies: WP01, WP02, WP03, WP04, WP05.
- Owned files: `kitty-specs/grounded-extensible-engine-research-01KSD0D1/findings.md`
- Estimated prompt size: ~300 lines

Included subtasks:
- [ ] T023 Create the final `findings.md` structure with an executive summary and citation approach that can absorb the outputs of WP01 through WP05. (WP06)
- [ ] T024 Merge the prior research artifacts into one coherent findings document that covers FR-001 through FR-010 end to end. (WP06)
- [ ] T025 Run a coverage and consistency pass against the spec, checklist, and mission success criteria, tightening any weak sections. (WP06)
- [ ] T026 Review the final findings package for plain-English vocabulary, traceability, and strict Stage 2 boundary fidelity. (WP06)

Implementation sketch:
1. Build the document skeleton first so the final synthesis has a stable frame.
2. Merge the WP01-WP05 outputs into one coherent argument instead of concatenating separate notes.
3. Run a strict coverage pass against the spec and success criteria.
4. Tighten language so the final package is readable by the maintainer without software-engineering jargon.

Parallel opportunities:
- None. This WP is the convergence step for all prior research artifacts.

Risks:
- The final synthesis may read like six stitched-together notes instead of one coherent decision package.
- Traceability may get lost if citations are not carried through from earlier artifacts.

Reviewer focus:
- Confirm the findings document reads as one decision-ready package.
- Confirm every functional requirement is visibly satisfied in the final output.
