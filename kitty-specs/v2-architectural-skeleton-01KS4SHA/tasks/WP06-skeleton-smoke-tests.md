---
work_package_id: WP06
title: Skeleton Smoke Tests
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
requirement_refs:
- FR-019
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T021
- T022
- T023
- T024
- T025
- T026
agent: "claude:opus-4-7:implementer:implementer"
shell_pid: "11032"
history:
- timestamp: '2026-05-21T09:53:12Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: tests/
execution_mode: code_change
owned_files:
- tests/test_skeleton.py
- kitty-specs/v2-architectural-skeleton-01KS4SHA/checklists/requirements.md
tags: []
---

# Work Package Prompt: WP06 - Skeleton Smoke Tests

## Objective

Create the dedicated smoke-test file for the skeleton mission, run the requested verification commands, and update the mission checklist based on actual outcomes.

This WP depends on all prior implementation WPs because it validates the integrated skeleton surface rather than a single isolated file group.

## Owned Surface

- `tests/test_skeleton.py`
- `kitty-specs/v2-architectural-skeleton-01KS4SHA/checklists/requirements.md`

Do not expand ownership beyond these files. Fixes required in code surfaces belong in the owning WP lane unless they are trivial coordination fixes already merged before this WP begins.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP06 --agent <name>`

## Subtasks

### T021 - Add import and stub behavior tests

**Purpose**

Verify the new Stage 2/3/4 and parser-contract modules import cleanly and still behave as a pure skeleton.

**Required coverage**

- `premura.engine` imports and re-exports the expected surface.
- `premura.mcp` and `premura.ui` import.
- `premura.parsers._lang` and `premura.parsers.lookup` import.
- `PluginParseResult` and `PluginParser` import from `premura.parsers.base`.
- Each callable stub raises `NotImplementedError`.

**Naming guidance**

- Keep test names traceable to the FRs they cover.
- Prefer grouped test functions over one tiny test per assertion if grouping keeps the file readable.

### T022 - Add skill packaging/idempotency tests

**Purpose**

Verify the one intentional behavioral addition (`install-skills`) and the package-data contract.

**Required coverage**

- `importlib.resources.files("premura")...SKILL.md` resolves successfully.
- `install_skills(tmp_path)` writes the shipped file on first run.
- A second call returns `[]` and leaves file content unchanged.
- The installed target path matches `.claude/skills/parser-generator/SKILL.md`.

**Keep in mind**

- Tests should avoid depending on the operator's real home directory.
- Use temp directories for the install target.

### T023 - Add ontology migration and seed tests

**Purpose**

Prove that the storage/catalog WP actually satisfies the schema and seed contract.

**Required coverage**

- Migration `002` adds the six new columns.
- Re-running migrations is idempotent.
- `seed_dim_metric()` works for rows missing new keys and rows providing them.
- YAML row count is `>= 140`.
- Every row has non-empty `category`.
- Every `lab:*` row has `loinc` set.

### T024 - Structure the test file around FR coverage

**Purpose**

Make the test file reviewable as a contract-verification artifact rather than a random bag of assertions.

**Required structure**

- Cover FR-001 through FR-017 in `tests/test_skeleton.py`.
- Keep the cross-repo doc grep checks out of this file where the spec says they are already covered elsewhere.
- Use helper functions or fixtures only when they reduce duplication meaningfully.

**Non-goal**

- Do not rewrite unrelated v1 tests.

### T025 - Run the verification commands and resolve issues

**Purpose**

Back the smoke tests with the broader mission-level verification required by the spec.

**Run these commands**

```bash
uv run python -m pytest tests/test_skeleton.py -q
uv run python -m pytest -q
uv run hpipe doctor
uv run ruff check src/premura/{engine,mcp,ui,skills,parsers}
uv run mypy src/premura/{engine,mcp,ui,skills,parsers}
```

**Expectation**

- Fix issues that belong to the skeleton surface if any of these fail.
- If an external or pre-existing environment issue blocks a command, document it clearly instead of papering over it.

### T026 - Update the implementation checklist

**Purpose**

Reflect the post-implementation status in the mission checklist.

**Required changes**

- Update `kitty-specs/v2-architectural-skeleton-01KS4SHA/checklists/requirements.md`.
- Flip items that are now evidenced by the implemented/tested skeleton.
- Keep notes factual and tied to observed verification results.

**Important**

- Do not mark items complete based on intention alone.
- If something could not be fully verified, say so explicitly.

## Validation Strategy

This WP's own validation is the verification ladder above. In review, the file should also make it easy to answer:

- does the skeleton import cleanly?
- do the stubs remain stubs?
- does package-data installation work?
- does the ontology seed/migration contract hold?

## Definition Of Done

- `tests/test_skeleton.py` exists and covers FR-001 through FR-017 as intended.
- The targeted smoke-test command passes.
- Full `pytest -q` passes.
- `hpipe doctor` passes.
- `ruff` and `mypy` pass on the new code surfaces.
- `checklists/requirements.md` reflects post-implementation evidence.

## Risks And Watchouts

- This WP can turn into a dumping ground for code fixes; keep ownership clear.
- Command failures may expose integration issues across multiple WPs, so coordinate carefully.
- Checklist drift is easy if results are not recorded immediately after verification.

## Reviewer Guidance

Review the test file as the mission's executable acceptance contract. The most important question is whether a future maintainer could read `tests/test_skeleton.py` and understand exactly what the skeleton guarantees today.

## Activity Log

- 2026-05-21T11:42:49Z – claude:opus-4-7:implementer:implementer – shell_pid=11032 – Started implementation via action command
- 2026-05-21T11:51:25Z – claude:opus-4-7:implementer:implementer – shell_pid=11032 – Ready for review: skeleton smoke tests cover ontology, engine, parser protocol, stub stages, skills bundling, and CONTRACT.md/CLI — 27 new tests, 52/52 pytest green
