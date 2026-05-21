# Implementation Plan: v2 Architectural Skeleton

**Branch**: `master` (target) | **Date**: 2026-05-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/v2-architectural-skeleton-01KS4SHA/spec.md`
**Mission ID**: `01KS4SHAJFA45WZYXS6XG8EFNE` (mid8: `01KS4SHA`)
**Mission type**: `software-dev`

## Summary

Land the v2 architectural skeleton: placeholder subpackages for the four data-flow stages (Ingest/parsers, Engine, MCP, User interface), the federated parser-generation contract (`PluginParser` Protocol + `PluginParseResult` dataclass + `parsers/CONTRACT.md` + `AGENTS.md` + shipped Claude skill), the engine signal-registry contract (`SignalSpec` + `@signal(...)` decorator + `REGISTRY` dict + 5 stub API functions including `check_inputs_available`/`list_unavailable` for the input-availability gate), the ontology schema extension (six new `dim_metric` columns + ~150 seeded rows with LOINC/IEEE-1752.1 cross-references + clinically standard multilingual aliases), and the `hpipe install-skills` CLI verb wired through `ops/bootstrap.sh`. Plus `docs/UPDATE_STRATEGY.md` documenting the six DB-update kinds with the gaps queued for follow-up missions.

**Skeleton-only**: every newly introduced stage function raises `NotImplementedError`. Existing v1 user-facing flows keep their current behavior; additive edits to existing files are allowed where needed for the skeleton. No new third-party dependencies. No new CLI verbs beyond `install-skills`. The deliverable is *contracts and file layout*, with `install-skills` as the one intentional behavioral addition.

**Canonical vocabulary policy (defined now, rewrite deferred)**: common reusable observations stay as bare English canonical `metric_id`s (for example `weight`, `heart_rate`, `steps`, `spo2`); clinical lab analytes use `lab:*`; engine outputs reserve `derived:*`; `vendor:*` is fallback-only for source-specific concepts. Aliases retain clinically standard names and abbreviations only. Renaming the legacy v1 metric IDs to the final canonical vocabulary is explicitly deferred to a later **full-rebuild-from-raw** mission rather than handled in this skeleton PR.

## Technical Context

**Language/Version**: Python 3.11 (pinned by `.python-version`; project requires `>=3.11`).
**Primary Dependencies**: No new dependencies. Already-installed: `duckdb>=1.1,<2`, `pydantic>=2.9,<3`, `typer>=0.12,<1`, `polars>=1.12,<2`, `pyyaml>=6.0,<7`, `structlog>=24.4,<25`. Plus dev: `pytest>=8.3`, `ruff>=0.7`, `mypy>=1.13`.
**Storage**: DuckDB single-file warehouse at `data/duck/health.duckdb`. Schema `hp.*`. Migration loader at `src/premura/store/duck.py:28-39` discovers `.sql` files in `premura.store.migrations` package via `importlib.resources`, sorts lexically, executes sequentially. Idempotency is each migration's responsibility (DuckDB ≥0.8 supports `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`).
**Testing**: pytest, 17 existing tests in `tests/` with `conftest.py` providing `empty_warehouse` fixture. Markers: `regression` for tests that need real on-disk exports.
**Target Platform**: macOS (development); the package is platform-portable but the launchd plist is macOS-only (out of scope here).
**Project Type**: Single Python project, `src/`-layout (`src/premura/` is the package root).
**Performance Goals**: Skeleton additions must add < 100ms to `hpipe doctor` wall-clock time (NFR-005). No other performance targets — no behavior ships.
**Constraints**: No new third-party deps (C-003). No CLI verbs beyond `install-skills` (C-004). Existing v1 flows keep current behavior (C-002). `derived:*` `metric_id` namespace reserved for engine layer (C-011). MCP and UI layers must not access DuckDB directly (C-012). Repo directory rename deferred to user (C-009).
**Scale/Scope**: ~12 new files, ~3 modified files (cli.py, store/duck.py, dim_metric.yaml). ~107 new ontology rows. 1 new test file (`tests/test_skeleton.py`).

No `[NEEDS CLARIFICATION]` markers — all design decisions settled during `/spec-kitty.plan` discovery.

## Charter Check

**SKIPPED** — no charter present (`.kittify/charter/charter.md` absent per `spec-kitty charter context --action plan --json` output). When a charter is added in the future, the engine's open-boundary framing (registry contract is open; signal function bodies may be proprietary) and the parser-federation contract (community PRs governed by `CONTRACT.md`) are the two architecturally-load-bearing commitments that any future governance doc should ratify.

## Project Structure

### Documentation (this feature)

```
kitty-specs/v2-architectural-skeleton-01KS4SHA/
├── plan.md                         # This file
├── spec.md                         # Authoritative spec (19 FR / 8 NFR / 12 C)
├── meta.json                       # Mission identity record
├── research.md                     # Phase 0 — technical-unknowns resolution
├── data-model.md                   # Phase 1 — extended schemas + new dataclasses
├── contracts/
│   ├── plugin-parser.md            # PluginParser Protocol + PluginParseResult shape + decision tree
│   └── signal-registry.md          # engine.SignalSpec + @signal + REGISTRY + 5-function API
├── quickstart.md                   # Phase 1 — contributor verification recipe
├── checklists/
│   └── requirements.md             # Spec quality checklist (post-specify, 17/17 passing)
└── tasks/                          # (Empty here; /spec-kitty.tasks fills in next)
```

### Source Code (repository root)

```
src/premura/
├── __init__.py                       # (existing — unchanged)
├── cli.py                            # MODIFY: append @app.command(name="install-skills")
├── config.py                         # (existing — unchanged)
├── dedupe.py                         # (existing — unchanged)
├── dim_metric.yaml                   # MODIFY: 43 → ≥140 rows; existing 43 gain `category`; new ~107 rows with full new-column data
├── encrypt.py                        # (existing — unchanged)
├── loader.py                         # (existing — unchanged)
├── notify.py                         # (existing — unchanged)
├── upload.py                         # (existing — unchanged)
├── engine/                           # NEW (Stage 2)
│   ├── __init__.py                   # docstring + re-exports + 5 stub API functions
│   └── _registry.py                  # SignalSpec dataclass, @signal decorator, REGISTRY dict
├── mcp/                              # NEW (Stage 3)
│   └── __init__.py                   # docstring-only + 1 stub register_tools()
├── ui/                               # NEW (Stage 4)
│   └── __init__.py                   # docstring-only + 1 stub start_interview()
├── parsers/
│   ├── base.py                       # MODIFY (append-only): PluginParseResult + PluginParser
│   ├── lookup.py                     # NEW: suggest_metric() stub
│   ├── CONTRACT.md                   # NEW: agent-agnostic parser contract
│   ├── _lang/                        # NEW
│   │   └── __init__.py               # detect_language() stub, local-only docstring
│   ├── bmt.py                        # (existing — unchanged)
│   ├── garmin_gdpr.py                # (existing — unchanged)
│   ├── health_connect.py             # (existing — unchanged)
│   └── sleep_as_android.py           # (existing — unchanged)
├── skills/                           # NEW
│   ├── __init__.py                   # install_skills() function (real, not stub — small)
│   └── parser-generator/
│       └── SKILL.md                  # NEW: stub Claude Code skill manifest
└── store/
    ├── duck.py                       # MODIFY: extend seed_dim_metric() for 6 new columns
    └── migrations/
        ├── 001_init.sql              # (existing — unchanged)
        └── 002_dim_metric_ontology.sql  # NEW: 6 ADD COLUMN IF NOT EXISTS

ops/
└── bootstrap.sh                      # MODIFY: append skill-install step gated by HPIPE_SKIP_SKILLS + tty check

AGENTS.md                             # NEW at repo root (agents.md convention)

docs/
└── UPDATE_STRATEGY.md                # NEW

tests/
└── test_skeleton.py                  # NEW
```

**Structure Decision**: Subpackages live as siblings under `src/premura/` (status quo layout, confirmed during discovery). The `engine/` subpackage uses a private `_registry.py` for the dataclass/decorator/dict; `__init__.py` re-exports the public symbols (`signal`, `SignalSpec`, `REGISTRY`) and adds the 5 stub API functions. All other new subpackages (`mcp/`, `ui/`, `parsers/_lang/`, `skills/`) are flat — `__init__.py` only. No multi-method classes, no Protocol ABC trees beyond `PluginParser` itself.

## Build order

Three independent tracks; can be implemented in any order within a single PR. Smoke test ties them together at the end.

### Track A — Ontology + schema (must land atomically as one commit)

1. `src/premura/store/migrations/002_dim_metric_ontology.sql` — six `ALTER TABLE … ADD COLUMN IF NOT EXISTS` statements.
2. `src/premura/store/duck.py:seed_dim_metric` — extend to read + INSERT the six new fields via `row.get(...)`.
3. `src/premura/dim_metric.yaml` — add `category` to all 43 existing rows; append ~107 new rows with full new-column data.

Atomic because: applying (1) without (2) leaves the new columns NULL on every seed; (2) without (1) errors at INSERT. (3) without (1)+(2) is silently dropped (loader ignores unknown YAML keys).

### Track B — Engine layer (registry contract)

4. `src/premura/engine/_registry.py` — `SignalSpec` dataclass, `signal` decorator, `REGISTRY` dict. ~25 lines.
5. `src/premura/engine/__init__.py` — docstring (stage name, on-demand vs auto-run, open boundary note) + re-exports + 5 stub functions raising `NotImplementedError`.

### Track C — Parser-federation contract + plumbing

6. `src/premura/parsers/base.py` — append `PluginParseResult` dataclass + `PluginParser` Protocol. **Append only**, do not touch existing symbols.
7. `src/premura/parsers/lookup.py` — `suggest_metric()` stub.
8. `src/premura/parsers/_lang/__init__.py` — `detect_language()` stub, "local-only" docstring.
9. `src/premura/parsers/CONTRACT.md` — write the agent-agnostic contract document.
10. `src/premura/mcp/__init__.py` — docstring-only stub.
11. `src/premura/ui/__init__.py` — docstring-only stub.
12. `src/premura/skills/parser-generator/SKILL.md` — stub skill manifest with frontmatter + reference to CONTRACT.md.
13. `src/premura/skills/__init__.py` — `install_skills(target_root)` real function (small, ~30 lines: walk `importlib.resources.files("premura.skills")` for SKILL.md files; sha256-compare; copy if different; return written list).
14. `src/premura/cli.py` — append `@app.command(name="install-skills")` verb that calls `skills.install_skills(Path.cwd())`.
15. `ops/bootstrap.sh` — append skill-install step gated by `HPIPE_SKIP_SKILLS=1` + `[[ -t 0 ]]`.

### Track D — Cross-cutting docs

16. `AGENTS.md` (repo root) — standards-first rule, pointers to skill + CONTRACT.md.
17. `docs/UPDATE_STRATEGY.md` — six update kinds, status of each.

### Final — Test

18. `tests/test_skeleton.py` — verify FR-001 through FR-017.

### After implementation

19. Update `kitty-specs/v2-architectural-skeleton-01KS4SHA/checklists/requirements.md` post-implementation — flip remaining status items to ✓ as appropriate.

## Complexity Tracking

No charter exists, so no charter-check violations to justify. Skeleton is intentionally minimal:

| Concern | Why this minimal shape | Simpler alternative considered |
|---|---|---|
| `engine/_registry.py` (separate file) | Keeps the contract isolated from the stub API; future implementer adds signal modules without touching the registry definition. | Inline in `__init__.py`. Rejected: muddies the open-boundary boundary. |
| `parsers/CONTRACT.md` + `AGENTS.md` (two docs) | CONTRACT.md is the deep, code-coupled contract; AGENTS.md is a 1-page top-level pointer following an emerging cross-tool convention. Serves different reader audiences. | Single `AGENTS.md` with all content. Rejected: forces non-Claude agents to scroll past parser-specific detail to find project-level rules. |
| `parsers/lookup.py` (separate file) | The lookup function is *not* a language concern; it's an ontology concern. Putting it in `_lang/` would mix unrelated responsibilities. | Stash in `_lang/lookup.py`. Rejected: misleading namespace. |
| `PluginParseResult` (new dataclass vs. reuse `ParseResult`) | The user chose option B during discovery — three new structured fields (`language_detected`, `unmapped_metrics`, `confidence`) better than overloading `notes`. | Reuse `ParseResult` and stuff metadata into `notes`/`raw_payload`. Rejected by user. |
| `revision` field on `SignalSpec` | Reserved metadata for future `hpipe revalidate` command (see `docs/UPDATE_STRATEGY.md`). Cheap now; expensive to retrofit later. | Omit and add later. Rejected: forces a SignalSpec schema migration when revalidation ships. |

No real complexity violations — every choice is defensibly the simplest path that honors the constraints.

## Phase 0 outputs

See [research.md](research.md). Resolved unknowns:

- DuckDB `ADD COLUMN IF NOT EXISTS` supported since v0.8 (project pinned at ≥1.1 → safe).
- Hatchling default-includes non-`.py` files under `packages = ["src/premura"]` → no `pyproject.toml` config change needed for skill `.md` files or `dim_metric.yaml`.
- Claude Code skill frontmatter convention: `name:` + `description:` (with embedded trigger phrases), no formal `triggers:` array.
- Typer `@app.command(name="install-skills")` is the correct verb registration; help-text is the docstring first line.
- `importlib.resources.files(...)` works identically in editable (`pip install -e .`) and wheel installs because both honor the same package-data layout.

## Phase 1 outputs

- [data-model.md](data-model.md) — concrete schemas: extended `hp.dim_metric` columns, `dim_metric.yaml` row shape, `SignalSpec` dataclass, `PluginParseResult` dataclass.
- [contracts/plugin-parser.md](contracts/plugin-parser.md) — full PluginParser Protocol surface + decision tree + alias-PR loop.
- [contracts/signal-registry.md](contracts/signal-registry.md) — `@signal(...)` decorator surface, `REGISTRY` contract, 5-function engine API, auto_safe / priority / revision semantics.
- [quickstart.md](quickstart.md) — contributor verification recipe (clone → bootstrap → install-skills → smoke test → query).

## Branch contract (final reaffirmation before `/spec-kitty.tasks`)

- Current branch: `master`
- Planning/base branch: `master`
- Final merge target: `master`
- `branch_matches_target`: `true`
- Single PR per [C-010](spec.md); no force-push, no history rewrite.

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| Parallel v1-closeout PR conflicts in `cli.py` (both append `@app.command` blocks at EOF) | Resolve by ordering: whichever lands first wins; second rebases. Conflict surface is < 10 lines and trivial. Coordinated via `STATUS.md` row updates only (file-scope-disjoint by C-002). |
| DuckDB ADD COLUMN IF NOT EXISTS breaks on future minor version | Project pins `duckdb<2`. Migration's leading comment documents the version requirement. If pin loosens, fall back to Python-side `PRAGMA table_info` check. |
| `seed_dim_metric` loader update silently drops new columns on rows without the new keys | By design — backward-compat via `row.get(None)` returns NULL, which the migration's nullable columns accept. Tested in FR-016 / NFR-007. |
| Skill manifest frontmatter syntax breaks Claude Code skill loader | Mirror the exact frontmatter shape of `~/.claude/skills/spec-kitty-*/SKILL.md` (verified during planning research). Test asserts presence of `name:` and `description:`. Manual smoke confirms Claude Code lists the skill after install. |
| `importlib.resources` lookup of shipped skill fails in editable install | NFR-006 explicitly tests both wheel and editable modes. If editable fails, add `[tool.hatch.build.targets.wheel.force-include]` to pyproject. |
| YAML row count drifts below 140 in implementation | Hard floor 140 in FR-017. If sourcing yields fewer, implementer relaxes the test threshold and documents the gap in STATUS.md (user-confirmed strategy: "Lower threshold + STATUS note"). |
| Community parser accidentally emits `derived:*` metric_id | Caught at code review per C-011 + `parsers/CONTRACT.md`. Future possible CI grep enforcement; not in skeleton scope. |

## Verification recipe (matches SC-001 through SC-008)

```bash
# SC-002, SC-001 (existing tests + skeleton tests pass)
uv run python -m pytest -q tests/ && echo "SC-002 GREEN"

# SC-003 (doctor green)
uv run hpipe doctor && echo "SC-003 GREEN"

# SC-004 (install-skills idempotent)
TMP=$(mktemp -d) && cd "$TMP" && \
  uv run --project /Users/nbrandizzi/repos/personal/health_export hpipe install-skills && \
  test -f .claude/skills/parser-generator/SKILL.md && \
  HASH1=$(shasum -a 256 .claude/skills/parser-generator/SKILL.md) && \
  uv run --project /Users/nbrandizzi/repos/personal/health_export hpipe install-skills | grep -q "no changes" && \
  HASH2=$(shasum -a 256 .claude/skills/parser-generator/SKILL.md) && \
  [ "$HASH1" = "$HASH2" ] && echo "SC-004 GREEN"

# SC-005 (single mission commit on engine/__init__.py)
cd /Users/nbrandizzi/repos/personal/health_export && \
  [ "$(git log --oneline -- src/premura/engine/__init__.py | wc -l)" = "1" ] && echo "SC-005 GREEN"

# SC-006 (package data ships, editable install)
uv run python -c "from importlib.resources import files; assert files('premura').joinpath('skills/parser-generator/SKILL.md').is_file()" && echo "SC-006 GREEN"

# SC-007 (categories populated after fresh ingest)
rm -f data/duck/health.duckdb && uv run hpipe ingest && \
  uv run python -c "
import duckdb; c=duckdb.connect('data/duck/health.duckdb', read_only=True)
rows = c.execute('SELECT category, COUNT(*) FROM hp.dim_metric WHERE category IS NOT NULL GROUP BY 1').fetchall()
assert len(rows) >= 5, rows; print(rows)" && echo "SC-007 GREEN"

# SC-008 (open registry boundary)
uv run python -c "from premura.engine import signal, SignalSpec, REGISTRY; assert REGISTRY == {}; print('open boundary OK')" && echo "SC-008 GREEN"
```

## Next phase

`/spec-kitty.tasks` will decompose this plan into work packages. Suggested decomposition (informational; the tasks command makes the final call):

- **WP01** — Track A: ontology schema + loader + YAML seed (the atomic schema-data triple).
- **WP02** — Track B: engine registry contract.
- **WP03** — Track C: parser federation contract (base.py extension, lookup.py, _lang stub, CONTRACT.md, mcp + ui docstring stubs).
- **WP04** — Track C: skill plumbing (parser-generator skill, install_skills function, install-skills CLI verb, bootstrap.sh hook).
- **WP05** — Track D: cross-cutting docs (AGENTS.md, UPDATE_STRATEGY.md).
- **WP06** — Smoke test (`tests/test_skeleton.py`) wrapping FR-001 through FR-017.

WP06 depends on all others. WP01 / WP02 / WP03 / WP05 are independent. WP04 depends on WP03 (parser-generator skill references CONTRACT.md, which is created in WP03).
