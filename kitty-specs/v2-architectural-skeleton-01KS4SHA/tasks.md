# Tasks: v2 Architectural Skeleton

**Mission**: `v2-architectural-skeleton-01KS4SHA`
**Mission ID**: `01KS4SHAJFA45WZYXS6XG8EFNE`
**Generated**: `2026-05-21T09:53:12Z`
**Planning Branch**: `master`
**Merge Target**: `master`
**Feature Dir**: `/Users/nbrandizzi/repos/personal/health_export/kitty-specs/v2-architectural-skeleton-01KS4SHA`

## Branch Context

- Current branch at task generation: `master`
- Planning/base branch: `master`
- Final merge target: `master`
- Branches match expected planning context: `true`
- Branch strategy: planning artifacts were generated on `master`; execution worktrees are allocated per computed lane from `lanes.json`, and all completed work merges back into `master`.

## Work Package Overview

| WP | Title | Priority | Dependencies | Prompt | Estimated Prompt Size |
|---|---|---|---|---|---|
| WP01 | Ontology Schema And Seed | High | None | `tasks/WP01-ontology-schema-and-seed.md` | ~330 lines |
| WP02 | Engine Registry Skeleton | High | None | `tasks/WP02-engine-registry-skeleton.md` | ~260 lines |
| WP03 | Parser And UI Contract Stubs | High | None | `tasks/WP03-parser-and-ui-contract-stubs.md` | ~430 lines |
| WP04 | Skill Install Plumbing | High | WP03 | `tasks/WP04-skill-install-plumbing.md` | ~320 lines |
| WP05 | Cross-Cutting Agent Docs | Medium | None | `tasks/WP05-cross-cutting-agent-docs.md` | ~240 lines |
| WP06 | Skeleton Smoke Tests | High | WP01, WP02, WP03, WP04, WP05 | `tasks/WP06-skeleton-smoke-tests.md` | ~420 lines |

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Add `002_dim_metric_ontology.sql` with the six nullable ontology columns and idempotent `ADD COLUMN IF NOT EXISTS` statements. | WP01 |  | [D] |
| T002 | Extend `seed_dim_metric()` to read, insert, and update the six new ontology fields while preserving backward compatibility for rows missing those keys. | WP01 |  | [D] |
| T003 | Add `category` to all existing legacy rows in `src/premura/dim_metric.yaml` without renaming legacy `metric_id`s. | WP01 |  | [D] |
| T004 | Append the new ontology rows to `src/premura/dim_metric.yaml` so the seed reaches the required floor with clinically standard aliases and standards metadata. | WP01 |  | [D] |
| T005 | Create `src/premura/engine/_registry.py` with `SignalSpec`, `REGISTRY`, and the `@signal(...)` decorator contract. | WP02 |  |
| T006 | Create `src/premura/engine/__init__.py` with the Stage 2 docstring, re-exports, and the five `NotImplementedError` API stubs. | WP02 |  |
| T007 | Keep the engine surface import-safe and implementation-free so `REGISTRY` stays empty until future signal modules are imported. | WP02 |  |
| T008 | Append `PluginParseResult` to `src/premura/parsers/base.py` without altering existing parser types or behaviors. | WP03 |  |
| T009 | Append the additive `PluginParser` Protocol to `src/premura/parsers/base.py` with `language_hint`, `declares_metrics()`, and the narrowed parse return type. | WP03 |  |
| T010 | [P] Create `src/premura/parsers/lookup.py` with the reverse-index docstring and `suggest_metric()` stub. | WP03 | [P] |
| T011 | [P] Create `src/premura/parsers/_lang/__init__.py` with the local-only language-detection/translation TODO contract and stub. | WP03 | [P] |
| T012 | Create `src/premura/parsers/CONTRACT.md` with the standards-first parser workflow, alias rules, and reserved-namespace guidance. | WP03 |  |
| T013 | [P] Create `src/premura/mcp/__init__.py` and `src/premura/ui/__init__.py` with their stage docstrings, stubs, and layering assertions. | WP03 | [P] |
| T014 | Create the shipped parser-generator skill manifest at `src/premura/skills/parser-generator/SKILL.md`. | WP04 |  |
| T015 | Implement `src/premura/skills/__init__.py::install_skills()` using package resources and sha256-based idempotency. | WP04 |  |
| T016 | Extend `src/premura/cli.py` with `hpipe install-skills`, including human-readable output for writes vs. no-op runs. | WP04 |  |
| T017 | Extend `ops/bootstrap.sh` to run `hpipe install-skills` behind `HPIPE_SKIP_SKILLS` and TTY gating. | WP04 |  |
| T018 | [P] Create repo-root `AGENTS.md` with the standards-first rule and links to `parsers/CONTRACT.md` and the shipped skill. | WP05 | [P] |
| T019 | [P] Create `docs/UPDATE_STRATEGY.md` covering the six update kinds and their handled vs. deferred status. | WP05 | [P] |
| T020 | Align both new docs with the deferred full-rebuild canonical-vocabulary policy and Stage 4 `ui/` terminology. | WP05 |  |
| T021 | Add import-surface and stub-raising tests in `tests/test_skeleton.py` for the engine, MCP/UI, parser stubs, and parser base additions. | WP06 |  |
| T022 | Add skill packaging and idempotency tests in `tests/test_skeleton.py`, covering resource lookup and install behavior. | WP06 |  |
| T023 | Add ontology migration, seed-shape, row-count, and nullable-backward-compat tests in `tests/test_skeleton.py`. | WP06 |  |
| T024 | Organize the smoke tests so they clearly trace back to FR-001 through FR-017 without relying on unrelated v1 test files. | WP06 |  |
| T025 | Run the requested verification commands (`pytest`, `doctor`, `ruff`, `mypy`) and fix test/support issues surfaced by the new skeleton files. | WP06 |  |
| T026 | Update `kitty-specs/v2-architectural-skeleton-01KS4SHA/checklists/requirements.md` to reflect the post-implementation state. | WP06 |  |

## Work Packages

### WP01 - Ontology Schema And Seed

- Prompt: `tasks/WP01-ontology-schema-and-seed.md`
- Goal: land the atomic schema/catalog triple so the warehouse can store the new ontology columns and seed data without changing current v1 behavior.
- Priority: High
- Independent validation: a fresh warehouse applies migration `002`, seeds `hp.dim_metric` successfully, and yields `>=140` seeded rows with non-null categories.
- Dependencies: None.
- Owned files: `src/premura/store/duck.py`, `src/premura/store/migrations/002_dim_metric_ontology.sql`, `src/premura/dim_metric.yaml`
- Estimated prompt size: ~330 lines

Included subtasks:
- [x] T001 Add `002_dim_metric_ontology.sql` with the six nullable ontology columns and idempotent `ADD COLUMN IF NOT EXISTS` statements. (WP01)
- [x] T002 Extend `seed_dim_metric()` to read, insert, and update the six new ontology fields while preserving backward compatibility for rows missing those keys. (WP01)
- [x] T003 Add `category` to all existing legacy rows in `src/premura/dim_metric.yaml` without renaming legacy `metric_id`s. (WP01)
- [x] T004 Append the new ontology rows to `src/premura/dim_metric.yaml` so the seed reaches the required floor with clinically standard aliases and standards metadata. (WP01)

Implementation sketch:
1. Add the new SQL migration with comments explaining idempotency and nullability.
2. Update the seed loader to bind all 11 columns and serialize aliases to JSON.
3. Normalize every existing YAML row with a category, preserving the legacy metric IDs explicitly deferred by the spec.
4. Append the new rows until the ontology floor is satisfied, keeping alias content clinically standard and standards fields populated where required.

Parallel opportunities:
- None worth splitting inside this WP; the migration, loader update, and YAML expansion are intentionally atomic and share the same data surface.

Risks:
- Incorrect YAML shape or unquoted LOINC values can break seeding entirely.
- Loader/schema drift can make `seed_dim_metric()` fail only at runtime.
- It is easy to accidentally rename legacy IDs despite the explicit defer decision.

Reviewer focus:
- Confirm the migration is fully idempotent and nullable.
- Confirm no existing legacy `metric_id` was renamed or removed.
- Confirm new aliases are clinically standard, not raw vendor junk.

### WP02 - Engine Registry Skeleton

- Prompt: `tasks/WP02-engine-registry-skeleton.md`
- Goal: establish the Stage 2 import surface and open-boundary registry contract without shipping any real signal behavior.
- Priority: High
- Independent validation: `from premura.engine import signal, SignalSpec, REGISTRY` succeeds and `REGISTRY == {}` before any future signal module import.
- Dependencies: None.
- Owned files: `src/premura/engine/**`
- Estimated prompt size: ~260 lines

Included subtasks:
- [ ] T005 Create `src/premura/engine/_registry.py` with `SignalSpec`, `REGISTRY`, and the `@signal(...)` decorator contract. (WP02)
- [ ] T006 Create `src/premura/engine/__init__.py` with the Stage 2 docstring, re-exports, and the five `NotImplementedError` API stubs. (WP02)
- [ ] T007 Keep the engine surface import-safe and implementation-free so `REGISTRY` stays empty until future signal modules are imported. (WP02)

Implementation sketch:
1. Implement the minimal registry data model in `_registry.py` exactly per the documented fields/defaults.
2. Re-export the public registry symbols and add the five stub APIs from `engine/__init__.py`.
3. Confirm the module graph does not import any future implementation locations or create registry entries at import time.

Parallel opportunities:
- None; `_registry.py` and `__init__.py` are tightly coupled and small.

Risks:
- Field defaults or types can drift from the spec if the dataclass is improvised.
- Importing anything outside the minimal registry surface can break NFR-008.

Reviewer focus:
- Verify docstring language matches the Stage 2 contract.
- Verify the public surface matches FR-001 through FR-003 exactly.

### WP03 - Parser And UI Contract Stubs

- Prompt: `tasks/WP03-parser-and-ui-contract-stubs.md`
- Goal: land the additive parser-contract surface plus the Stage 3/4 stub packages and the agent-facing parser contract document.
- Priority: High
- Independent validation: imports succeed for `PluginParseResult`, `PluginParser`, `_lang`, `lookup`, `mcp`, and `ui`, and each callable stub raises `NotImplementedError`.
- Dependencies: None.
- Owned files: `src/premura/parsers/base.py`, `src/premura/parsers/lookup.py`, `src/premura/parsers/_lang/**`, `src/premura/parsers/CONTRACT.md`, `src/premura/mcp/**`, `src/premura/ui/**`
- Estimated prompt size: ~430 lines

Included subtasks:
- [ ] T008 Append `PluginParseResult` to `src/premura/parsers/base.py` without altering existing parser types or behaviors. (WP03)
- [ ] T009 Append the additive `PluginParser` Protocol to `src/premura/parsers/base.py` with `language_hint`, `declares_metrics()`, and the narrowed parse return type. (WP03)
- [ ] T010 [P] Create `src/premura/parsers/lookup.py` with the reverse-index docstring and `suggest_metric()` stub. (WP03)
- [ ] T011 [P] Create `src/premura/parsers/_lang/__init__.py` with the local-only language-detection/translation TODO contract and stub. (WP03)
- [ ] T012 Create `src/premura/parsers/CONTRACT.md` with the standards-first parser workflow, alias rules, and reserved-namespace guidance. (WP03)
- [ ] T013 [P] Create `src/premura/mcp/__init__.py` and `src/premura/ui/__init__.py` with their stage docstrings, stubs, and layering assertions. (WP03)

Implementation sketch:
1. Make the append-only additions to `parsers/base.py` first so the rest of the parser surface has a committed type contract.
2. Add the lookup and `_lang` stubs with docstrings that encode their future behavior and privacy boundary.
3. Materialize `parsers/CONTRACT.md` from the planning contract so agents have an authoritative shipped doc.
4. Add the `mcp` and `ui` stub packages with the exact layering language the spec requires.

Parallel opportunities:
- T010, T011, and T013 are parallel-safe after the additive `parsers/base.py` work starts because they touch disjoint files.

Risks:
- `parsers/base.py` must remain behaviorally compatible with existing v1 parser tests.
- The parser contract doc can easily drift from the canonical-vocabulary policy if written from memory instead of the mission docs.
- The Stage 4 package name must remain `ui/`, not the superseded `learn/` name.

Reviewer focus:
- Verify `Parser`, `Measurement`, `Interval`, and `ParseResult` stayed unchanged.
- Verify docstrings include the exact literal strings the tests and FRs expect.
- Verify the parser contract explicitly encodes the clinically-standard alias rule and `vendor:*` fallback policy.

### WP04 - Skill Install Plumbing

- Prompt: `tasks/WP04-skill-install-plumbing.md`
- Goal: ship the parser-generator skill as package data and expose the one intentional new behavior, `hpipe install-skills`, without disturbing current v1 flows.
- Priority: High
- Independent validation: `uv run hpipe install-skills` writes `.claude/skills/parser-generator/SKILL.md` on first run and prints `no changes` on the second run.
- Dependencies: WP03.
- Owned files: `src/premura/skills/**`, `src/premura/cli.py`, `ops/bootstrap.sh`
- Estimated prompt size: ~320 lines

Included subtasks:
- [ ] T014 Create the shipped parser-generator skill manifest at `src/premura/skills/parser-generator/SKILL.md`. (WP04)
- [ ] T015 Implement `src/premura/skills/__init__.py::install_skills()` using package resources and sha256-based idempotency. (WP04)
- [ ] T016 Extend `src/premura/cli.py` with `hpipe install-skills`, including human-readable output for writes vs. no-op runs. (WP04)
- [ ] T017 Extend `ops/bootstrap.sh` to run `hpipe install-skills` behind `HPIPE_SKIP_SKILLS` and TTY gating. (WP04)

Implementation sketch:
1. Write the shipped skill manifest so it points back to `src/premura/parsers/CONTRACT.md` instead of embedding the decision tree.
2. Implement the package-resource copy helper with sha256 comparison and deterministic target paths under `.claude/skills/`.
3. Wire the helper into the CLI command and ensure output matches the spec's success criteria.
4. Hook bootstrap into the new command without changing behavior in CI or non-interactive contexts.

Parallel opportunities:
- None after dependency resolution; the skill manifest, installer, CLI verb, and bootstrap hook form a short integration chain.

Risks:
- Package-resource lookup can fail in editable installs if the helper walks the package tree incorrectly.
- CLI help/output can drift from the expected human-readable strings.
- Bootstrap gating can accidentally change non-interactive behavior if the TTY/env conditions are wrong.

Reviewer focus:
- Confirm `install_skills()` is idempotent and returns only written files.
- Confirm the skill manifest is a stub, not an implementation playbook.
- Confirm bootstrap only appends the new step and does not reorder existing bootstrap actions.

### WP05 - Cross-Cutting Agent Docs

- Prompt: `tasks/WP05-cross-cutting-agent-docs.md`
- Goal: add the repo-level agent pointer doc and update-strategy document that explain how the skeleton should be used and how future warehouse updates are expected to evolve.
- Priority: Medium
- Independent validation: `AGENTS.md` and `docs/UPDATE_STRATEGY.md` exist with the required references and policy statements.
- Dependencies: None.
- Owned files: `AGENTS.md`, `docs/UPDATE_STRATEGY.md`
- Estimated prompt size: ~240 lines

Included subtasks:
- [ ] T018 [P] Create repo-root `AGENTS.md` with the standards-first rule and links to `parsers/CONTRACT.md` and the shipped skill. (WP05)
- [ ] T019 [P] Create `docs/UPDATE_STRATEGY.md` covering the six update kinds and their handled vs. deferred status. (WP05)
- [ ] T020 Align both new docs with the deferred full-rebuild canonical-vocabulary policy and Stage 4 `ui/` terminology. (WP05)

Implementation sketch:
1. Add the short repo-root agent pointer doc first so the top-level navigation exists.
2. Write the update-strategy document with the handled-now vs. future-mission split.
3. Cross-check both docs for the agreed canonical-vocabulary defer/full-rebuild policy and the finalized `ui/` naming.

Parallel opportunities:
- T018 and T019 are parallel-safe because they touch disjoint files.

Risks:
- The docs can easily reintroduce the superseded `learn/` wording.
- The update strategy can accidentally imply in-place vocabulary migration instead of full rebuild.

Reviewer focus:
- Confirm the standards-first rule and authoritative doc links are explicit.
- Confirm the update document distinguishes what this mission lands now vs. what is deferred.

### WP06 - Skeleton Smoke Tests

- Prompt: `tasks/WP06-skeleton-smoke-tests.md`
- Goal: add the dedicated skeleton smoke test file, run the required verification commands, and update the mission checklist to reflect implemented status.
- Priority: High
- Independent validation: `uv run python -m pytest tests/test_skeleton.py -q`, full `pytest -q`, `hpipe doctor`, `ruff`, and `mypy` all pass, and the checklist reflects the shipped state.
- Dependencies: WP01, WP02, WP03, WP04, WP05.
- Owned files: `tests/test_skeleton.py`, `kitty-specs/v2-architectural-skeleton-01KS4SHA/checklists/requirements.md`
- Estimated prompt size: ~420 lines

Included subtasks:
- [ ] T021 Add import-surface and stub-raising tests in `tests/test_skeleton.py` for the engine, MCP/UI, parser stubs, and parser base additions. (WP06)
- [ ] T022 Add skill packaging and idempotency tests in `tests/test_skeleton.py`, covering resource lookup and install behavior. (WP06)
- [ ] T023 Add ontology migration, seed-shape, row-count, and nullable-backward-compat tests in `tests/test_skeleton.py`. (WP06)
- [ ] T024 Organize the smoke tests so they clearly trace back to FR-001 through FR-017 without relying on unrelated v1 test files. (WP06)
- [ ] T025 Run the requested verification commands (`pytest`, `doctor`, `ruff`, `mypy`) and fix test/support issues surfaced by the new skeleton files. (WP06)
- [ ] T026 Update `kitty-specs/v2-architectural-skeleton-01KS4SHA/checklists/requirements.md` to reflect the post-implementation state. (WP06)

Implementation sketch:
1. Build out the new test file in logical groups: imports/stubs, skill plumbing, ontology/migration.
2. Keep the test names and coverage aligned with the FR identifiers to make review straightforward.
3. Run the mission-level verification commands, fix issues that belong to the skeleton surface, then update the checklist with observed outcomes.

Parallel opportunities:
- None; all subtasks converge on the same test file and final checklist update.

Risks:
- The test file can become too coupled to implementation details instead of the public contracts.
- `doctor`, `ruff`, or `mypy` may expose issues outside the new file if the skeleton imports are not minimal.
- The checklist update must be evidence-based, not aspirational.

Reviewer focus:
- Confirm the test file covers FR-001 through FR-017 in the intended grouped way.
- Confirm the verification commands were actually run and any failures resolved.
- Confirm the checklist update reflects the final implementation, not the pre-implementation draft state.
