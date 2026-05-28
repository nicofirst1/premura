# 01 — Repo Baseline Inventory (Stage 2 engine)

> Mission: `grounded-extensible-engine-research-01KSD0D1` · WP01 · supports FR-001
> Purpose: a source-backed snapshot of what Premura has **already committed** about its Stage 2 signal engine, what is **known temporary debt**, and what is **still an open design question** — so WP02–WP06 can cite this instead of re-deriving the baseline.

This document describes shipped reality and current docs only. Where docs are aspirational (e.g. `VISION.md`), that is flagged explicitly. Every top-level claim carries an inline file reference.

---

## Sources used

### Authoritative (shipped behavior + locked boundaries)

- `docs/architecture/STAGES.md` — the source of truth for the four-stage pipeline and the Stage 2 contract; also records the temporary direct-read exception.
- `docs/architecture/UPDATE_STRATEGY.md` — defines the six warehouse-update kinds and which are handled today; owns the `derived:`-row invalidation story tied to `SignalSpec.revision`.
- `docs/adr/0002-mcp-local-warehouse-boundary.md` — the locked decision that MCP (Stage 3) reads the local warehouse directly while `age` stays at export/upload.
- `src/premura/engine/_registry.py` — the shipped Stage 2 registration shape: `SignalSpec` dataclass + `signal(...)` decorator + module-level `REGISTRY`.
- `src/premura/engine/__init__.py` — the shipped public Stage 2 API: `compute`, `list_by_domain`, `list_auto_safe`, `check_inputs_available`, `list_unavailable`, plus `derived:*` persistence.
- `src/premura/engine/lab_ratios.py` — the only concrete signals shipped so far: three derived lab ratios (`ldl_hdl_ratio`, `ast_alt_ratio`, `tg_hdl_ratio`).
- `src/premura/dim_metric.yaml` — the controlled metric vocabulary that carries `validity_window` and `missing_data_policy` per metric (the inputs Stage 2 reads).
- `docs/operations/STATUS.md` — the authoritative snapshot of what is actually shipped today (engine, MCP, parsers, tests).
- `CONTEXT.md` — the project's canonical vocabulary; binds the plain-English terms this mission must reuse.

### Supporting / historical (intent and trajectory, not shipped contract)

- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md` — phase-level sequencing; named source of truth for phase planning, positions deeper Stage 2 work as still-missing v2 payoff.
- `docs/product/ROADMAP.md` — older prose narrative of upcoming work; useful for direction, explicitly *not* a contract.
- `docs/history/product/VISION.md` — long-term pillars (extensibility, teaching, privacy); explicitly labeled "proposal/archive, not a build contract."
- `kitty-specs/grounded-extensible-engine-research-01KSD0D1/spec.md` and `plan.md` — this mission's own framing and key entities.

Watchout for later WPs: treat `VISION.md` / `ROADMAP.md` prose as direction only. Where it conflicts with `STAGES.md`, the engine code, or `STATUS.md`, the shipped sources win (`docs/product/FULL_APP_DEVELOPMENT_PLAN.md` "Roadmap Principles").

---

## Stable commitments

These are already decided. A later WP can build on them without re-litigating.

1. **Stage 2 is the deterministic signal-processing layer** that turns raw warehouse rows into *answerable* signals. It has no network and no LLM; it must be inspectable and reproducible from the warehouse alone (`docs/architecture/STAGES.md` §2).
2. **Stage boundaries are fixed and ordered**: Ingest → Signal processing (Stage 2) → MCP (Stage 3, the only model-facing and only network-touching stage) → User interface (Stage 4, presentation/teaching). A feature is placed by where it sits in this flow (`docs/architecture/STAGES.md` "The four stages", "Boundary contracts").
3. **Stage 2 owns four families of responsibility**, already named in the architecture: time-validity (per-metric freshness windows), missing-data policy (per-metric imputation rules + an `is_imputed` mask), derived signals (compound metrics persisted under `metric_id` prefix `derived:`), and the signal selector (ranking which signals can answer a question given this warehouse's actual contents) (`docs/architecture/STAGES.md` §2).
4. **The Stage 2 seam is shipped as an open boundary.** Registration is via the `SignalSpec` frozen dataclass and the `@signal(...)` decorator into a module-level `REGISTRY`; importing `premura.engine` never imports any signal implementation, so a proprietary engine package could reimplement the boundary without breaking callers (`src/premura/engine/_registry.py`; `src/premura/engine/__init__.py` module docstring).
5. **The shipped public Stage 2 API is concrete**: `compute(spec_name, conn)`, `list_by_domain(domain)`, `list_auto_safe()`, `check_inputs_available(inputs, conn, within)`, and `list_unavailable(domain, conn)` (`src/premura/engine/__init__.py` `__all__`). These are no longer stubs — `STATUS.md` lists "Signal engine foundations" as shipped with 82/82 tests green (`docs/operations/STATUS.md` "What's working end-to-end").
6. **`SignalSpec` already carries the fields a contribution model needs**: `name`, `domain` (list of tags), `inputs` (canonical `metric_id`s), `output` (must start with `derived:` when set), `priority` (`high`/`normal`/`low`, drives whether missing-input gaps are surfaced), `auto_safe` (opt-in for future auto-precompute), `revision` (bump on logic change), and `fn` (`src/premura/engine/_registry.py` `SignalSpec`).
7. **Derived outputs persist back into the warehouse** under a `derived:` `metric_id`, with the `SignalSpec.revision` stamped into each row's `raw_payload`, and conflicts resolved by `dedupe_key` on insert (`src/premura/engine/__init__.py` `_persist_derived_rows`; `docs/architecture/UPDATE_STRATEGY.md` §(d)).
8. **Input availability is validity-gated, not just presence-gated.** `check_inputs_available` consults each metric's `validity_window` from `hp.dim_metric` and treats stale-past-window data as unavailable; the `dim_metric.yaml` ontology already supplies those windows and missing-data policies (`src/premura/engine/__init__.py` `check_inputs_available`; `src/premura/dim_metric.yaml` header + per-metric `validity_window` / `missing_data_policy`).
9. **The first concrete signals are the three sparse lab ratios** shipped in M3: `derived:ldl_hdl_ratio`, `derived:ast_alt_ratio`, `derived:tg_hdl_ratio`, all `priority="high"`, `auto_safe=True`, tagged to `blood` plus `cardiometabolic`/`liver` domains (`src/premura/engine/lab_ratios.py` `register_builtin_signals`; `docs/operations/STATUS.md`).
10. **Local-first privacy posture is non-negotiable** and inherited by every stage: cleartext never leaves the machine unencrypted, no telemetry, network only on explicit user action at Stage 3 (`docs/history/product/VISION.md` Pillar 6; `docs/architecture/STAGES.md` §3).
11. **Stage 2 relationship to Stage 3 and Stage 4 is committed**: Stage 3/MCP is supposed to call Stage 2 signal functions (not the warehouse) so callers receive validity- and imputation-gated results; Stage 4 only presents/teaches what Stage 3 hands it (`docs/architecture/STAGES.md` "Boundary contracts"). The long-term intent is for user-facing MCP tools to lean on engine-backed signal functions rather than direct fact-table reads (`docs/product/ROADMAP.md` "Concrete build order" item 5; `docs/product/FULL_APP_DEVELOPMENT_PLAN.md` Phase 1 follow-on list).

---

## Known debt / temporary exceptions

These are committed *as debt*: documented, accepted for now, and expected to close. Later WPs must not treat them as the target architecture.

1. **Direct-read of the warehouse by shipped MCP tools (the headline exception).** As of 2026-05-24 the shipped Stage 3 tools — `query_warehouse`, `list_metrics`, `metric_summary` (`src/premura/mcp/server.py`, exposed via `src/premura/mcp/entrypoint.py`) — read `hp.fact_measurement` / `hp.fact_interval` **directly**, breaching the "MCP never reads `fact_measurement` directly" rule. This is a deliberate, transitional operator/expert slice from M2, accepted *while Stage 2 is still mostly thin*. The rule itself stands; the tools carry warnings that their output bypasses validity and imputation policy and must not back freshness- or imputation-sensitive health conclusions. The exception closes when agent-facing analysis routes through validity-gated, engine-backed signal functions, at which point `query_warehouse` is narrowed to operator-only (or removed) and `list_metrics` / `metric_summary` are re-backed by signal functions (`docs/architecture/STAGES.md` "Known exception (temporary): direct-read operator tools"; `docs/adr/0002-mcp-local-warehouse-boundary.md`). **This is the central reason the mission exists: Stage 2 is thin, so Stage 3 is reaching past it.**
2. **The signal selector is named but not shipped.** It is listed as one of Stage 2's four responsibilities, but no selector code exists yet (`docs/architecture/STAGES.md` §2; the engine package ships only `list_by_domain` / `list_unavailable` discovery helpers, not ranking — `src/premura/engine/__init__.py`).
3. **Derived-signal invalidation is metadata-only.** The `revision` field is stamped into persisted rows, but there is no `hpipe revalidate` command yet; re-deriving today means manually deleting stale `derived:*` rows and re-ingesting (`docs/architecture/UPDATE_STRATEGY.md` §(d), "deferred").
4. **`auto_safe` is metadata only.** The flag exists and the three lab ratios set it, but the auto-precompute-on-ingest flow it describes is not wired up; `list_auto_safe()` only returns the set (`src/premura/engine/__init__.py` `list_auto_safe` docstring "This is metadata only"; `src/premura/engine/_registry.py` `auto_safe`).
5. **Missing-data imputation policy is declared, not yet executed by a public engine path.** `dim_metric.yaml` carries the per-metric `missing_data_policy` (`none` / `last_observation_carried_forward` / `linear_interp` / `seasonal_naive`) and STAGES.md describes the `is_imputed` mask, but no shipped Stage 2 function applies imputation or returns that mask yet (`src/premura/dim_metric.yaml`; `docs/architecture/STAGES.md` §2 missing-data bullet — the engine `__init__.py` reads validity windows but does not impute).
6. **Canonical-vocabulary rename is deferred.** Legacy v1 `metric_id`s are preserved as-is; the eventual namespacing/rename routes through a future full-rebuild mission, not in-place edits (`src/premura/dim_metric.yaml` header; `docs/architecture/UPDATE_STRATEGY.md` §(e), §(f), "deferred").
7. **Only one concrete signal family ships.** The engine has exactly three lab ratios; everything else in Stage 2 is currently boundary-and-metadata. Deeper Stage 2 signal behavior is explicitly listed as still-missing v2 payoff (`src/premura/engine/lab_ratios.py`; `docs/product/FULL_APP_DEVELOPMENT_PLAN.md` "Current Starting Point").

---

## Open design questions

These are genuinely undecided. This mission (WP02–WP06) is meant to answer or scope them; they are not yet committed.

1. **Contribution shape / contract.** `SignalSpec` is a registration record, not a contributor-facing contract. What rationale, evidence, inputs, outputs, caveats, tests, and review notes a *new* engine function must ship with is undecided. The parser side has a written `src/premura/parsers/CONTRACT.md` to borrow from; the engine has no equivalent (mission `spec.md` FR-004; `plan.md` Track 3).
2. **Grounding / evidence rules.** What counts as "scientifically grounded enough" to admit a function — the accept / defer / reject rubric and the evidence package behind it — is not defined anywhere in the repo today (mission `spec.md` FR-003, key entity "Grounding rubric").
3. **Reviewer quality gate.** No bounded pass/fail checklist exists for accepting a new engine function (mission `spec.md` FR-005, NFR-003 caps it at ≤10 checks).
4. **Seam disposition (keep / change / defer).** Which current seam elements (`SignalSpec` fields, `REGISTRY`, `compute`, `list_by_domain`, availability checks, `revision`, `derived:` persistence) survive into the contribution model unchanged versus need change is not yet decided (mission `spec.md` FR-006; `plan.md` Track 4).
5. **Baseline personal profile data.** Some useful functions need stable context like height, birth date, or sex, which do not fit cleanly as ordinary observed measurements. How those attributes are stored and updated is an explicit, separate design problem tracked in GitHub issue [#6](https://github.com/nicofirst1/premura/issues/6); this mission must name the dependency, not solve it (mission `spec.md` FR-007, C-004; key entity "Baseline personal profile attribute").
6. **Taxonomy of health directions, question shapes, and function families.** The directions exist informally across docs (sleep, cardio, metabolic, stress, recovery, gut, overview), but a normalized first-wave taxonomy is not committed (mission `spec.md` FR-002; `docs/history/product/VISION.md` Pillar 4; `docs/architecture/STAGES.md` §4 interview list).
7. **Which functions are the quick wins.** A ranked 3–7 shortlist biased toward commonly-available data (steps, weight, height, heart rate) does not exist yet (mission `spec.md` FR-008).
8. **Whether the engine becomes a plugin/skill system.** `VISION.md` Pillar 1 bets on Claude Code skills for *parsers* and leaves "what's the contract between a skill and the loader" as an open question; whether engine functions follow a similar extensibility model is undecided and out of scope to *implement* here (`docs/history/product/VISION.md` Pillar 1; mission `spec.md` §2 "Out of scope").

---

## Terminology notes (normalized vocabulary for this mission)

`CONTEXT.md` is the binding source for project vocabulary; the maintainer is an AI researcher, not a day-to-day software engineer, so prefer plain English and avoid SE jargon (`CONTEXT.md` "Maintainer mental model"). The terms below drift across docs; this mission should use the wording in the right-hand column.

| Term | Where it appears / drift | Wording this mission reuses |
|---|---|---|
| **Health direction** | `CONTEXT.md` defines it as a user-facing *routing* entry point (sleep, energy, mood, movement, recovery, longevity) — explicitly *not* a metric or a UI tab. `STAGES.md` §4 lists a slightly different set (sleep, cardio, metabolic, stress, mental, gut, lab/cardiometabolic, overview). The engine's `SignalSpec.domain` uses tags like `liver`, `blood`, `cardiometabolic` — these are *domain tags on a signal*, a narrower thing than a user-facing direction. | "Health direction" = the user-facing area a person enters through (a routing choice). Keep it distinct from a signal's `domain` tag. When referring to code, say "the signal's `domain` tag", not "direction". |
| **Signal** | `CONTEXT.md`: a validity-checked, question-ready value or series shaped to answer something; may be raw or derived. Avoid "stat", "feature", "datapoint". | Use "signal" exactly as `CONTEXT.md` defines it. A signal is always shaped to answer a question, not raw data. |
| **Derived signal** | `CONTEXT.md`: a signal computed from one or more canonical metrics and persisted with a `derived:` `metric_id`; belongs to signal processing, not ingest. Matches the engine's `derived:*` outputs. Avoid "synthetic field", "convenience calculation". | "Derived signal" for any engine output persisted under `derived:`. The three lab ratios are the canonical examples. |
| **Engine function** | Not a `CONTEXT.md` term. Docs/code call the unit variously: STAGES.md says "deterministic Python functions" / "four families of function"; the code calls a registered unit a `SignalSpec` with an `fn`; the mission spec uses "engine function" and "engine function family". | Use "engine function" for one registered Stage 2 signal function (one `SignalSpec` + its `fn`), and "engine function family" for a class of them (summary, trend, ratio, freshness-aware status, change detection). Explain on first use as "a registered Stage 2 signal function". |
| **Contribution contract** | Not yet a real artifact (see Open Questions). `CONTEXT.md` warns against naming abstract SE concepts like "contract"/"seam" — say "the agreed shape of what a new engine function must provide" on first use. The parser side has `src/premura/parsers/CONTRACT.md` as a spirit-analogue. | Use "contribution contract", but gloss it in plain English on first use: "the package a contributor must hand in to add a new engine function — its rationale, inputs, outputs, caveats, tests, and review notes." Do not over-formalize it into governance jargon. |

Additional vocabulary guardrails for later WPs (from `CONTEXT.md`):
- Avoid invented coinages (e.g. "decomposition surface", "compression bias") and Jira-isms ("epic", "story points"). In this repo's planning vocabulary a unit of work is a **mission** broken into **work packages**, and an exploratory study is an **ablation study** producing a **design decision note** (folder `docs/adr/` is kept, but call them "design decision notes" in prose).
- When describing a stage boundary, say "where stage X hands off to stage Y" rather than "the seam/contract" (`CONTEXT.md` "Concepts to describe in plain English").

---

## How later WPs should use this baseline

- **WP02 (taxonomy)** can start from the health-direction list and the `domain`-tag-vs-direction distinction above, plus the four function families in `STAGES.md` §2, rather than re-reading the docs.
- **WP03 (grounding rubric + contract + gate)** should treat Open Questions 1–3 as its charter and borrow structure from `src/premura/parsers/CONTRACT.md`.
- **WP04 (seam evaluation + profile data)** should disposition the eight `SignalSpec` fields and the five public API functions listed under Stable Commitments 5–8, and route profile-data design to issue #6 (Open Question 5).
- **WP05 (quick wins + follow-on)** should bias toward the commonly-available metrics already in `dim_metric.yaml` / `STATUS.md` and keep the direct-read debt (Known Debt 1) in view as the gap the engine is meant to close.
