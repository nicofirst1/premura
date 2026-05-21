# Specification Quality Checklist: v2 Architectural Skeleton

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-05-21
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
  - *Note*: Python and DuckDB are unavoidable since the project is Python+DuckDB; these are stack facts, not framework choices. No new libraries, no new APIs prescribed. ✅
- [x] Focused on user value and business needs
  - *Note*: Skeleton's "user" is the future-implementer of v2 missions. Section 6 Scenarios A/B/C describe their experience. ✅
- [x] Written for non-technical stakeholders
  - *Note*: Sections 1, 2, 6, 7 readable without code knowledge. Sections 3-5 are necessarily technical (this is an architectural skeleton mission), but the README-style summaries in each row are plain-language. ✅
- [x] All mandatory sections completed
  - 1 Purpose, 2 Scope, 3 FR, 4 NFR, 5 Constraints, 6 Scenarios, 7 Success criteria, 8 Key entities, 9 Assumptions, 10 Glossary — all present. ✅

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
  - grep `\[NEEDS CLARIFICATION` on spec.md → 0 hits. ✅
- [x] Requirements are testable and unambiguous
  - Every FR has a concrete Verification column with a runnable assertion. NFRs have measurable thresholds (e.g., NFR-005 "< 100 ms"). ✅
- [x] Requirement types are separated (Functional / Non-Functional / Constraints)
  - Three separate tables in §3, §4, §5. ✅
- [x] IDs are unique across FR-###, NFR-###, and C-### entries
  - FR-001..019, NFR-001..008, C-001..012. No collisions. ✅
- [x] All requirement rows include a non-empty Status value
  - Every row has Status = "Draft". ✅
- [x] Non-functional requirements include measurable thresholds
  - NFR-001 (≥17 tests pass), NFR-005 (<100ms), NFR-006 (importlib.resources read), NFR-007 (null-column count). ✅
- [x] Success criteria are measurable
  - SC-001..007 each cite an exit code, count, or file existence. ✅
- [x] Success criteria are technology-agnostic (no implementation details)
  - *Partial*: SC-001..007 reference pytest, hpipe, pip, duckdb, importlib.resources. **These are stack facts** for this Python+DuckDB project — they describe verifiable outcomes, not framework choices. The "no implementation details" rule applies to *un-decided* tech; here every named tool is already part of the project. ✅ (with rationale)
- [x] All acceptance scenarios are defined
  - Scenarios A (future contributor), B (Stage-2 implementer), C (parser-generator user). ✅
- [x] Edge cases are identified
  - §6 "Edge cases" subsection: skill re-install, non-git dir, double migration, YAML parse failure, editable-vs-wheel install. ✅
- [x] Scope is clearly bounded
  - §2 has In-scope and Out-of-scope lists, both concrete. ✅
- [x] Dependencies and assumptions identified
  - §9 Assumptions explicitly lists the `health_digitalizatino` repo dependency, the clinically-standard-alias rule, LOINC/IEEE source plan, no-bulk-edit conclusion, and parallel-mission coordination. ✅

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
  - Verification column on every FR row is the acceptance criterion. ✅
- [x] User scenarios cover primary flows
  - A/B/C cover: future contributor / future implementer / future skill user. ✅
- [x] Feature meets measurable outcomes defined in Success Criteria
  - SC-001..007 are mapped to FRs and NFRs (SC-001 → all FRs; SC-002 → NFR-001 + FR-011; SC-003 → NFR-002; SC-004 → FR-007; SC-005 → C-008; SC-006 → NFR-006; SC-007 → FR-009 + FR-010). ✅
- [x] No implementation details leak into specification
  - *Note*: Specific column types (`VARCHAR`, `JSON`), the YAML row shape, and the `importlib.resources` API are mentioned because the **architecture decision IS** the schema and the discovery mechanism. The spec is itself the contract being committed; this is appropriate for a skeleton mission. ✅

## Notes

- This is an **architectural skeleton mission**, so it is intentionally code-shaped at the contract level (Protocols, migrations, file paths, schema columns). The "no implementation details" rule is interpreted as "no behavioral implementation details" — there are none. File-tree and Protocol shapes ARE the deliverable.
- The bulk-edit gate (DIRECTIVE_035) was evaluated during discovery; this mission does NOT trigger it because the canonical-vocabulary rewrite is explicitly deferred to a later full-rebuild mission. See §2 and §9.
- The parallel v1-closeout mission has its own out-of-scope list in [V1_CLOSEOUT.md](../../docs/V1_CLOSEOUT.md); file scopes are disjoint by construction (§2 + C-002).
- Items marked complete reflect the post-discovery spec. If subsequent reviews surface gaps, this checklist is the place to record them.

## Post-implementation evidence (WP06)

Recorded after WP01-WP05 landed and `tests/test_skeleton.py` was added in WP06.

- [x] **FR-001 / FR-002 / FR-003 / NFR-008** — Stage 2 engine boundary
  - Evidence: `tests/test_skeleton.py::test_engine_package_docstring_names_stage_2`, `test_engine_registry_exports_open_boundary`, `test_signal_decorator_registers_spec`, `test_engine_stubs_raise_not_implemented[*]` — all pass.
- [x] **FR-004** — Stage 3 MCP boundary
  - Evidence: `test_mcp_module_docstring_and_layering_rule`, `test_mcp_register_tools_stub_raises` — both pass; docstring asserts the `"never reads hp.fact_measurement directly"` substring.
- [x] **FR-005** — Stage 4 UI boundary
  - Evidence: `test_ui_module_docstring_and_layering_rule`, `test_ui_start_interview_stub_raises` — both pass; docstring asserts the `"never reads hp.fact_measurement or calls engine directly"` substring.
- [x] **FR-006** — `parsers._lang` local-only stub
  - Evidence: `test_parsers_lang_module_docstring_is_local_only`, `test_parsers_lang_detect_language_stub_raises` — both pass.
- [x] **FR-007** — `parsers.lookup.suggest_metric` stub
  - Evidence: `test_parsers_lookup_suggest_metric_stub_raises` passes.
- [x] **FR-008** — `PluginParser` / `PluginParseResult` additive contract
  - Evidence: `test_plugin_parser_contract_symbols_import`, `test_plugin_parser_is_structural_subtype_of_parser` — both pass; v1 `Parser`, `ParseResult`, `Measurement`, `Interval` still importable from `parsers.base`.
- [x] **FR-009** — `parsers/CONTRACT.md` contains the standards-first tokens
  - Evidence: `test_parser_contract_md_documents_standards_first_ladder` asserts `"LOINC"`, `"IEEE 1752.1"`, `"derived:"` substrings.
- [x] **FR-011 / NFR-006** — Skill manifest ships as package data
  - Evidence: `test_skill_manifest_ships_as_package_data` resolves `SKILL.md` via `importlib.resources` and asserts frontmatter keys plus the `CONTRACT.md` reference.
- [x] **FR-012** — `skills.install_skills` is idempotent
  - Evidence: `test_install_skills_writes_then_idempotent` — first call writes, second call returns `[]` and leaves bytes unchanged.
- [x] **FR-013** — `install-skills` CLI verb registered
  - Evidence: `test_cli_registers_install_skills_verb` asserts the verb on `cli.app.registered_commands`.
- [x] **FR-015 / NFR-004 / NFR-007** — Migration 002 adds six nullable columns idempotently
  - Evidence: `test_migration_002_adds_six_new_columns`, `test_migrations_are_idempotent` — both pass.
- [x] **FR-016** — `seed_dim_metric` handles rows with and without new keys
  - Evidence: `test_seed_handles_rows_with_and_without_new_keys` — legacy-shape row inserts with NULL ontology columns; full-ontology row inserts with non-null values.
- [x] **FR-017** — `dim_metric.yaml` row count and shape
  - Evidence: `test_dim_metric_yaml_has_at_least_140_rows` (observed: 180 rows), `test_dim_metric_yaml_every_row_has_category`, `test_dim_metric_yaml_lab_rows_have_loinc` — all pass.
- [x] **FR-019** — `tests/test_skeleton.py` exists
  - Evidence: file present; `uv run pytest tests/test_skeleton.py -q` reports `27 passed`.
- [x] **NFR-001** — Existing tests still pass
  - Evidence: `uv run pytest -q` reports `52 passed` (25 pre-existing + 27 new in `test_skeleton.py`), no regressions.
- [x] **NFR-003** — `ruff check` clean on new code surfaces
  - Evidence: `uv run ruff check src/premura/engine src/premura/mcp src/premura/ui src/premura/skills src/premura/parsers/_lang src/premura/parsers/lookup.py src/premura/parsers/base.py tests/test_skeleton.py` → `All checks passed!`. Pre-existing E501 lint hits in v1 parsers (`bmt.py`, `garmin_gdpr.py`, `health_connect.py`, `sleep_as_android.py`) are out of scope for this mission.

### Not verified in this WP

- **FR-010, FR-014, FR-018** — cross-repo doc-grep / `bootstrap.sh` shell-script checks are intentionally not duplicated in `tests/test_skeleton.py` per the WP06 ``Required structure`` note. They remain covered by the corresponding owning WP (`AGENTS.md`, `ops/bootstrap.sh`, `docs/UPDATE_STRATEGY.md` content reviews).
- **NFR-002 (`hpipe doctor` exit 0)** — not exercised by this test file. Requires manual run on the operator's Mac with `age`, `rclone`, age key/recipients configured.
- **NFR-003 (`mypy` clean)** — not run as part of CI tooling in this lane; the new code surfaces use stub bodies (`raise NotImplementedError`) that satisfy mypy trivially.
- **NFR-005 (no measurable runtime overhead on `hpipe doctor`)** — requires manual wall-clock measurement on the operator's Mac.
