# Parser Contributing

> Status: live reference. Parser contributor guide; authoritative parser rules live in `src/premura/parsers/CONTRACT.md`.

This guide is for contributors extending Premura through its federated parser surface. If you are making general code changes across the repo, start with `CONTRIBUTING.md` instead.

## Before building a new parser, check the seam does not already exist

An empty `hp.*` table means no data has flowed yet, not that support is missing. Before proposing a new parser or subsystem, grep the type, loader, and store - not just `registry.py`. Observations (`Measurement`, `Interval`, `ClinicalNote`) are defined in `base.py` and persisted by `store/loader.py`; nutrition and supplement intake persist via `store/profile_intake.py`; diagnoses are captured through the MCP `record_condition_episode` tool rather than a parser.

## Standards-first rule (project-level)

When mapping a vendor field to a canonical `metric_id` (in any parser, any ontology row, any review comment), you MUST resolve in this order and stop at the first match:

1. **Existing alias** in `src/premura/dim_metric.yaml` — call `suggest_metric(X)`.
2. **LOINC** for clinical lab markers — `metric_id = "lab:<english_canonical_name>"`.
3. **IEEE 1752.1** for wearable / physiological metrics.
4. **Bare English canonical name** for reusable cross-vendor concepts that neither LOINC nor IEEE 1752.1 covers.
5. **`vendor:<source>:<field>`** as the fallback for source-specific concepts.

If no step applies, do not invent a `metric_id`. Skip the field at parse time and surface it via `IngestBatch.unmapped_metrics` for human review.

Aliases recorded in `dim_metric.yaml` are restricted to **clinically standard names and abbreviations only** — not free-text search terms or marketing phrasing.

## Where to read next

- **Parser plugin contract (agent-agnostic, authoritative):** `src/premura/parsers/CONTRACT.md` — defines `PluginParser`, `IngestBatch`, the full decision tree, the `derived:` namespace rule, and the same-PR ontology rule.
- **Claude Code skill (parser-generation walkthrough):** `src/premura/skills/parser-generator/SKILL.md` — installable via `premura install-skills`, which copies the skill into `./.claude/skills/` in the current project root.
- **General development guide:** `CONTRIBUTING.md`
- **Four-stage data flow:** `docs/building/STAGES.md` — Ingest (parsers) → Engine → MCP → UI. Each stage's importable Python package documents its layering rule in its `__init__.py` docstring (notably: Stage 3 MCP never reads `hp.fact_measurement` directly; Stage 4 UI never reads it or calls the engine directly).
- **Warehouse update policy:** `src/premura/store/UPDATE_STRATEGY.md` — the six update kinds and which ones the current architecture handles versus defers.

If `CONTRACT.md` ever disagrees with this file, `CONTRACT.md` wins.

## Stage naming (final)

The four stages are `parsers`, `engine`, `mcp`, `ui`. Stage 4 is `ui/`, not `learn/` — an earlier draft used `learn`; that name is dead. Do not reintroduce it.

## Canonical vocabulary policy

The policy above is defined now. **Renaming the legacy v1 `metric_id`s to the final canonical vocabulary is deferred** to a later mission and will happen via a **full rebuild from raw inputs**, not an in-place metric-id rewrite migration. New parsers and ontology rows added today follow the policy; existing rows are left in place.

## Stool ecology and microbiome-style reports

Stool reports often mix standard clinical chemistry, pathogen microbiology, and
commercial ecology/taxonomic profiling in one table. Apply the standards-first
rule per field, not per report:

1. **Standard stool chemistry stays `lab:stool_*`.** If LOINC has a stool analyte
   with the same property/system/scale, use or add the corresponding
   `lab:stool_*` row. Examples from LOINC include calprotectin `[Mass/mass] in
   Stool` (`38445-3`), pancreatic elastase `[Mass/mass] in Stool` (`25907-7`),
   alpha-1-antitrypsin `[Mass/volume] in Stool` (`9407-8`), fecal fat
   mass-content/mass-concentration terms, and reducing substances in stool.
2. **Pathogen presence/culture findings are clinical microbiology.** A named
   organism may get a canonical lab row only when the source result is a
   presence/threshold/culture/antigen/PCR-style clinical finding and a matching
   LOINC-style organism/test exists. Preserve the organism, method, and scale;
   do not collapse pathogen-specific findings into a generic stool culture row
   unless the source itself reports only a generic culture outcome.
3. **Commercial ecology abundance is not automatically `lab:stool_*`.** Genus or
   species abundance rows such as commensal bacteria/fungi, flora balance,
   “good/bad” organism groups, alpha/beta diversity, and taxonomic profiling
   scores are microbiome/taxonomic-profile observations. If Premura has no
   microbiome domain yet, leave them in `unmapped_metrics` or propose a
   `vendor:<source>:<field>` metric with a PR note. Do not create dozens of
   `lab:stool_<organism>` metrics from one vendor's ecology scale.
4. **Reported ratios are observations only if the lab reported them.** A ratio
   printed in the source can be stored as an observed lab/vendor result with
   provenance. A ratio computed by Premura belongs to `derived:*`, which parsers
   must not emit.
5. **Qualitative stool descriptors need an explicit home.** Color, consistency,
   Bristol type, and similar descriptors are useful only when their scale is
   clear. Prefer an existing standard row; otherwise surface them as unmapped or
   a vendor metric rather than encoding free-text report categories as aliases.

This keeps established stool lab markers ingestible while preventing a single
commercial stool-ecology export from polluting the global lab ontology.

## Federated vs. core

- **Federated (PRs welcome):** new parsers under `src/premura/parsers/` plus the matching `dim_metric.yaml` rows, governed by this file and `src/premura/parsers/CONTRACT.md`.
- **Core (this repo's maintainers):** engine signal functions, MCP wiring, UI flow. Those layers are not federated work.
