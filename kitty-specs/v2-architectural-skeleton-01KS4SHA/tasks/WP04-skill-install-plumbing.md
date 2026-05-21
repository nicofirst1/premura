---
work_package_id: WP04
title: Skill Install Plumbing
dependencies:
- WP03
requirement_refs:
- FR-011
- FR-012
- FR-013
- FR-014
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
- T016
- T017
history:
- timestamp: '2026-05-21T09:53:12Z'
  agent: gpt-5.4
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/skills/
execution_mode: code_change
owned_files:
- src/premura/skills/**
- src/premura/cli.py
- ops/bootstrap.sh
tags: []
---

# Work Package Prompt: WP04 - Skill Install Plumbing

## Objective

Ship the parser-generator skill as package data and expose the one intentional new behavioral path for this mission: `hpipe install-skills`.

This WP depends on WP03 because the skill manifest must point at the shipped `src/premura/parsers/CONTRACT.md` surface.

## Owned Surface

- `src/premura/skills/__init__.py`
- `src/premura/skills/parser-generator/SKILL.md`
- `src/premura/cli.py`
- `ops/bootstrap.sh`

Do not modify any other package data or command surfaces.

## Branch Strategy

- Planning/base branch: `master`
- Final merge target: `master`
- Execution branch allocation: computed later from `lanes.json`
- Implementation command: `spec-kitty agent action implement WP04 --agent <name>`

## Subtasks

### T014 - Create `skills/parser-generator/SKILL.md`

**Purpose**

Ship the Claude Code skill manifest inside the Python package.

**Required changes**

- Create `src/premura/skills/parser-generator/SKILL.md`.
- Include YAML frontmatter with at least:
  - `name:`
  - `description:`
- Put trigger phrases in the `description:` body, matching the conventions found in existing Claude Code skills.
- In the body, point the reader to `src/premura/parsers/CONTRACT.md` as the authoritative parser contract.

**Do not do**

- Do not embed the full decision tree inline.
- Do not add executable behavior, API calls, or a full generation playbook.

### T015 - Implement `install_skills()`

**Purpose**

Materialize shipped skill files under `.claude/skills/` using package resources and idempotent writes.

**Required changes**

- Create or fill in `src/premura/skills/__init__.py`.
- Expose `install_skills(target_root: Path) -> list[Path]`.
- Discover shipped `SKILL.md` files via `importlib.resources.files("premura.skills")`.
- Copy each skill to `target_root/.claude/skills/<skill-name>/SKILL.md`.
- Use sha256 comparison so unchanged files are not rewritten.
- Return the list of files actually written.

**Implementation constraints**

- No new dependencies.
- No symlink-only solution; the user-visible contract is copied materialization.
- Keep the helper small and self-contained.

### T016 - Add the `install-skills` CLI verb

**Purpose**

Expose skill installation through the public CLI surface.

**Required changes**

- Extend `src/premura/cli.py` with `@app.command(name="install-skills")`.
- Call `skills.install_skills(Path.cwd())`.
- Print written files on the first run.
- Print `no changes` when nothing was rewritten.

**Do not do**

- Do not alter existing command behavior or parser orchestration.
- Do not add extra verbs.
- Do not refactor the whole CLI file for style.

### T017 - Extend bootstrap with TTY/env gating

**Purpose**

Hook the new CLI command into bootstrap while preserving non-interactive safety.

**Required changes**

- Extend `ops/bootstrap.sh` after the `uv sync --extra dev` step.
- Run `uv run hpipe install-skills` only when:
  - `HPIPE_SKIP_SKILLS` is not `1`, and
  - the shell is interactive enough per `[[ -t 0 ]]`.

**Behavior rules**

- CI/non-interactive contexts should skip skill installation automatically.
- Manual local bootstrap should install the skill unless the env var explicitly disables it.

## Validation Strategy

Primary checks for this WP:

```bash
uv run hpipe install-skills
uv run hpipe install-skills
uv run python -c "from importlib.resources import files; assert files('premura').joinpath('skills/parser-generator/SKILL.md').is_file()"
```

Expected outcomes:

- first command writes the skill file,
- second command prints `no changes`,
- resource lookup works in editable installs,
- bootstrap contains the documented gating strings.

## Definition Of Done

- Shipped skill manifest exists and points back to the authoritative contract.
- `install_skills()` exists and is idempotent.
- `hpipe install-skills` is wired and user-readable.
- `ops/bootstrap.sh` invokes the command behind the required guards.

## Risks And Watchouts

- Package-resource traversal is the main hidden risk; keep it simple and deterministic.
- CLI output wording matters because tests and success criteria inspect it.
- Bootstrap is a shared operational script; append-only discipline matters.

## Reviewer Guidance

Review end-to-end from package data to installed file path. The key question is whether the user can bootstrap the repo and have Claude discover the shipped skill without any manual copying.
