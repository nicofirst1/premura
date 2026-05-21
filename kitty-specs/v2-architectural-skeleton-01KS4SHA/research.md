# Phase 0 — Research: v2 Architectural Skeleton

> Mission: `v2-architectural-skeleton-01KS4SHA`
> Date: 2026-05-21
> Purpose: Resolve technical unknowns surfaced during `/spec-kitty.plan` discovery before Phase 1 design.

## Inventory of unknowns coming into Phase 0

From the planning interrogation, five unknowns needed resolution before the implementation plan could solidify:

1. Does DuckDB ≥ 1.1 support `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`?
2. How does Hatchling include non-`.py` files (skill `.md`, `dim_metric.yaml`, `.sql` migrations) as package data?
3. What is the canonical Claude Code skill frontmatter schema?
4. What is the typer pattern for registering a CLI verb with a hyphenated name like `install-skills`?
5. Does `importlib.resources.files(...)` work identically in `pip install -e .` editable installs and in wheel installs?

All five resolved as of 2026-05-21.

---

## 1. DuckDB `ADD COLUMN IF NOT EXISTS`

**Decision**: Use `ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS <col> <type>` directly in migration `002_dim_metric_ontology.sql`.

**Rationale**: DuckDB has supported `ADD COLUMN IF NOT EXISTS` since v0.8 (released August 2023). The project pins `duckdb>=1.1,<2` in `pyproject.toml` (line 8), so the syntax is universally available across the supported range. Reference: [DuckDB ALTER TABLE documentation](https://duckdb.org/docs/sql/statements/alter_table).

**Alternatives considered**:
- **`PRAGMA table_info('hp.dim_metric')` + Python-side conditional ALTER**: Would work but requires a Python wrapper around the migration; runs counter to the existing migration loader's "just execute the .sql file" contract (`store/duck.py:28-39`).
- **Try/catch wrapping in SQL**: DuckDB does not support `BEGIN ... EXCEPTION` blocks at the SQL level. Would require splitting the migration into per-column statements with Python-side error handling.

**Risk**: If the `duckdb` pin ever loosens beyond `<2` and the syntax changes in a future major, migration 002's leading comment documents the version requirement so the regression is visible.

---

## 2. Hatchling package-data inclusion

**Decision**: No `pyproject.toml` changes needed. The existing `[tool.hatch.build.targets.wheel]` block with `packages = ["src/premura"]` automatically includes all non-`.py` files (`.md`, `.yaml`, `.sql`, `.j2`) under that tree.

**Rationale**: Hatchling's wheel target follows the standard Python packaging conventions for the `src/`-layout. Files in `src/premura/` are bundled whether they're Python modules or data files. Verified empirically: the existing project already ships `dim_metric.yaml`, `store/migrations/001_init.sql`, and `ops/launchd.plist.j2` as package data without any explicit configuration. The new `skills/parser-generator/SKILL.md` and `store/migrations/002_dim_metric_ontology.sql` will be bundled the same way.

**Verification step in NFR-006**: build a wheel (`python -m build --wheel`) and confirm `unzip -l dist/*.whl | grep SKILL.md` shows the file.

**Alternatives considered**:
- **`[tool.hatch.build.targets.wheel.force-include]`**: Required only when files live outside the package tree. Not our case.
- **`MANIFEST.in`**: Setuptools-era convention; Hatchling does not use it.

---

## 3. Claude Code skill frontmatter convention

**Decision**: Use the schema observed in installed spec-kitty skills (`~/.claude/skills/spec-kitty-*/SKILL.md`):

```yaml
---
name: parser-generator
description: >-
  Scaffold a new vendor parser from an export dump. Reads the canonical
  metric ontology and the agent-agnostic contract in
  src/premura/parsers/CONTRACT.md, drafts a parser module against the
  PluginParser Protocol, and offers a PR back upstream.
  Triggers: "create a parser for", "scaffold parser", "new vendor parser",
  "generate parser from dump", "add ingestion for".
  Does NOT handle: signal engine functions (those live in src/premura/engine/),
  user-facing interview flow (Stage 4), or MCP server tooling (Stage 3).
---
```

**Rationale**: Verified by reading actual installed skill files:
- `~/.claude/skills/spec-kitty-glossary-context/SKILL.md`
- `~/.claude/skills/spec-kitty-git-workflow/SKILL.md`
- `~/.claude/skills/ad-hoc-profile-load/SKILL.md`

All three use `name:` + `description:` (with embedded trigger phrases and anti-trigger phrases in prose), no formal `triggers:` array. The `argument-hint:` key appears optionally on skills that take an argument.

The body convention is markdown with `# <skill-name>` as H1, `## Step N: <description>` for procedural steps, and a final `## References` or `## Quick Reference` section. Our parser-generator skill body is a stub that references `src/premura/parsers/CONTRACT.md` rather than embedding the decision tree, so its body is short (per FR-011).

**Alternatives considered**:
- **Formal `triggers:` array in frontmatter**: Not observed in any inspected skill; would diverge from convention.
- **Embedding the full contract inline in `SKILL.md`**: Rejected — would duplicate `CONTRACT.md` and create a fork-risk between the two documents.

---

## 4. Typer verb registration

**Decision**: Match the existing pattern in `src/premura/cli.py`:

```python
@app.command(name="install-skills")
def install_skills_cmd() -> None:
    """Install Claude Code skills shipped with this package into ./.claude/skills/."""
    written = skills.install_skills(Path.cwd())
    if not written:
        console.print("[dim]no changes[/dim]")
        return
    for path in written:
        console.print(f"wrote: {path}")
```

**Rationale**: Verified by reading existing simple verbs in `cli.py`:
- `doctor` (lines 340-381): `@app.command()` with a docstring as help text.
- `gc` (lines 389-406): `@app.command()` with `Annotated[int, typer.Option(...)]` for arguments.

Hyphenated CLI names are supported via the `name="install-skills"` argument to `@app.command`. The Python function name itself can use underscores (`install_skills_cmd` to disambiguate from the imported `skills.install_skills` helper).

**Alternatives considered**:
- **`@app.command()` with Python function name `install_skills`**: Typer would normalize to `install-skills` automatically, but the function name would collide with `skills.install_skills` after `from premura import skills`. The explicit `name="install-skills"` + suffix on the function avoids the collision.

---

## 5. `importlib.resources.files(...)` parity across install modes

**Decision**: Use `importlib.resources.files("premura").joinpath("skills/<name>/SKILL.md")` and trust it to work identically in editable (`pip install -e .`) and wheel installs.

**Rationale**: As of Python 3.9+, `importlib.resources.files(...)` returns a `Traversable` object backed by the actual filesystem in both modes:
- **Editable install**: `files(...)` resolves to `src/premura/...` in the source tree.
- **Wheel install**: `files(...)` resolves to `<site-packages>/premura/...`.

Both expose `.joinpath(...)`, `.read_text()`, `.is_file()`, and (via `as_file()`) a context manager for cases where a real filesystem path is needed.

The existing `store/duck.py` already uses this pattern for migrations (`resources.files(MIGRATIONS_PACKAGE).iterdir()` at line 36) and YAML (`resources.files("premura").joinpath(DIM_METRIC_YAML).read_text(...)` at line 45). The pattern is proven in this codebase.

**NFR-006 explicitly verifies** both modes:
- `pip install -e . && python -c "...files('premura').joinpath('skills/parser-generator/SKILL.md').is_file()"`
- `python -m build --wheel && unzip -l dist/*.whl | grep SKILL.md`

**Alternatives considered**:
- **`pkg_resources` (legacy setuptools API)**: Deprecated since `setuptools>=68`; modern projects should use `importlib.resources`.
- **`__file__`-based path construction**: Brittle across install modes; doesn't work in zipped wheels.

---

## Cross-cutting observations from the v1 codebase

These were discovered during exploration and inform the implementation plan but are not "unknowns" per se:

- **Migration loader idempotency**: `store/duck.py:28-39` does not track which migrations have been applied. Each migration's SQL must be self-idempotent (`CREATE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`). Our migration 002 honors this rule.

- **`seed_dim_metric` is the loader-update load-bearing change**: The current loader at `store/duck.py:42-67` only reads 5 fields. Adding columns via migration 002 is **insufficient** to surface the new data — the loader must also be extended. This was almost missed in the original spec; corrected in spec.md FR-016.

- **Existing 43 `dim_metric.yaml` rows are uniform 5-field**: Verified by reading the file. No schema variability today. Adding the `category` field to all existing rows (per FR-017) is a non-trivial sub-task — needs ~43 manual category assignments, but the categories are obvious (e.g., `heart_rate` → `cardiovascular`, `weight` → `body_composition`).

- **`conftest.py` provides `empty_warehouse`**: All migration/schema tests can use this fixture (lines 11-17 of `tests/conftest.py`). Skeleton test reuses it.

- **No CLI testing pattern in the existing tests**: Adding `install-skills` should test the underlying `install_skills()` function directly (with `tmp_path`), not via subprocess invocation of the CLI. Faster, more reliable, no `uv run` indirection.

---

## Closed unknowns

All five entry-state unknowns are resolved. No unresolved clarification markers remain in `spec.md` or `plan.md`. The Phase 1 design proceeds with full information.
