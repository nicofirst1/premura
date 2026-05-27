# Premura Full App Development Plan

> Status: review draft. Phase-level development plan for the whole app trajectory from the current shipped state forward. Complements `ROADMAP_BOOTSTRAP_PLAN.md`, which now serves mainly as the record of how the first concrete backlog (M1-M3) was instantiated. Product-identity questions are settled in `DOCTRINE.md`.
>
> **Vocabulary note**: this doc uses the project vocabulary defined in `CONTEXT.md` §"Planning" (e.g. "ablation study" rather than "spike", "design decision note" rather than "ADR"). Live GitHub artifacts (issue titles, label values, file paths) keep their existing names — only prose follows the new vocabulary.

## Purpose

Describe the likely end-to-end development path for Premura from the current shipped state through the next major phases of the product.

This file is not the GitHub backlog and not the first execution plan. It is the higher-level roadmap that explains:

- what phases the app likely passes through
- what each phase is trying to prove or ship
- which open risks each phase retires
- how the immediate execution plan fits into the larger trajectory

## Inputs Used

- `CONTEXT.md` (vocabulary)
- `docs/product/DOCTRINE.md`
- `docs/operations/STATUS.md`
- `docs/product/VISION.md`
- `docs/product/ROADMAP.md`
- `docs/product/RISK_OPPORTUNITY.md`
- `docs/product/ROADMAP_BOOTSTRAP_PLAN.md`
- `docs/architecture/STAGES.md`
- `docs/architecture/UPDATE_STRATEGY.md`
- `docs/research/PROPOSAL_LABS.md`
- `/tmp/premura-planning-handoff-2026-05-22.md`

## Relation To Existing Docs

- `docs/product/VISION.md` covers the long-term pillars (extensibility, warehouse, AI tools, interview, teaching, privacy). This file is the phase-level expression of how those pillars get built in code.
- **This file is the source of truth for phase-level planning.** `docs/product/ROADMAP.md` is the older prose narrative of upcoming work; several of its phase-shaped sections ("Big idea — MCP server," "New source class — clinical labs," "Smaller follow-ups," "Mid-term — analytical layer") now overlap with the phases below. ROADMAP.md should be compressed in a follow-up doc pass to pointers into this file. **That compression is pending — track as a small follow-up doc task.**
- `docs/product/ROADMAP_BOOTSTRAP_PLAN.md` is the concrete first pass that justified the original M1-M3 issue set. It still records the rationale for Phases 1 and 2, but it is no longer the current next-action list.
- This file sits between VISION (long-term) and BOOTSTRAP/ROADMAP (near-term execution).

## Current Starting Point

Premura has already shipped:

- four-source ingest into the warehouse
- encryption and opt-in backup flow
- launchd automation
- the federated parser plug-in code (`PluginParser`, `IngestBatch`, `dim_metric.yaml` ontology)
- a real Stage 3 MCP surface — the three raw warehouse tools (`query_warehouse`, `list_metrics`, `metric_summary`) plus six signal-backed tools
- the first real Stage 2 behavior — six grounded, freshness-aware signals (current resting HR, resting-HR trend, steps trend, weight trend, deep-sleep vs own baseline, overnight-HRV change around a date) with a contributor contract (`src/premura/engine/CONTRACT.md`); `ui` remains a stub
- the authoritative profile/intake **meaning contract** (`docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md` plus the `docs/architecture/contracts/profile_and_intake_*.yaml` surfaces, design decision note `docs/adr/0005-profile-and-intake-contract.md`). This fixes where baseline profile context, nutrition intake, and supplement intake live and what they mean — it ships **no** storage, importer, capture screen, or Stage 2 answer; it only settles the boundary so follow-on missions build against one home.

So `engine` and `mcp` are no longer empty stubs: Stage 2 and part of Stage 3 are real for six approved question shapes, and the long-open profile/intake boundary question is now answered at the contract level rather than per-mission. What is still missing is the rest of the v2 payoff:

- the deterministic Stage 3 statistics tools (`correlate`, `paired_t_test`, …), PubMed integration, and the signal selector — none of which this first grounded slice built
- broader Stage 2 coverage beyond the six approved descriptive/comparative answers; the six are non-diagnostic and carry no significance or causation claims, and profile-dependent answers (BMI, age-adjusted interpretation) remain deferred — but now as an implementation mission *over* the profile/intake contract, not as an unresolved boundary question
- a first new source class beyond the original wearable/app quartet
- proof that the parser-skill model is viable
- proof that the teaching/interview layer can be useful rather than aspirational

Small v1 residue (real-data SAA validation, project wiki hub page) is not scheduled into any phase. SAA validation is filed only if a real export breaks something; the wiki hub waits until the codebase is more mature.

## Roadmap Principles

1. Resolve architectural uncertainty before scaling surface area.
2. Prefer one real end-to-end slice over many speculative documents.
3. Treat Stage 2 and Stage 3 as product-critical; v2 is not just "more parsers."
4. Use real risk retirement from `RISK_OPPORTUNITY.md` to decide what comes next.
5. Keep the system local-first and faithful to the stage boundaries in `STAGES.md`.

## Conventions

This plan follows the conventions established in `ROADMAP_BOOTSTRAP_PLAN.md` §"Conventions":

- **Tag-cut on milestone close**: each phase ships as a milestone (`v2.0`, `v2.1`, …) and closes with a corresponding `git tag` (`v2.0.0`, `v2.1.0`, …). Tags are restore points.
- **Design decision note timing**: design decision notes land *before* missions that introduce a new stage interface or a new public type; *after* missions where the decision is an implementation detail inside an already-approved direction. See `docs/adr/0001-ingest-batch-parser-seam.md` for the post-mission template (the folder `docs/adr/` is kept for filesystem stability; in prose call them "design decision notes").
- **Mission title format**: GitHub tracking issues use `[M1]`/`[M2]`/`[M3]` prefixes. New missions in later phases follow the same convention (`[M4]`, `[M5]`, …).
- **Multi-stage labels**: missions that genuinely span stages carry multiple `stage:*` labels (e.g. M3 carries both `stage:ingest` and `stage:engine`).
- **Mission breakdown**: one GitHub tracking issue per mission. Intra-mission breakdown lives in `kitty-specs/<slug>/` as work packages. Cross-mission dependencies are encoded as "blocked by" comments on tracking issues.

## Development Phases

### Phase 1: `v2.0 analytical surface foundation`

> **Status: largely shipped.** The MCP access decision is settled, the first MCP query surface (M2) landed, and a follow-on grounded-signals mission added six Stage 2 answers with six signal-backed Stage 3 tools routed through them. The stage hand-off is real for those six question shapes. Deterministic stats tooling still belongs to Phase 3.

#### Goal

Make the hand-off from Stage 2 to Stage 3 real and usable.

#### Main work

- `mcp-server-duckdb + age` compatibility ablation study (M1)
- Produce the design decision note that locks how MCP reads the warehouse
- Build the first MCP query surface (M2):
  - `query_warehouse`
  - `list_metrics`
  - `metric_summary`

#### Why this phase exists

This is the highest-leverage open question in the current docs. If Premura is supposed to become an analytical tool rather than only a warehouse, this question has to be settled early.

#### Risks retired

- the open MCP-access question from `RISK_OPPORTUNITY.md:151`
- a major source of uncertainty for all later analytical work

#### Likely work shape

- one mission for the ablation study + design decision note
- one mission for the first MCP surface

#### Exit criteria

- there is a documented, accepted way for MCP tools to read the warehouse
- the MCP layer is no longer a stub package only
- the app can answer basic warehouse questions through a real Stage 3 surface
- tag `v2.0.0` cut on milestone close

### Phase 2: `v2.1 labs`

> **Status: shipped in first form.** M3 is closed: lab ingest, sparse-signal rules, and first derived lab ratios landed. The remaining lab follow-ons are narrower: Stage 3 lab exposure, extraction-quality validation tooling, and any parser corrections surfaced by real operator use.

#### Goal

Add the first new source class and the first substantive Stage 2 engine behavior.

#### Main work

- Run the docling ablation study on real lab PDFs
- Add the lab parser (in-tree at `src/premura/parsers/lab_pdf.py`)
- Add lab ontology rows
- Seed validity windows for sparse clinical metrics
- Seed missing-data policies for sparse clinical metrics
- Add first derived lab ratios

#### Why this phase exists

The lab proposal is the first place where Premura becomes more than a wearable dump unifier. It also forces real Stage 2 rules around validity, sparsity, and derived signals.

#### Risks retired

- proves whether Premura can handle a source class that is sparse, multilingual, and structurally different from the v1 sources
- starts converting Stage 2 from architecture placeholder to real behavior

#### Likely work shape

- one mission (M3), decomposed into WPs inside `kitty-specs/<m3-slug>/`
- Stage 3 lab-signal exposure stays out of this phase; filed as cross-mission sub-work that depends on M1's design decision note and M2's MCP infrastructure

#### Exit criteria

- the warehouse can ingest a representative lab corpus
- Stage 2 has real validity and missing-data policy behavior for at least one meaningful domain
- at least one family of derived signals exists for sparse clinical data
- tag `v2.1.0` cut on milestone close

### Phase 3: `v2.2 analytical depth`

#### Goal

Turn the first MCP surface into an actually useful analytical surface.

#### Main work

- Add deterministic stats tools from `ROADMAP.md` (`correlate`, `paired_t_test`, `rolling_mean`, `change_point`, …)
- Add PubMed search/fetch integration
- Add the personal-data bridge from literature to warehouse queries
- Add reproducible research trace or notebook output

#### Why this phase exists

Phase 1 proved that MCP can safely access the warehouse and answer six grounded descriptive/comparative questions through Stage 2. This phase is a different layer: it adds the deterministic *statistics* (correlation, significance tests, change-point detection) and literature grounding that the grounded-signals slice deliberately stayed out of. It proves that Premura can support evidence-backed n-of-1 analysis, not just non-diagnostic descriptive answers.

#### Risks retired

- Addresses one half of `R7` (LLM narration honesty: tools return CIs and effect sizes so the LLM cannot fabricate them).
- The underlying half of R7 — n=1 statistical weakness from confounded, self-correlated, life-event-driven time series — remains. The mitigation that belongs here is **surfacing validity and confound warnings alongside CIs**, not just returning CIs. Tool outputs should include `validity_status`, `is_imputed_pct`, and a confound checklist where applicable.

#### Likely work shape

- one or more missions, depending on how much of the analytical surface lands together

#### Exit criteria

- the app can answer at least a small set of concrete analytical questions through deterministic tools
- analytical output is reproducible enough to be inspected later
- PubMed use is tool-grounded rather than prompt-grounded
- tool outputs include validity/confound metadata, not just point estimates

### Phase 4: `v2.3 parser ecosystem validation`

#### Goal

Test whether the parser-skill and parser-generator story is real or still speculative.

#### Main work

- Build at least one real third-party parser outside the original four sources (candidate: Withings CSV, chosen because the format is simple enough that the skill model can be the bottleneck rather than the parsing complexity)
- Use that work to validate the parser plug-in interface and parser-generator workflow
- Decide whether the ecosystem story should be expanded, narrowed, or deferred

#### Why this phase exists

The docs already call out the parser-skill bet as risk `R2`. That risk does not retire through documentation; it retires only when one real external-style parser lands end to end.

#### Risks retired

- `R2` directly

#### Likely work shape

- one mission for the parser itself
- possibly one follow-up task or mission for plug-in interface corrections if the experiment fails cleanly

#### Exit criteria

- either the parser ecosystem model is validated by a real example
- or the project has evidence to scale the ambition back instead of assuming ecosystem traction

### Phase 5: `v2.4 interview + teaching MVP`

#### Goal

Prove that Premura can teach and guide, not just ingest and analyze.

#### Main work

- Add the first CLI interview flow
- Add a small number of curated health-direction tracks
- Add the first teaching patterns for a narrow metric set
- Keep the surface deliberately narrow so the team learns what good teaching requires

#### Why this phase exists

The docs position teaching and interview as core differentiation, but they are also the weakest-validated part of the plan (highest combined severity × likelihood on the risk matrix). This phase turns that into a constrained experiment.

#### Risks retired

- `R4` directly

#### Likely work shape

- one mission, because it crosses Stage 3 and Stage 4 behavior and needs explicit acceptance criteria

#### Exit criteria

- a user can enter through one or two health directions and receive a guided, explainable experience
- the project has learned whether the teaching layer is tractable in CLI-first form

### Phase 6: `v2.5+ ingest and warehouse expansion`

#### Goal

Broaden depth and operational polish after the core analytical and teaching bets have been tested.

#### Candidate work

- `hpipe inspect <file>`
- `hpipe gc` extension for `data/raw/`
- `hp.fact_interval.unit` migration
- historical Garmin backfill flow
- sample-level Garmin HRV and respiration expansion
- FIT-file decoding
- daily Health Connect pickup
- cross-source priority reconsideration

#### Why this phase exists

These are useful, but they are not the strongest differentiators while the app still lacks a real analytical and teaching surface.

#### Likely work shape

- a mix of single-mission items and parallel small efforts under the mission/task split rule

#### Exit criteria

- the warehouse and ingest surface are richer without distracting from the core product identity

## Sequencing Summary

The likely whole-app ordering is:

1. `v2.0 analytical surface foundation`
2. `v2.1 labs`
3. `v2.2 analytical depth`
4. `v2.3 parser ecosystem validation`
5. `v2.4 interview + teaching MVP`
6. `v2.5+ ingest and warehouse expansion`

This is not a rigid dependency chain for every sub-issue. It is the default product-development order that best matches the current docs and open risks.

## Dependency Notes

- The MCP/warehouse access decision (Phase 1) is settled, and the default agent-facing Stage 3 surface is now fully validity-gated. The only remaining lower-guarantee path is the explicit operator entrypoint, which stays separate from the default surface and requires human approval for agent use.
- Lab ingest and Stage 2 lab rules (Phase 2) do not need to wait for the full analytical surface, but lab Stage 3 exposure should.
- Parser ecosystem validation (Phase 4) does not need to wait for the teaching layer.
- Teaching (Phase 5) should wait until there is enough real analytical substance to teach from.

## Risk Retirement Map

### `R2`: parser-skill bet is unproven

Primary retirement phase: `v2.3 parser ecosystem validation`

### `R4`: teaching-as-pillar is the worst risk

Primary retirement phase: `v2.4 interview + teaching MVP`

### `R7`: n=1 stats can mislead

Primary retirement phase: `v2.2 analytical depth`, **partial only**.

R7 has two halves:

1. **LLM narration honesty** — solved by deterministic tools that return CIs and effect sizes; the LLM narrates the tool output rather than producing magnitudes from priors. Phase 3 addresses this.
2. **Underlying n=1 statistical weakness** — confounded by life events, exercise schedule, alcohol, season, illness. Tool outputs that look statistically significant can still teach the user wrong things. Phase 3 mitigates this by attaching validity/confound metadata to tool outputs, but does not eliminate it.

R7 likely never goes to zero. The practical goal is to constrain and surface uncertainty, not to pretend n-of-1 analysis becomes certainty.

## How To Use This Plan

- Use `ROADMAP_BOOTSTRAP_PLAN.md` as the record of why M1-M3 were the first missions, not as the current execution queue.
- Use this file to decide whether a new proposal belongs in the current phase, the next phase, or the parking lot.
- Use `ROADMAP.md` as the shorter live reference until the deferred compression pass folds its phase-shaped sections into pointers here.

## How This Doc Evolves

When a phase closes (its milestone ships and its tag cuts), its section is rewritten as a one-paragraph summary pointing at the closed milestone, the shipped ADRs, and any follow-on missions that emerged. The detailed scope text moves to git history; the live doc stays a forward-looking plan, not a changelog.

When a risk retires, its entry in the Risk Retirement Map is updated to note the retiring artifact (design decision note, mission, or evidence) and the phase that retired it.

## Recommendation

Treat the near-term roadmap as:

- First, treat Phases 1 and 2 as shipped in their initial form: M1-M3 are closed, the first grounded Stage 2/3 slice is live, and labs exist in-tree.
- Second, treat the profile/intake **boundary** as settled at the contract level (see `docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md` and `docs/adr/0005-profile-and-intake-contract.md`). The follow-on work that issue `#6` originally framed as "model baseline profile attributes" is now a set of implementation missions *over* that contract — storage adapter, manual entry, import paths, and the first signals that consume profile/intake (BMI, age-adjusted interpretation) — alongside the deterministic-stats missions. None of those are shipped yet; the boundary they build on is.
- Third, revisit this plan with evidence from that analytical-depth and profile/intake-implementation work before locking parser-ecosystem or teaching missions too tightly.

The biggest mistake would be to plan the teaching layer, parser ecosystem, and ingest expansion in equal detail before the analytical access path and first Stage 2 rules are proven in code.
