# Quickstart: v2 Architectural Skeleton

> Mission: `v2-architectural-skeleton-01KS4SHA`
> Phase 1 quickstart document
> Audience: contributor verifying the skeleton landed correctly, or starting a follow-up mission against it.

## Prerequisites

- macOS, Linux, or any platform with Python 3.11 and `uv`.
- The repo cloned at `~/repos/personal/health_export/` (or wherever you keep it — substitute paths accordingly).
- For full bootstrap: `brew install age uv rclone` (or your platform equivalent).

## Step 1 — Sync the codebase

```bash
cd ~/repos/personal/health_export
git checkout master
git pull
uv sync --extra dev
```

Should report: dependencies installed, no errors. If `uv` complains about Python version, ensure `.python-version` is honored (3.11).

## Step 2 — Run the existing test suite

```bash
uv run python -m pytest -q
```

**Expected**: ≥18 tests pass (17 pre-existing + ≥1 new from `tests/test_skeleton.py`). Zero failures. If any pre-existing test fails, the skeleton mission has broken v1 (NFR-001 violation).

## Step 3 — Verify the skeleton subpackages import cleanly

```bash
uv run python -c "
from premura import engine, mcp, ui
from premura.parsers import _lang, lookup
from premura.parsers.base import Parser, PluginParser, ParseResult, PluginParseResult
from premura.engine import signal, SignalSpec, REGISTRY
print('all imports OK')
print(f'REGISTRY empty: {REGISTRY == {}}')
"
```

**Expected**:
```
all imports OK
REGISTRY empty: True
```

If `REGISTRY` is not empty, some module is registering signals at import time — that violates the open-boundary principle of this mission.

## Step 4 — Verify the stubs raise `NotImplementedError`

```bash
uv run python -c "
from premura import engine, mcp, ui
from premura.parsers import _lang, lookup

stubs = [
    ('engine.compute', lambda: engine.compute('x', None)),
    ('engine.list_by_domain', lambda: engine.list_by_domain('liver')),
    ('engine.list_auto_safe', lambda: engine.list_auto_safe()),
    ('engine.check_inputs_available', lambda: engine.check_inputs_available([], None)),
    ('engine.list_unavailable', lambda: engine.list_unavailable('liver', None)),
    ('mcp.register_tools', lambda: mcp.register_tools(None, ['liver'])),
    ('ui.start_interview', lambda: ui.start_interview()),
    ('_lang.detect_language', lambda: _lang.detect_language('hello')),
    ('lookup.suggest_metric', lambda: lookup.suggest_metric('foo')),
]
for name, fn in stubs:
    try:
        fn()
    except NotImplementedError as e:
        print(f'  {name}: OK ({e})')
    else:
        print(f'  {name}: FAILED — did not raise NotImplementedError')
"
```

**Expected**: 9 lines each ending in `OK`. Any line ending in `FAILED` indicates a stub that has accidentally been implemented (or removed).

## Step 5 — Install the parser-generator skill

```bash
uv run hpipe install-skills
```

**Expected** (first run):
```
wrote: .claude/skills/parser-generator/SKILL.md
```

**Expected** (second run):
```
no changes
```

Verify the file:
```bash
test -f .claude/skills/parser-generator/SKILL.md && \
  head -10 .claude/skills/parser-generator/SKILL.md
```

You should see the YAML frontmatter:
```yaml
---
name: parser-generator
description: >-
  ...
---
```

## Step 6 — Verify the ontology schema and seed

```bash
# Wipe local DB to force a fresh migration + seed
rm -f data/duck/health.duckdb

# Initialize (this runs migrations 001 and 002, then seeds dim_metric)
uv run python -c "
from premura.store import duck
from pathlib import Path
conn = duck.initialize(Path('data/duck/health.duckdb'))
print('initialized')
n = duck.seed_dim_metric(conn)
print(f'seeded {n} dim_metric rows')
conn.close()
"
```

**Expected**: `seeded` count is `≥140` (per FR-017).

Verify the new columns are populated:
```bash
duckdb -readonly data/duck/health.duckdb \
  "SELECT category, COUNT(*) FROM hp.dim_metric WHERE category IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 10;"
```

**Expected**: a table with at least 5 distinct categories and counts.

Verify lab markers have LOINC codes:
```bash
duckdb -readonly data/duck/health.duckdb \
  "SELECT loinc, COUNT(*) FROM hp.dim_metric WHERE metric_id LIKE 'lab:%' AND loinc IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 10;"
```

**Expected**: most rows have a real LOINC code (`"718-7"`, `"2093-3"`, etc.). Some may show `"[unmapped]"` for markers where no LOINC exists.

## Step 7 — Verify the package data ships correctly

```bash
uv run python -c "
from importlib.resources import files
skill_path = files('premura').joinpath('skills/parser-generator/SKILL.md')
print(f'exists: {skill_path.is_file()}')
print(f'first 100 chars: {skill_path.read_text()[:100]!r}')
"
```

**Expected**: `exists: True`, first 100 chars include the YAML frontmatter.

## Step 8 — Verify the project-level docs exist

```bash
test -f AGENTS.md && echo "AGENTS.md OK"
test -f src/premura/parsers/CONTRACT.md && echo "CONTRACT.md OK"
test -f docs/UPDATE_STRATEGY.md && echo "UPDATE_STRATEGY.md OK"
test -f docs/V1_CLOSEOUT.md && echo "V1_CLOSEOUT.md OK"
```

**Expected**: four `OK` lines.

## Step 9 — Doctor stays green

```bash
uv run hpipe doctor
```

**Expected**: exit code 0, no new red rows compared to pre-mission state. (NFR-002)

## Step 10 — Lint and typecheck pass

```bash
uv run ruff check src/premura/{engine,mcp,ui,skills,parsers/_lang,parsers/lookup.py,parsers/base.py}
uv run mypy src/premura/{engine,mcp,ui,skills,parsers/_lang}
```

**Expected**: both exit 0. (NFR-003)

## If something failed

| Symptom | Likely cause |
|---|---|
| Tests fail with `ImportError: cannot import name 'signal'` | `src/premura/engine/_registry.py` missing or not re-exported in `__init__.py` |
| `REGISTRY` is not empty at import | Some module is decorating functions at import — should not happen in the skeleton |
| `install-skills` fails with `ModuleNotFoundError` | `src/premura/skills/__init__.py` missing or not importable |
| `install-skills` writes nothing on first run | `skills/parser-generator/SKILL.md` not shipped as package data — check `importlib.resources` lookup |
| `dim_metric` rows lack `category` column | Migration 002 not applied — check migration is in `src/premura/store/migrations/` and ends in `.sql` |
| Lab rows have `loinc` IS NULL | `seed_dim_metric` loader update missing — check `store/duck.py` reads `row.get("loinc")` |
| YAML parse error | A new row in `dim_metric.yaml` has invalid syntax — likely unquoted LOINC code starting with a digit |

## Next steps after the skeleton merges

Now that the contracts and file layout are in place, follow-up missions can proceed:

1. **Engine implementation mission** — replace 5 `NotImplementedError` stubs with real implementations; add 2-3 reference signal functions; wire `auto_safe` to `hpipe ingest`.
2. **MCP server mission** — implement `register_tools` against the `mcp` Python SDK; depends on at least one engine signal function existing.
3. **Lab PDF parser mission** (FEATURE_BLOOD.md) — implement `parsers/lab_pdf.py` against `PluginParser`; depends on `_lang` and `lookup` being implemented.
4. **Update strategy mission** — implement `hpipe revalidate` and `hpipe rebuild`; depends on signal functions being persisted with `signal_revision` in `raw_payload`.
5. **User-interface mission** — implement `start_interview` and the 6 health-direction tracks inside `ui/`; depends on MCP being operational.

The skeleton makes all five of these missions architecturally independent — they can run in any order, each in their own mission, each merging without coordinating with the others (file scopes disjoint by construction).
