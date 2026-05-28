# v2 Architectural Skeleton — Specification

> **Mission**: `v2-architectural-skeleton-01KS4SHA`
> **Mission type**: `software-dev`
> **Target branch**: `master`
> **Created**: 2026-05-21
> **Last refined**: 2026-05-21 (post `/spec-kitty.plan` discovery)
> **Status**: Refined Draft
>
> Companion to the project-wide docs: [VISION.md](../../docs/history/product/VISION.md), [STAGES.md](../../docs/architecture/STAGES.md), [SPEC.md](../../docs/product/SPEC.md), [STATUS.md](../../docs/operations/STATUS.md), [ROADMAP.md](../../docs/product/ROADMAP.md), [RISK_OPPORTUNITY.md](../../docs/history/product/RISK_OPPORTUNITY.md).
> Sibling handoff to a parallel agent: [V1_CLOSEOUT.md](../../docs/V1_CLOSEOUT.md).

## 1. Purpose

Land the architectural skeleton for the v2 vision in [VISION.md](../../docs/history/product/VISION.md) and the four-stage data flow in [STAGES.md](../../docs/architecture/STAGES.md). After this mission merges, every future v2 work item has a *named, importable place to live*, and the contracts between stages exist as Python Protocols, dataclasses, migrations, registry shape, and skill manifests — but no behavior is added.

The mission commits two **load-bearing federated contracts**:

1. **The plugin contract** — agents (Claude or otherwise) generate a Python parser module from a vendor dump, mapping vendor fields → canonical `metric_id`s via a strict standards-first decision tree, and offer the result as a PR. Aliases grow alongside parsers, so the system needs less translation over time. The contract is documented in `src/premura/parsers/CONTRACT.md` (agent-agnostic) and surfaced to agents via `AGENTS.md` (root) and `src/premura/skills/parser-generator/SKILL.md` (Claude Code skill).

2. **The signal-engine registry contract** — Stage 2 signal functions register into a typed `REGISTRY` dict via a `@signal(...)` decorator. Each `SignalSpec` declares which domains the function serves, which canonical metric_ids it needs, which (if any) it produces, its priority, its revision, and whether it's safe to auto-precompute at ingest. MCP's tool exposure (Stage 3) and the UI layer's interview routing (Stage 4) both depend on this contract. The registry is the **open boundary** of the engine — the signal function bodies themselves may, in the long term, become proprietary.

The skeleton is **placeholder-only**: no implementations of the new v2 layers ship. Existing v1 user-facing flows keep their current behavior; additive edits to existing files are allowed where needed for the skeleton. `install-skills` is the one intentional new behavior in this mission. v1 close-out is delegated to a separate agent per [V1_CLOSEOUT.md](../../docs/V1_CLOSEOUT.md).

## 2. Scope

### In scope

- New subpackages under `src/premura/`:
  - **`engine/`** (Stage 2) — `__init__.py` documenting the layer + `_registry.py` defining `SignalSpec`, `signal` decorator, `REGISTRY` dict. Five stub API functions: `compute`, `list_by_domain`, `list_auto_safe`, `check_inputs_available`, `list_unavailable`. All raise `NotImplementedError`.
  - **`mcp/`** (Stage 3) — `__init__.py` docstring-only stub with `register_tools(server, domains)` raising `NotImplementedError`. Docstring documents: queries `engine.list_by_domain`, exposes available signals as MCP tools, returns missing-inputs report for high-priority gaps. Layering rule: never reads `hp.fact_measurement` directly.
  - **`ui/`** (Stage 4) — `__init__.py` docstring-only stub with `start_interview()` raising `NotImplementedError`. Docstring documents: drives the 6-direction interview (Pillar 4), hands domains to `mcp.register_tools`. Layering rule: never reads `hp.fact_measurement` or calls `engine` directly.
- New `parsers/_lang/` stub: language detection + local-only translation contract as TODO. One `__init__.py` with `detect_language(text)` stub raising `NotImplementedError`. Docstring contains the literal string `"local-only"`.
- New `parsers/lookup.py`: `suggest_metric(field_name: str) -> str | None` stub. When implemented, will build a flat reverse-index over all canonical `metric_id`s + all language-bucket aliases for case-insensitive exact match.
- New `src/premura/parsers/CONTRACT.md` — agent-agnostic parser contract. Documents (a) the `PluginParser` Protocol, (b) the standards-first decision tree (existing alias → LOINC for labs → IEEE 1752.1 for wearables → bare English canonical name for a reusable cross-source concept → vendor-namespaced fallback), (c) the `dim_metric.yaml` row shape, (d) the `unmapped_metrics` and alias-PR-with-parser feedback loops, (e) the **reserved `derived:*` namespace** rule (community parsers must not emit `derived:*` — only the engine layer does).
- New `AGENTS.md` at repo root following the [agents.md](https://agents.md) convention. Short pointer doc: standards-first ordering as a project-level rule, link to the parser-generator skill (Claude path) and `src/premura/parsers/CONTRACT.md` (universal path).
- Additive extension of `src/premura/parsers/base.py`:
  - `PluginParseResult(ParseResult)` dataclass adding three fields: `language_detected: str | None`, `unmapped_metrics: list[str]`, `confidence: float`.
  - `PluginParser(Parser, Protocol)` Protocol adding `language_hint: str | None`, `def declares_metrics(self) -> list[str]: ...`, and `def parse(self, path: Path) -> PluginParseResult: ...` (overriding the return type via Protocol covariance).
  - Existing `Parser` Protocol, `Measurement`, `Interval`, `ParseResult` untouched.
- New `src/premura/skills/parser-generator/SKILL.md` shipped *inside the package* as package data. Stub frontmatter (`name:`, `description:` with embedded triggers) and stub body that points the agent at `src/premura/parsers/CONTRACT.md` rather than embedding the contract inline.
- New `src/premura/skills/__init__.py` exposing `install_skills(target_root: Path) -> list[Path]` that copies shipped skills into `target_root/.claude/skills/<name>/`, idempotent via sha256-comparison. Returns the list of files actually written (empty list = no-op).
- New `hpipe install-skills` CLI verb wired in `src/premura/cli.py` that calls `skills.install_skills(Path.cwd())`.
- `ops/bootstrap.sh` step appended after `uv sync`, gated by `HPIPE_SKIP_SKILLS=1` env var AND `[[ -t 0 ]]` tty check (auto-skip in CI / non-interactive).
- New DuckDB migration `src/premura/store/migrations/002_dim_metric_ontology.sql` adding six columns to `hp.dim_metric`: `category VARCHAR`, `validity_window VARCHAR`, `missing_data_policy VARCHAR`, `aliases JSON`, `loinc VARCHAR`, `ieee1752 VARCHAR`. Each via `ALTER TABLE … ADD COLUMN IF NOT EXISTS`.
- Updated `src/premura/store/duck.py` — `seed_dim_metric()` extended to read the new six fields from each YAML row via `row.get(...)` and INSERT them with the existing fields. ON CONFLICT clause updated to refresh all six.
- Extended `src/premura/dim_metric.yaml` to ~150 rows total (target 150 ±10, minimum hard floor 140). Existing 43 rows gain a `category` field and remain under their current legacy `metric_id`s in this mission. New ~107 rows cover: wearable expansion (~40), CBC + chemistry + lipids + liver/kidney + electrolytes + thyroid + iron + vitamins + inflammation + endocrine (~80), urine starter (~15), stool starter (~15). English canonical `metric_id`s; LOINC + IEEE-1752.1 cross-references where available; aliases in flat per-language buckets (`en`, `it`, `de`, …) containing clinically standard names and abbreviations only.
- New `docs/UPDATE_STRATEGY.md` documenting the six kinds of DB update (new ingest, schema migrations, ontology seed refresh, derived signal invalidation, full rebuild from raw, parser updates). Marks which are handled today and queues the remaining work as a follow-up mission.
- One smoke test `tests/test_skeleton.py` covering imports, registry contract, migration idempotency, YAML schema + count, and `install-skills` idempotency.

### Out of scope

- **v1 close-out** — delegated per [V1_CLOSEOUT.md](../../docs/V1_CLOSEOUT.md). This mission does **not** touch `encrypt.py`, `notify.py`, `upload.py`, `dedupe.py`, `loader.py`, `config.py`, existing CLI verbs, existing v1 parsers, existing tests, `ops/launchd.plist.j2`.
- Any implementation of Stage 2/3/4 logic — no real signal functions, no MCP server running, no interview routing, no input-availability checks against real data.
- Any implementation inside `parsers/_lang/` — only the directory + TODO contract.
- Real parser generation by Claude — the skill is a stub manifest; live generation is a future mission.
- Bulk LOINC import (~800 additional rows). This mission seeds the high-value ~150.
- Lab PDF parser ([FEATURE_BLOOD.md](../../docs/FEATURE_BLOOD.md)) — its own future mission.
- Repo directory rename (`health_export/` → `premura/`) — user handles separately.
- Public-release / OSS publishing prep.
- New CLI verbs beyond `install-skills`. The future `hpipe revalidate` / `hpipe rebuild` verbs implementing the update strategy belong to a follow-up mission.
- Any new third-party dependency in `pyproject.toml`.
- Renaming existing legacy v1 `metric_id`s to the final canonical vocabulary. That rewrite is deferred to a follow-up mission that performs a **full rebuild from raw inputs** rather than an in-place compatibility migration.

## 3. Functional requirements

| ID | Requirement | Verification | Status |
|---|---|---|---|
| FR-001 | The system SHALL contain `src/premura/engine/` (renamed from `signals/`) with `__init__.py` whose docstring names "Stage 2 — Signal engine" per [STAGES.md](../../docs/STAGES.md), explicitly documents the on-demand + opt-in-auto-run execution modes, and notes that the layer may host proprietary derivations behind the open registry boundary. | `python -c "from premura import engine; print(engine.__doc__[:80])"` prints the stage name. | Draft |
| FR-002 | The system SHALL contain `src/premura/engine/_registry.py` defining: `SignalSpec` frozen dataclass with fields `name: str`, `domain: list[str]`, `inputs: list[str]`, `output: str \| None`, `priority: str = "normal"`, `auto_safe: bool = False`, `revision: str = "1"`, `fn: Callable = None`; the module-level dict `REGISTRY: dict[str, SignalSpec] = {}`; and a decorator `signal(*, name, domain, inputs, output=None, priority="normal", auto_safe=False, revision="1")` that registers the decorated function. | A test imports `signal`, `SignalSpec`, `REGISTRY`; decorates a no-op function; asserts `REGISTRY[name]` is populated with the right fields. | Draft |
| FR-003 | The `engine` module SHALL expose five stub API functions, each raising `NotImplementedError` with a message referencing `STAGES.md`: `compute(spec_name, conn)`, `list_by_domain(domain)`, `list_auto_safe()`, `check_inputs_available(inputs, conn, within=None)`, `list_unavailable(domain, conn)`. | Each function callable from `from premura.engine import …`; each call raises `NotImplementedError`. | Draft |
| FR-004 | The system SHALL contain `src/premura/mcp/__init__.py` whose docstring names "Stage 3 — MCP" and documents: queries `engine.list_by_domain` per user-picked domain, exposes available signals as tools, returns missing-inputs report for high-priority gaps. Single stub `register_tools(server, domains: list[str] \| None = None)` raises `NotImplementedError`. The docstring includes the literal string `"never reads hp.fact_measurement directly"`. | Import + call raises `NotImplementedError`; docstring substring assertion passes. | Draft |
| FR-005 | The system SHALL contain `src/premura/ui/__init__.py` whose docstring names "Stage 4 — User interface", documents the 6 health directions per VISION Pillar 4, and explains the call pattern through MCP. Single stub `start_interview()` raises `NotImplementedError`. Docstring includes the literal string `"never reads hp.fact_measurement or calls engine directly"`. | Import + call raises `NotImplementedError`; docstring substring assertion passes. | Draft |
| FR-006 | The system SHALL contain `src/premura/parsers/_lang/__init__.py` documenting the language-detection + local-only-translation contract as a TODO, with a stub `detect_language(text: str) -> str` raising `NotImplementedError`. The docstring contains the literal string `"local-only"`. | Import + call raises `NotImplementedError`; docstring substring assertion passes. | Draft |
| FR-007 | The system SHALL contain `src/premura/parsers/lookup.py` with a stub `suggest_metric(field_name: str) -> str \| None` raising `NotImplementedError`. The module's docstring documents the planned reverse-index behavior over canonical `metric_id`s and all-language aliases (case-insensitive exact match). | Import + call raises `NotImplementedError`. | Draft |
| FR-008 | The system SHALL extend `src/premura/parsers/base.py` (append-only) with: `PluginParseResult(ParseResult)` dataclass with fields `language_detected: str \| None = None`, `unmapped_metrics: list[str] = field(default_factory=list)`, `confidence: float = 1.0`; and `PluginParser(Parser, Protocol)` Protocol with `language_hint: str \| None`, `def declares_metrics(self) -> list[str]: ...`, `def parse(self, path: Path) -> PluginParseResult: ...`. Existing `Parser`, `Measurement`, `Interval`, `ParseResult` SHALL remain unchanged. | Both new symbols importable; existing v1 parser tests still pass; a typing-only test confirms `PluginParser` is a structural subtype of `Parser`. | Draft |
| FR-009 | The system SHALL contain `src/premura/parsers/CONTRACT.md` — agent-agnostic — covering the `PluginParser` Protocol, the standards-first decision tree (existing alias → LOINC for labs → IEEE 1752.1 for wearables → bare English canonical name for a reusable cross-source concept → `vendor:<source>:<field>` fallback), the `dim_metric.yaml` row shape including aliases, the alias-PR feedback loop, and the **reserved `derived:*` namespace** rule. | The file exists; a test asserts the strings `"LOINC"`, `"IEEE 1752.1"`, and `"derived:"` all appear in its content. | Draft |
| FR-010 | The system SHALL contain `AGENTS.md` at repo root referencing both the parser-generator skill at `src/premura/skills/parser-generator/SKILL.md` and the agent-agnostic contract at `src/premura/parsers/CONTRACT.md`, and stating the standards-first ordering as a project-level rule. | A test asserts both relative paths appear as substrings in `AGENTS.md`. | Draft |
| FR-011 | The system SHALL contain `src/premura/skills/parser-generator/SKILL.md` shipped as package data with frontmatter conforming to Claude Code skill conventions (at minimum `name:` and `description:` with embedded trigger phrases). The body MUST reference `src/premura/parsers/CONTRACT.md` as the authoritative contract rather than embedding the decision tree. | Load via `importlib.resources.files("premura").joinpath("skills/parser-generator/SKILL.md")`; assert frontmatter keys present; assert reference to `CONTRACT.md` substring. | Draft |
| FR-012 | The system SHALL contain `src/premura/skills/__init__.py` exposing `install_skills(target_root: Path) -> list[Path]` that copies every shipped skill under `premura.skills.*` into `target_root/.claude/skills/<name>/`, idempotent by sha256-comparison, returning files actually written. | Test: call with `tmp_path`; assert file at `tmp_path/.claude/skills/parser-generator/SKILL.md` exists; capture sha256; call again; assert return value is `[]` (empty) and sha256 unchanged. | Draft |
| FR-013 | The system SHALL add an `install-skills` CLI verb (`@app.command(name="install-skills")`) to `src/premura/cli.py` that calls `skills.install_skills(Path.cwd())` and prints the list of files written (or "no changes" if empty). | `uv run hpipe install-skills` from a clean temp dir produces `.claude/skills/parser-generator/SKILL.md` and exits 0; second invocation prints "no changes" and exits 0. | Draft |
| FR-014 | `ops/bootstrap.sh` SHALL invoke `uv run hpipe install-skills` after `uv sync --extra dev`, gated by `HPIPE_SKIP_SKILLS=1` env var AND `[[ -t 0 ]]` tty check (auto-skip in non-interactive contexts). | Static grep: `bootstrap.sh` contains `HPIPE_SKIP_SKILLS`, `install-skills`, and `[[ -t 0 ]]`. Manual smoke: running with `HPIPE_SKIP_SKILLS=1` does not create `.claude/skills/`. | Draft |
| FR-015 | The system SHALL add migration `src/premura/store/migrations/002_dim_metric_ontology.sql` containing six `ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS …` statements for `category VARCHAR`, `validity_window VARCHAR`, `missing_data_policy VARCHAR`, `aliases JSON`, `loinc VARCHAR`, `ieee1752 VARCHAR`. | After `store.duck.run_migrations(conn)` on a fresh DB, `PRAGMA table_info('hp.dim_metric')` lists all six new columns; running again is idempotent. | Draft |
| FR-016 | `src/premura/store/duck.py:seed_dim_metric` SHALL be extended to read the six new keys from each YAML row via `row.get(...)` and include them in the INSERT...ON CONFLICT UPDATE statement, while remaining backward-compatible with rows that lack the new keys (those rows INSERT NULLs into the new columns). | Existing v1 ingest tests pass. New test: a row without the new keys inserts; a row with all keys inserts with non-null values. | Draft |
| FR-017 | `src/premura/dim_metric.yaml` SHALL grow from 43 to ≥140 rows. Every row (existing + new) MUST have a non-empty `category` field. New rows additionally MUST have `display_name`, `canonical_unit`, `value_kind`. Lab rows (`metric_id` starts with `lab:`) MUST carry a `loinc` value (or the literal placeholder `"[unmapped]"` where no LOINC code exists). Wearable rows MUST carry an `ieee1752` value or null. | A test loads YAML; asserts `len(rows) >= 140`; asserts every row has non-empty `category`; asserts every `lab:*` row has `loinc` set. | Draft |
| FR-018 | The system SHALL contain `docs/UPDATE_STRATEGY.md` documenting six update kinds (new ingest, schema migration, ontology seed refresh, derived-signal invalidation, full rebuild from raw, parser updates). Marks (a)/(b)/(c) as handled and queues (d)/(e)/(f) as future-mission work. | The file exists; a test asserts the strings `"new ingest"`, `"schema migration"`, `"derived"`, `"rebuild"` all appear. | Draft |
| FR-019 | The system SHALL contain `tests/test_skeleton.py` covering FR-001 through FR-017 (excluding cross-repo doc grep checks already covered above). | `uv run python -m pytest tests/test_skeleton.py -q` passes. | Draft |

## 4. Non-functional requirements

| ID | Requirement | Threshold / Verification | Status |
|---|---|---|---|
| NFR-001 | The 17 existing pytest tests SHALL remain passing after this mission's changes. | `uv run python -m pytest -q` reports `≥17 passed` and no regressions in pre-existing tests. | Draft |
| NFR-002 | `hpipe doctor` SHALL exit 0 (green) after this mission's changes on the user's Mac. | `uv run hpipe doctor` exits 0. | Draft |
| NFR-003 | New Python code SHALL pass `ruff check` and `mypy` under the existing project config. | `uv run ruff check src/premura/{engine,mcp,ui,skills,parsers}` and `uv run mypy src/premura/{engine,mcp,ui,skills,parsers}` exit 0. | Draft |
| NFR-004 | The DuckDB migration SHALL be idempotent. Running it twice on the same DB MUST not error and MUST not duplicate columns. | Apply migration twice in a test; assert no error and `PRAGMA table_info` shows each new column exactly once. | Draft |
| NFR-005 | Skeleton additions SHALL add no measurable runtime overhead to existing CLI verbs. | Wall-clock difference of `hpipe doctor` before/after this mission, on the user's Mac, < 100 ms. | Draft |
| NFR-006 | The Python package wheel SHALL include the shipped skill files as package data, accessible via `importlib.resources` in both wheel-installed and editable-installed modes. | `pip install -e .` then `python -c "from importlib.resources import files; assert files('premura').joinpath('skills/parser-generator/SKILL.md').is_file()"` returns true. Build wheel; `unzip -l dist/*.whl | grep SKILL.md` shows the file. | Draft |
| NFR-007 | The migration's added columns SHALL be nullable so historical rows remain queryable without backfill. | After applying the migration to a populated DB, pre-existing rows return NULL on the new columns without errors. | Draft |
| NFR-008 | The `engine` registry contract SHALL be importable independently of any signal-function implementation (the open boundary). | `python -c "from premura.engine import signal, SignalSpec, REGISTRY"` succeeds with REGISTRY as an empty dict. | Draft |

## 5. Constraints

| ID | Constraint | Rationale | Status |
|---|---|---|---|
| C-001 | The `_lang/` stub's documented contract MUST specify "local-only translation; no external API calls". | [VISION.md Pillar 6](../../docs/history/product/VISION.md) — no PHI leaves the machine. | Draft |
| C-002 | Existing v1 user-facing behavior for ingest/export/upload/doctor/run-monthly/gc/install-launchd and the four shipped v1 parsers MUST remain unchanged in this mission. Files under `src/premura/parsers/{health_connect,garmin_gdpr,sleep_as_android,bmt}.py`, `src/premura/{encrypt,notify,upload,dedupe,loader,config}.py`, and existing tests under `tests/test_parsers/` MAY NOT be behaviorally modified. Additive edits to `cli.py`, `store/duck.py`, `parsers/base.py`, and `dim_metric.yaml` are allowed as specified elsewhere in this spec. The existing `Parser` Protocol, `Measurement`, `Interval`, `ParseResult` symbols in `parsers/base.py` MUST remain unchanged. | v1 close-out is owned by the parallel agent ([V1_CLOSEOUT.md](../../docs/V1_CLOSEOUT.md)); scope discipline avoids regressions while allowing the skeleton's additive contracts. | Draft |
| C-003 | No new third-party dependency MAY be added to `pyproject.toml` in this mission. | Skeleton ships zero behavior; libs (scipy, statsmodels, ruptures, mcp SDK, docling) belong to the missions that actually use them. | Draft |
| C-004 | No CLI verbs MAY be added beyond `install-skills`. | Defers UI surface decisions to Stage 4 work. `hpipe revalidate` / `hpipe rebuild` belong to the update-strategy follow-up. | Draft |
| C-005 | No row MAY be removed from `dim_metric.yaml` in this mission. Rows MAY only be added or have new columns populated; legacy v1 `metric_id`s remain in place until the later full-rebuild canonical-vocabulary mission. | Existing facts in the warehouse reference these `metric_id`s today, and the project prefers fewer migrations by doing vocabulary rewrites via rebuild. | Draft |
| C-006 | The `PluginParser` Protocol MUST be additive — the existing `Parser` Protocol SHALL NOT have any method added, removed, or modified. | v1 parsers must remain valid against the old Protocol; no migration of existing parsers in this mission. | Draft |
| C-007 | No change to the existing DuckDB schema `hp.*` other than the column additions in migration `002_dim_metric_ontology.sql`. | Schema stability for v1 queries. | Draft |
| C-008 | The shipped skill at `src/premura/skills/parser-generator/SKILL.md` MUST be a stub. Live generation logic, Anthropic-API calls, or any executable Claude-side behaviour are NOT part of this mission. | Skeleton-only scope. | Draft |
| C-009 | The repo directory MUST stay at `~/repos/personal/health_export/` for the duration of this mission. The user will rename later. | User explicit instruction. | Draft |
| C-010 | The mission MUST land as a single PR on `master`. No force-push, no history rewrite. | Coordination with the parallel v1-closeout PR; clean review. | Draft |
| C-011 | The `derived:*` `metric_id` namespace is RESERVED for the engine layer. Community parsers MUST NOT emit `metric_id`s starting with `derived:`. `parsers/CONTRACT.md` MUST document this rule explicitly. | Separation of concerns: parsers report observations; the engine produces derivations. Persistence-vs-views is the engine's choice per signal function. | Draft |
| C-012 | The `mcp/` module SHALL NOT import from `premura.store` or call DuckDB directly. The `ui/` module SHALL NOT import from `premura.store`, `premura.engine`, or call DuckDB directly. These layering boundaries are documented in module docstrings; an optional future mission may add import-graph linting. | STAGES.md layering rule: each stage reads only through the layer below it. | Draft |

## 6. User scenarios & testing

### Scenario A — A future contributor opens the repo

After this mission merges and `bash ops/bootstrap.sh` runs:

1. The contributor opens the repo in Claude Code.
2. Claude Code lists `parser-generator` as an available project skill (because `install-skills` ran during bootstrap).
3. The contributor browses `src/premura/{engine,mcp,ui,parsers}` and reads docstrings explaining the architectural intent of each layer.
4. The contributor reads `AGENTS.md` and `src/premura/parsers/CONTRACT.md` to understand the parser-generation contract.
5. The contributor opens `src/premura/dim_metric.yaml` and sees 150 metrics with categories, LOINC codes for labs, IEEE-1752.1 codes for wearables, and IT/DE/EN aliases for lab markers.

### Scenario B — A future "implement signal processing" mission begins

1. The mission spec references `src/premura/engine/` as the home of the work.
2. The first signal function (e.g., `ast_alt_ratio`) is implemented:
   ```python
   from premura.engine import signal

   @signal(name="ast_alt_ratio", domain=["liver", "metabolic"],
           inputs=["lab:ast", "lab:alt"], output="derived:ast_alt_ratio",
           priority="high", auto_safe=True, revision="1")
   def compute_ast_alt_ratio(conn): ...
   ```
3. No file moves are needed. The migration `002_dim_metric_ontology.sql` is already applied; `validity_window` and `missing_data_policy` are readable from `hp.dim_metric`. The `derived:ast_alt_ratio` `metric_id` is in `dim_metric.yaml`.
4. The implementation also fills in the body of `engine.compute`, `engine.list_by_domain`, and the other stubs.

### Scenario C — A future user adds a parser for vendor X (federated work)

1. User clones the repo, drops `vendor_x_export.zip` in `data/inbox/`.
2. User invokes the `parser-generator` skill in Claude Code: *"create a parser for this dump."*
3. Claude reads `src/premura/parsers/CONTRACT.md` (which the skill points to). For each vendor field, Claude follows the standards-first decision tree:
   - Call `suggest_metric(field_name)` against the ontology + aliases.
   - If miss → look up LOINC (for labs) or IEEE-1752.1 (for wearables).
   - If still miss but the concept is reusable → propose a bare English canonical `metric_id`.
   - If still source-specific → propose `vendor:<source>:<field>`.
4. Claude writes `src/premura/parsers/vendor_x.py` against the `PluginParser` Protocol, returning `PluginParseResult` (with `unmapped_metrics` if any).
5. Claude proposes any new `dim_metric.yaml` rows + new aliases in the same commit.
6. User verifies locally; if happy, Claude offers `git add + commit + gh pr create`.

### Scenario D — An MCP request from a curious user

1. User opens an MCP-aware client and tells the UI layer: *"I'm worried about my liver."*
2. `ui.start_interview()` calls `mcp.register_tools(server, domains=["liver"])`.
3. MCP queries `engine.list_by_domain("liver")` → list of `SignalSpec`s.
4. For each spec, MCP calls `engine.check_inputs_available(spec.inputs, conn)`.
5. Available specs → exposed as MCP tools (`compute_ast_alt_ratio()`, etc.).
6. Unavailable + `priority="high"` specs → assembled into a `missing_inputs_report` returned alongside the tool list (e.g., *"To compute AST/ALT ratio you need a lab panel including AST and ALT. Consider getting one."*).

**Note**: scenarios B/C/D are the **target** user journeys. This mission only lands the *skeleton* — the contracts, the registry shape, the file layout, and the stub functions that raise `NotImplementedError`. Execution requires follow-up missions.

### Edge cases

- **Skill already installed**: `install-skills` re-run with identical content → returns `[]`, exit 0.
- **Skill installed in a non-git directory**: writes to `.claude/skills/` regardless of git state; not its concern.
- **Migration applied twice**: idempotent via `ADD COLUMN IF NOT EXISTS`.
- **`dim_metric.yaml` parse failure**: smoke test fails loudly.
- **`importlib.resources` lookup in editable install (`pip install -e .`) vs wheel**: NFR-006 explicitly tests both.
- **A community parser tries to emit `derived:*`**: caught at code review per `parsers/CONTRACT.md` rule (C-011). Future possible enforcement: a CI check that greps generated parser files.
- **`SignalSpec.revision` field is unused at skeleton time**: that's correct. It's reserved metadata for the future `hpipe revalidate` command described in `docs/UPDATE_STRATEGY.md`.

## 7. Success criteria

- **SC-001**: All 19 FRs verified per their Verification columns. `pytest tests/test_skeleton.py -v` lists each FR-### in test names.
- **SC-002**: `uv run python -m pytest -q` reports `≥18 passed` (17 existing + ≥1 net new from `test_skeleton.py`).
- **SC-003**: `uv run hpipe doctor` exits 0 with no new red rows.
- **SC-004**: `uv run hpipe install-skills` from a clean temp directory produces `.claude/skills/parser-generator/SKILL.md` and exits 0; second invocation prints "no changes" and exits 0.
- **SC-005**: `git log --oneline -- src/premura/engine/__init__.py` shows exactly this mission's commit (proves nothing was smuggled into the skeleton).
- **SC-006**: After `pip install -e .`, `python -c "from importlib.resources import files; assert files('premura').joinpath('skills/parser-generator/SKILL.md').is_file()"` returns true.
- **SC-007**: Fresh `hpipe ingest` followed by `SELECT category, COUNT(*) FROM hp.dim_metric GROUP BY 1` shows non-null categories.
- **SC-008**: `python -c "from premura.engine import signal, SignalSpec, REGISTRY; assert REGISTRY == {}; print('open boundary OK')"` succeeds — the engine contract is loadable independently of any implementation.

## 8. Key entities

- **`hp.dim_metric`** — existing table gains six new columns (`category`, `validity_window`, `missing_data_policy`, `aliases`, `loinc`, `ieee1752`). All nullable. Newly seeded rows populate `category` and, where possible, `loinc` or `ieee1752`. `aliases` is JSON with flat per-language keys.
- **`PluginParser` Protocol** — new structural type in `src/premura/parsers/base.py`. Extends `Parser` additively. Used by future community-contributed parsers.
- **`PluginParseResult` dataclass** — new in `src/premura/parsers/base.py`, extends `ParseResult` with `language_detected: str | None`, `unmapped_metrics: list[str]`, `confidence: float`. Returned by `PluginParser.parse()`.
- **`SignalSpec` dataclass** — new in `src/premura/engine/_registry.py`. 8 fields: `name`, `domain`, `inputs`, `output`, `priority`, `auto_safe`, `revision`, and `fn`. Frozen.
- **`REGISTRY` dict** — module-level `dict[str, SignalSpec]` in `src/premura/engine/_registry.py`. Empty at import time; populated lazily by `@signal(...)` decorators when signal functions are imported.
- **Claude Code skill manifest** — markdown file at `src/premura/skills/<skill-name>/SKILL.md`. Shipped as package data. Copied into `.claude/skills/<name>/` by `install_skills`.
- **Ontology row (extended)** — entry in `dim_metric.yaml`:
  ```yaml
  - metric_id: lab:hemoglobin
    display_name: Hemoglobin
    canonical_unit: g/dL
    value_kind: instantaneous
    category: blood:cbc
    validity_window: P3M               # ISO 8601 duration
    missing_data_policy: none
    aliases:
      en: [Hgb, Hb, hemoglobin_total]
      it: [emoglobina, HB]
      de: [Hämoglobin, Hb]
    loinc: "718-7"
    ieee1752: null
    description: "Total haemoglobin in blood, principal oxygen carrier."
  ```

## 9. Assumptions

- The user's `~/repos/no_git/health_digitalizatino/` repo is reachable from the implementation machine and contains ingestion logic plus some IT/DE alias maps referenced in [FEATURE_BLOOD.md](../../docs/FEATURE_BLOOD.md). Only clinically standard aliases are kept; vendor-local or OCR-noisy names are dropped. If the repo is absent at implementation time, the agent generates ≤30 lab rows with English-only names and flags the gap.
- LOINC codes are sourced manually for the ~80 lab markers (no automation; ≈2 hours of curation against [Regenstrief's LOINC search](https://loinc.org/search/)).
- IEEE 1752.1 codes are sourced from the IEEE schema for wearable metrics where the standard publishes one. Where it doesn't, the field is `null`.
- "Spec-kitty-style skill install" means a directory copy/symlink. The implementation does not need to mirror spec-kitty's internals — only the user-visible contract of "shipped with package, materialised by an install command".
- The mission does NOT need to coordinate with the parallel v1-closeout PR beyond shared `STATUS.md` update lines, because file scopes are disjoint by C-002.
- Bulk-edit gate (`change_mode: bulk_edit`) is NOT required — the only "rename" was performed by the user before mission creation; this mission introduces new files and adds rows to a YAML, neither of which is a same-string-across-files edit. `signals/` → `engine/` is a naming choice for a *new* subpackage that hasn't been created yet; no cross-file rename is implied.
- DuckDB ≥1.1 supports `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (verified in research.md). If the pin loosens, migration 002 may need a Python-side check.

## 10. Glossary

- **Skeleton** — placeholder modules with declared contracts but no behavior. Importing them succeeds; calling their functions raises `NotImplementedError`.
- **Stage** — one of the four data-flow layers in [STAGES.md](../../docs/STAGES.md): Ingest, Engine (was "Signal processing"), MCP, UI.
- **Pillar** — one of the six trajectory commitments in [VISION.md](../../docs/history/product/VISION.md).
- **Skill** — a Claude Code skill manifest (`SKILL.md` + frontmatter). When installed under `.claude/skills/<name>/`, Claude Code discovers it.
- **`PluginParser`** — the Protocol future community parsers implement. Adds `declares_metrics`, `language_hint`, and a `PluginParseResult` return type to the existing `Parser` contract.
- **`SignalSpec`** — the registry record for one signal function in the engine. Carries domain tags, inputs, output, priority, revision, and auto_safe.
- **Federated work** — work done by external contributors (or external AI agents) via PRs against this repo, governed by `parsers/CONTRACT.md` and `AGENTS.md`. Parsers are federated. Engine signal functions are not (they're core/proprietary territory).
- **LOINC** — Logical Observation Identifiers Names and Codes; the free standard ontology for clinical lab tests.
- **IEEE 1752.1** — IEEE standard for mobile-health data.
- **Ontology row** — one entry in `dim_metric.yaml`.
- **`derived:*` namespace** — reserved metric_id prefix for outputs of engine signal functions. Off-limits to parsers (C-011).
