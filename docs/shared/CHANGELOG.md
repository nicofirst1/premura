# premura — Changelog

> Status: append-only history. One entry per mission (or comparable unit of
> work), newest first, written when the work merges and **never edited
> afterward** — corrections get their own entry. The current-state snapshot
> (counts, tables, what works today) lives in [STATUS.md](STATUS.md); this file
> holds the narratives. When a mission lands: add an entry here, then rewrite
> the affected STATUS.md lines (STATUS has a hard line cap enforced by
> `tests/test_docs_structure.py`).

## 2026-07-02 — Withings CSV parser: first real observation-seam vendor (#33, M4)

Phase 4's named candidate lands: a `PluginParser` for Withings' "Download
your data" CSV export (`--source withings`), proving the federated parser
ecosystem on the **observation** seam the way the MyFitnessPal intake parser
proved it on the intake seam.

- **`src/premura/parsers/withings.py`**: reads the zip-of-per-category-CSVs
  Withings export (`weight.csv`, `bp.csv`, `raw_tracker_hr.csv`,
  `aggregates_steps.csv`, `sleep.csv`; member routing + `preview_routing`
  mirror `garmin_gdpr.py`'s pattern). Weight, blood pressure, heart rate,
  steps, and sleep session/deep-% all reuse **existing** `dim_metric.yaml`
  metric_ids (decision-tree step 1) — no new rows needed for the FR-1 core
  set. Two new ontology rows were added for fields with no existing home:
  `fat_mass` (step 4, bare English canonical — a reusable cross-vendor
  body-composition concept) and `vendor:withings:pulse_wave_velocity` (step
  5, vendor fallback — Withings BPM Core-specific). The structural
  `weight.Category` field is declared via `unmapped_metrics`; malformed cells
  become `skipped_rows` with a reason; blank cells are left unknown rather
  than fabricated as zero.
- **Cross-source dedupe priority**: `withings` ranks between `garmin_gdpr`
  and `health_connect` (`SOURCE_PRIORITY["withings"] = 90`) — Withings' scale
  and BPM Core cuff are calibrated instruments that generally beat
  wrist-wearable estimates for weight/body-composition/BP and match a
  dedicated tracker for steps/HR/sleep, but Garmin's continuous wearable
  telemetry still outranks it.
  No live Withings export was available to validate against; this is the
  parser's documented contract surface built from public export
  documentation ("real vendor *format*, synthetic *data*" per the issue) — a
  real-export validation pass is separate follow-up work, `ready-for-human`.
- **Synthetic fixture**: `tests/fixtures/parsers/withings/` — the CSV content
  lives in the committed, text-only `csv_content.py` (single source of
  truth) and covers every spec-named edge case — happy path, blank cell,
  malformed cell, the vendor fallback, and the bare-English addition — end to
  end. `build_fixture.py` materializes it as a **local-only, gitignored**
  `.zip` (this repo's `.gitignore` excludes `*.zip` repo-wide and
  `ops/check_no_tracked_data.sh` documents "synthetic test fixtures are text
  formats ... and never match these patterns" — a finding worth recording:
  the issue's acceptance `<fixture>` path is generated on demand from
  committed text, not itself committed as a binary).
- **Real e2e exercise** (against a locally-built fixture zip):
  `hpipe ingest --source withings <fixture>` (37 rows inserted) → re-ingest
  (0 inserted, sha256 skip) → `hpipe inspect <fixture>` (5/5 members routed)
  → `hpipe status` → `weight_trend` through the MCP surface returned
  `status: available`, `trend_direction: flat` with honest
  carried-forward/gap caveats over the fixture data.

## 2026-06-12 — Operating-roles slice 2: PubMed citation binding

The first of the two named slice-2 items from `OPERATING_ROLES.md` (the
other, claim-to-trace binding, stays named later work pending its own
decision note): the answer-audit gate now deterministically verifies that
every PMID a draft cites was actually fetched in the named session —
"candidates are never citeable" is enforced at audit time, not just stated
at the tool layer.

- **Evidence-source trace recording** (migration 008, `call_kind` on
  `trace.tool_call`): `pubmed_search` / `pubmed_fetch` accept an optional
  `session_id` and record through the exact record → dispatch → finalize
  seam the analytical tools use, as `call_kind = evidence_source` rows.
  The multiplicity disclosure (raw, N, refusal breakdown, call list) counts
  `analytical` rows only, so "N unique hypotheses examined" stays
  uncontaminated by literature lookups; `mark_surfaced` refuses evidence
  rows so K cannot leak either. Provider outcomes map honestly: only an
  `available` fetch records terminal `available`; `provider_error` is an
  `error` row; `no_results` / `invalid_pmid` / `unavailable` are `refused`
  rows that never become citeable. Untraced PubMed calls (no `session_id`)
  are byte-identical to before.
- **Citation binding in the gate** (check 5 in `OPERATING_ROLES.md`):
  `answer_audit` extracts cited PMIDs under a fixed documented contract
  (`PMID`/`PMIDs`/`PubMed ID` textual markers with number lists, plus both
  PubMed record-URL hosts) and fails the verdict unless each has a
  successful in-session `pubmed_fetch`
  (`premura.trace.fetched_citation_pmids`, read back from the recorded
  hypothesis identity so recording and audit cannot drift). Extraction is
  deliberately generous because over-extraction fails closed. The measured
  disclosure carries a self-scoping citation line either way ("citations:
  none in the recognized PMID forms" / "K cited PMID(s) (recognized forms),
  all fetched this session" — it never claims "none cited" outright), and
  the verdict reports `cited_pmids`. A draft citing PMIDs without naming a
  session fails with a citation-specific reason. Out-of-form citations are
  invisible to the gate AND uncovered by the v1 advisory rubric (its
  categories are closed); the runtime contract's cite-in-recognized-form
  obligation carries that gap, and a rubric citation criterion is named
  follow-up work in the spec.
- The audit-consumer Call Record gains the additive `call_kind` field
  (contract doc updated). Pinned by `tests/test_operating_roles_slice2.py`
  (kind storage and backfill, disclosure exclusion, the citeable set, the
  extraction contract, gate pass/fail paths, and the full
  fetch → audit → envelope flow through the real MCP surface).

## 2026-06-12 — Condition-episode persistence (roadmap item 2)

The named-deferred follow-up from the analytical-tool work: operator-declared
condition episodes now have a warehouse home, so off/on questions stop
re-declaring episodes per request.

- **One home** (migration 007, `hp.condition_episode` + store boundary
  `premura.store.condition_episodes`): a row is the operator's *assertion on a
  date* — the label stays operator vocabulary (any non-empty string, never an
  enum, never a verified condition). Same honesty kit as profile capture:
  corrections **supersede** with full history, withdrawals **retract** with a
  reason, nothing is overwritten or deleted. The *current* set per label is
  kept non-overlapping at the store boundary (a conflicting declaration is a
  structured rejection pointing at supersede/retract), so the stored set is
  always analyzable. `end_day` may be omitted (ongoing) for record-keeping;
  ongoing episodes never enter the analysis read path.
- **Three capture tools** on the default MCP surface (now twenty-six tools —
  see STATUS §"MCP surfaces"): `condition_episode_record` /
  `condition_episode_list` / `condition_episode_retract`, thin wrappers in the
  profile-capture posture (structured `rejected` responses, capture-session
  provenance, `source_kind=agent_condition_capture`).
- **Consumption seam:** `condition_paired_t_test`'s `episodes` parameter is
  now optional at the MCP boundary. Omitted, the wrapper loads the stored
  current closed episodes for the label and builds the **same pre-registered
  engine request** — the envelope is byte-identical to declaring the same set
  by hand (locked by test), plus a wrapper-layer `episodes_source` disclosure
  naming the episode ids used. The stored set resolves *before* the research
  trace records the hypothesis, so the trace identity carries the actual
  episode set. An empty stored set flows into the normal too-few-episodes
  refusal. **The engine stayed stateless and untouched** — episodes are never
  auto-detected, and the label still only splits windows, never names a cause.

Mission ran in the frontier-window mode: confirmed mini-spec, direct
implementation, independent subagent review, and a real end-to-end exercise on
a sandboxed warehouse (record via MCP → analyze without re-declaring →
parity + disclosure verified).

## 2026-06-12 — AI-chat supplement/medication recall source (#23)

A second intake source, and the first whose "vendor" is an AI assistant: one
documented JSON interchange contract
([`AI_CHAT_RECALL_CONTRACT.md`](../building/architecture/AI_CHAT_RECALL_CONTRACT.md),
format `premura.ai_chat_recall.v1`) that any assistant's paste-prompt can
target, plus the intake-only parser consuming it through the federated seam
(`hpipe ingest --source aichat`, inbox autodiscovery via a document-shape +
marker sniff). Paste-prompts are derived artifacts — the contract states the
derivation rules and ships one reference prompt (Claude.ai); no assistant
list anywhere, and each export's `assistant` becomes its own provenance
source `ai_chat_recall:<slug>` without a registry edit.

The real work was the two honesty decisions the contract settles:

- **Fuzzy time.** `since` carries an explicit precision (`day`/`month`/`year`)
  whose date *shape* must match (strictly, zero-padded — lenient parsing
  would let `"2026-3"` vs `"2026-03"` re-exports become two inventory rows);
  a mismatch is a fabricated-precision contradiction and skips with a reason.
  Events anchor at the period's earliest instant; the declared precision and
  the chat's own wording persist in `raw_payload` (no schema migration).
  Missing `since` anchors at `exported_on` as precision `"unknown"`.
- **Provenance grade.** Everything lands under `source_kind=ai_chat_recall`
  — an AI's recollection of what the user told another AI — never mixed with
  app-logged intake. A verbatim `quote` is mandatory per entry (skipped
  otherwise); one event per recalled item, daily events never synthesized.
  The contract states this source answers *inventory* questions only, not
  adherence.

Mission ran in the frontier-window mode (no spec-kitty): confirmed mini-spec,
direct implementation, independent subagent review (PASS-WITH-NOTES; its
should-fix findings — prompt-text/fenced-reply misrouting of `ingest --source
all`, lenient date shapes destabilizing dedupe — were fixed pre-merge), and a
real end-to-end exercise: a live model roleplayed the assistant over a
synthetic chat history and its verbatim JSON went inbox → parser → warehouse,
idempotent on re-ingest. That exercise caught a contract gap reviews didn't:
assistants resolve "two weeks ago" into fake day-precision dates by
arithmetic, so the derivation rules now forbid it explicitly. Recalled-intake
duplication (the source class's own failure mode) skips with a reason instead
of failing the batch.

## 2026-06-12 — Tool-loop fixes from the first full-stack trial (#25, #26 + allowlist)

The first full-stack live trial (audit:
[`2026-06-12-v040-first-full-stack-live-trial.md`](../history/audits/2026-06-12-v040-first-full-stack-live-trial.md))
found the tool-loop tier unusable with its own default model family; the
highest-leverage defects are fixed:

- **#25 — content-borne tool calls are now recovered.** The `qwen2.5-coder`
  family writes tool calls as JSON in the assistant *content* (fenced or
  bare), never the chat API's native `tool_calls` field; the loop silently
  treated every such turn as a working-phase end, so the model executed zero
  tools. A bounded, format-level recovery rule (`_content_tool_calls` — any
  unambiguous call shape, never a per-model branch) now normalizes those to
  the native shape and dispatches them. Plain prose still ends the working
  phase; the recorded transcript keeps the assistant content verbatim. A
  ``json``-labeled fence that yields NO recoverable call (one bad escape in
  the call JSON was enough, per the verification trial) is a *malformed* call
  — corrective message, turn consumed (contract §3) — never a silent
  working-phase end.
- **#26 — absent-parser gate rounds now feed actionable guidance.** Ending
  the working phase with no parser ever written used to feed back the
  harness's own internal `ModuleNotFoundError` traceback verbatim; the loop
  now short-circuits to a synthesized failure telling the model to use
  `write_parser`, with honest empty self-reconcile telemetry.
- **`read_context` no longer refuses its own allowlist.** A bare relative
  request (`"qelband.csv"` — the exact form the brief and the refusal message
  advertise) resolved against the harness process CWD and never matched the
  absolute allowlist, so the tool refused the very names its own refusal
  listed and the operator authored blind. Found on the post-#25 re-run, where
  the 14B finally executed tools. A bare allowlisted *name* now resolves by
  name; full resolved-path matching, and every refusal bound (manifest,
  escape, traversal, directory-qualified relative), are unchanged.

The first two fixes are inside the loop module (`live_trial_tool_loop.py`),
the third in the `read_context` handler (`tool_loop_contract.py`); the gate,
grading, persistence, and one-shot tier are untouched.

## 2026-06-12 — Correction: the tool-loop tier had already merged 2026-06-11

The entry below (and the 2026-06-11 tool-loop entry's header) carried stale
framing: `tool-loop-live-trial-tier-01KTVG26` did **not** "remain genuinely
unmerged" — it squash-merged to master 2026-06-11 21:22 (`7d2c6a3`), before
the overnight release candidate was even built on top of it. The overnight
missions inherited the stale "in progress, not yet merged" STATUS/ROADMAP
lines and the post-merge reconciliation propagated them. STATUS and ROADMAP
now read merged-2026-06-11; per the never-edit-after rule the wrong entries
stay verbatim and this entry is the correction.

## 2026-06-12 — `v0.4.0` merged to `master` and tagged — release candidate accepted

Closes the loop the rc entry below opened (that entry and the seven mission
entries stay verbatim per the never-edit-after rule; this entry is the
correction-style follow-up recording what happened to them). The consolidated
review the candidate was waiting on ran as seven parallel per-mission
spec→code→test reviews plus a cross-mission seam pass — full record in
[`docs/history/audits/2026-06-12-overnight-release-candidate-pre-merge-review.md`](../history/audits/2026-06-12-overnight-release-candidate-pre-merge-review.md).

- **Verdict: zero blockers.** All seven missions PASS (four with nit-grade or
  deferred-by-design concerns). The cross-mission targets checked out: the
  six-tool reconciliation is complete on every authoritative surface, the
  m3→m4 judgment seam matches field-by-field, migration 006 is idempotent
  with all ~9 in-memory `Interval.unit` call sites cleaned, and the judge /
  improvement hook safety defaults (OFF, verdict-isolated) hold.
- **Two doc-truth fixes landed on the branch before merge:** the
  `analytical-claims-match-engine` rubric grounding claimed a dossier field
  that does not exist (engine results reach the judge only as tool-result
  turn content; `rubric_version` → `2026-06-12.2`), and the `log_turn`
  schema comment said `step_id` is "NOT a hard FK" while the DDL declares an
  enforced `REFERENCES`.
- **Merge + tag.** `overnight/release-candidate` merged to `master` (no-ff)
  and tagged `v0.4.0`; live docs (STATUS, ROADMAP) reconciled post-merge from
  "on branch, not yet merged" to merged-in-`v0.4.0` framing. The
  `tool-loop-live-trial-tier-01KTVG26` mission remains genuinely unmerged and
  keeps its in-progress framing.

## 2026-06-12 — Release candidate `v0.4.0-rc.1` — seven overnight missions consolidated — on `overnight/release-candidate`, awaiting review + tag

Release-prep meta-entry (this is the comparable-unit-of-work the header allows; it
adds, it does not rewrite the seven mission entries below — those stay verbatim per
the never-edit-after rule and keep their own "on branch, not yet merged" framing
until each lands on master). The night's seven feature missions (m2–m8) were
collected onto `overnight/release-candidate` for a single whole-night review and a
single tag. The orchestrator cuts the tag after review; this branch does not touch
`master` and creates no tag.

- **What the candidate carries (m2–m8, each narrated in its own entry below).**
  m2 conversation-turn capture (`log_turn`), m3 judge AI (`log_judgment` + dossier +
  versioned rubric), m4 improvement hook (`log_improvement` + versioned playbook),
  m5 synthetic fixture auto-generator, m6 analyze-and-answer task kind, m7 small
  follow-ups (`hpipe inspect`, `hpipe gc --dry-run`/`--raw`, `fact_interval.unit`
  migration 006), and m8 `condition_paired_t_test` (the sixth analytical tool).
- **Version reasoning → `v0.4.0`.** `v0.3.0` was already tagged 2026-06-01 at the
  finish-analytical-tool-set mission, and pyproject still read `0.3.0` (now an
  already-consumed version). The seven missions are all additive, backward-compatible
  feature work landing after that tag, so under the project's `v0.x.0` line this is
  the next minor: `0.4.0`. `pyproject.toml` is bumped `0.3.0 → 0.4.0` so the
  package metadata (`premura.__version__`, sourced from metadata) matches the tag the
  orchestrator will cut. `v1.0.0` stays reserved for the user-facing threshold.
- **Whole-night doc reconciliation.** Each mission synced STATUS/ROADMAP pre-merge
  from its own viewpoint; this pass fixed the cross-WP drift that survived the gaps:
  the `register_hypothesis_identity` docstring in `src/premura/trace.py` still listed
  five built-ins (now six), and `STAGES.md` (authoritative) plus
  `FULL_APP_DEVELOPMENT_PLAN.md` (authoritative, live Phase-3 status) still said
  "five analytical tools" / "returns exactly these five" and described condition-label
  pairing as deferred — all corrected to six with `condition_paired_t_test`. STATUS.md,
  ROADMAP.md, and the engine CONTRACT.md were already at six (synced by m8) and were
  left as-is.

## 2026-06-12 — Condition-label pairing (`paired-t-condition-pairing`) — on branch, not yet merged

Written pre-merge (overnight solo mission on
`overnight/m8-paired-t-condition-pairing`). Ships the reviewed **condition-label
pairing** extension the engine CONTRACT's deferred-extension rule prescribed, as
the sixth analytical tool — `paired_t_test` and `paired_inputs` are byte-for-byte
unchanged.

- **New tool `condition_paired_t_test`.** Reports a declared **off-vs-on** paired
  difference over one operator-declared condition *label* (any non-empty string,
  never an enum) and a set of non-overlapping declared **episodes**. The one fixed
  rule: each usable episode contributes one pair — off = mean of usable off-window
  observations outside every declared episode; on = mean of usable on-window
  observations truncated at `after_days`/the episode end; difference = on − off. The
  estimate is the mean of the per-episode differences with a descriptive dispersion
  band. The paired unit is the episode; the floor is two usable episodes.
- **Honesty boundary unchanged.** No p-value, no "significant", no cause — the label
  only splits the windows. Per-episode exclusions (before-window contamination,
  empty windows) are disclosed, never silently salvaged. Constant differences,
  too-few/overlapping episodes, scan requests, and inadmissible/stale series refuse
  with a distinct reason and no estimate.
- **Contract + seam + surface.** New `AnalyticalQuestionType.CONDITION_PAIRED_DIFFERENCE`
  and its policy twin (declared for exactly the families that allow anchor-date
  pairing today; no new family judgments); new `condition_inputs` preparation seam;
  the tool on the default + operator MCP surface; a thin delegating wrapper; and the
  tool's own normalized trace-identity (metric, label, episode set, windows,
  direction) registered for the session research trace.
- **Named-deferred:** warehouse storage of condition periods, multi-label contrasts,
  episode auto-detection, any scanning — recorded in ROADMAP.

## 2026-06-12 — Small follow-ups (`small-follow-ups`) — on branch, not yet merged

Written pre-merge (overnight solo mission on `overnight/m7-small-follow-ups`); the
post-merge close-out flips tense and records the merge. Three small, independent
roadmap items that close known gaps in the operating surface — they share no code,
so they shipped as three work packages on one branch.

- **`hp.fact_interval.unit` column (WP3).** STATUS called out "`fact_interval` has
  no `unit` column; carried in memory only" — and in fact the in-memory
  `Interval.unit` was *already dropped silently* in `dedupe._interval_frame`, so
  parser-supplied unit strings never reached the warehouse. Migration
  `006_interval_unit.sql` (003 was taken) adds a nullable `unit VARCHAR` with an
  idempotent backfill from `dim_metric.canonical_unit`, and the interval load path
  populates `unit` for new rows by joining to `dim_metric` — the metric registry is
  the **single source of unit truth, never a parser string**. The dead in-memory
  `Interval.unit` field is removed from the dataclass, the dedupe plumbing, and all
  nine parser construction sites.
- **`hpipe inspect <path>` (WP1).** A read-only routing-preview verb — the twin of
  `ingest` discovery. It resolves the parser for a path with the **same** routing
  primitives `ingest` uses (no second routing table), enumerates archive/file member
  names without reading their contents, and prints per-member routing plus an
  "N routed, M unhandled" summary. Routing preview is a **structural parser
  capability** (`preview_routing(member_names) -> RoutingPreview`, discovered by
  `hasattr`/Protocol — not a Garmin if-ladder); the Garmin parser implements it by
  delegating to its existing `_HANDLERS` dispatch so the preview can never drift from
  ingest. A parser lacking the capability is reported honestly (exit 0, names the rule
  for adding it). `inspect` opens no warehouse and writes nothing.
- **`hpipe gc` raw pruning + `--dry-run` (WP2).** gc applies one mtime cutoff to N
  roots: exports always, and `data/raw/` only with the opt-in `--raw` flag (files AND
  directories). `--dry-run` previews exactly what would be removed and removes nothing
  from either root. **Decision (recorded here per FR-2.3):** `--raw` defaults OFF
  because `run_monthly()` calls `gc(keep=3)` unattended; silently flipping it to delete
  staged source artifacts — for un-exported files the only local copy — is a human
  choice, not an overnight one. `run_monthly`'s behavior is unchanged.

## 2026-06-12 — Analyze-and-answer slice (`analyze-and-answer`) — on branch, not yet merged

Written pre-merge (overnight solo mission on `overnight/m6-analyze-and-answer`);
the post-merge close-out flips tense and records the merge. The acceptance harness
graded exactly one task shape — "build an honest parser." The product's real
end-to-end promise is "here's my data → load it → analyze it → answer my question,"
and nothing exercised or audited the second half. This mission teaches the harness a
**second task kind**: given a deterministically seeded synthetic warehouse and a
question, an operator must reach the data **only through the engine's analytical
surfaces** and return an answer a deterministic grader can verify for honesty and
grounding. Everything is captured in the session log through the existing
sole-writer surfaces, so the exchange is judged and improvable like a parser session.

- **Contract + deterministic grader (`premura.harness.answer_task`).** A
  `QuestionSpec` declares which registered engine analytical surface a question-kind
  calls and with what canonical parameters, renders the human question, and selects
  its metric **deterministically from the seed** out of the policy-covered,
  `dim_metric`-resident, analyzable metrics — never a metric id hardcoded in code.
  `AnswerOutcome` carries the final answer text, the claimed estimates as
  **structured** values, and tool-call provenance; a refusing operator carries a
  structured refusal instead. `grade_answer` **recomputes ground truth itself**
  through the same engine surface (a poisoned tool-call report cannot fool it) and
  bands three checks, each naming itself on failure: **honesty** (no forbidden
  statistical claim in the answer text — driven by a forbidden-claims pattern
  registry sourced from the engine contract's prohibitions: "significant"/
  significance, p-values, causal language, population-norm comparisons),
  **grounding** (claimed structured estimates match the recomputation within the
  kind's tolerance — never numbers parsed out of prose), and **refusal fidelity**
  (only a refusal mirroring the engine's refusal passes; a refusal where the engine
  computed a result fails).
- **A level above (guide, don't enumerate).** Question kinds and forbidden-claim
  patterns are registries with documented add rules; the core never branches on a
  kind id, there is no enumerated question list and no hardcoded metric id, and an
  unknown kind fails loudly. Tonight exactly one kind ships — `level_shift` over the
  `change_point` analytical tool.
- **Seam + capture (`premura.harness.answer_trial`).** `run_answer_trial` seeds a
  synthetic warehouse deterministically (synthetic by construction — fabricated
  source, invented values, a registry metric), hands the operator a **bounded
  analytical surface** wrapping the engine's registered analytical surfaces over that
  warehouse (the operator never receives a connection, path, or raw SQL), collects
  and grades the answer, captures the question + answer exchange through the existing
  sole-writer session-log surfaces (`open_session` / `record_step` / `record_turn` /
  `finish_session`, no schema change), so `build_dossier` shows it, and appends one
  scoreboard line under the existing **open tier axis** with the `analyze_answer`
  tier value, marked synthetic. `AnswerOperator` is a small protocol; the mission
  ships a scripted **honest** reference operator (drives the real surface, answers
  from its results, mirrors a refusal honestly) and a scripted **dishonest** contrast
  operator (fabricates estimates and/or emits forbidden claims). End-to-end tests
  cover the honest pass and all four spec-named edge cases.
- **Rubric + playbook extension by their own rules.** `JUDGE_RUBRIC.md` gains an
  analytical-honesty criterion (`analytical-claims-match-engine`) under the existing
  closed `process_honesty` category with a `rubric_version` bump, and
  `IMPROVEMENT_PLAYBOOK.md`'s `process_honesty` area is extended to cover analytical
  honesty with a `playbook_version` bump. Because criterion/area semantics are
  document-owned and never appear in code, this required **no engine, judge, or scan
  code edit** — a test confirms the rubric/playbook parsers accept the extended
  documents unchanged and the new criterion maps to an existing area.
- **CLI.** `python -m premura.harness.answer_task --seed N [--question-kind K]` runs
  the offline trial end to end with the scripted honest operator against a temp
  sandbox, prints a one-line summary (kind, metric, verdict with per-check results),
  and exits nonzero on any failed check — mirroring the m5 CLI pattern.
- **Deferred, named so it is not assumed shipped:** the real-model (Ollama) analyze
  operator and its prompt/tool-loop work, cross-session trend aggregation, MCP
  exposure of the session log, multi-turn / multi-question sessions, natural-language
  question parsing, model-generated answer prose, and new analytical tools in the
  engine.
- With the new task never invoked, the existing parser-trial and session-log tests
  pass unchanged; the sole-writer invariant, the NFR-005 live-trial gate guard, the
  no-new-dependency scan, and the engine guards are untouched.

## 2026-06-12 — Fixture auto-generator (`fixture-auto-generator`) — on branch, not yet merged

Written pre-merge (overnight solo mission on
`overnight/m5-fixture-auto-generator`); the post-merge close-out flips tense and
records the merge. The acceptance harness grades whether a model can build an
honest parser for an **unfamiliar** vendor export, but it owned exactly two
handwritten fixtures — a model under trial could simply have memorized
Fitbit-shaped exports, and two challenges cannot exercise the contract's breadth.
This mission adds a deterministic, seeded, offline generator that fabricates fresh,
never-seen synthetic vendor fixtures — a CSV plus its grader-only ground-truth
manifest — on demand, so the harness can always present a genuinely unfamiliar
source. Synthetic only: fabricated source names, invented values, canonical
metrics drawn from the committed registry — never derived from a real export.

- **Deterministic generation core.** `premura.harness.fixture_gen.generate_fixture(
  spec)` is pure and offline: every random choice flows from
  `random.Random(spec.seed)`, so the same `FixtureSpec` yields byte-identical CSV
  and manifest text on every run, on every machine. No model calls, no clock reads,
  no network, no reads of any operator data path. The generated observation fixture
  is a fair challenge by construction: a structural timestamp column in a
  seed-chosen encoding (ISO 8601 / epoch seconds / epoch microseconds), one or more
  mappable columns whose **distinct** canonical metrics are drawn from the committed
  metric registry at generation time (the grader's D6 distinct-metric rule), and at
  least one declared-gap decoy column with no canonical home (the honesty decoy). A
  mapped column's vendor-weird header is derived from a fabricated vendor token, not
  from the canonical metric id, so the header never leaks the answer — the canonical
  metric lives only in the grader-only manifest.
- **A level above, three registries.** Drawer behaviour, vendor-weird column-name
  weirdness, and timestamp encodings are each a small registry with its add rule
  documented where it lives (NFR-4): a **drawer-strategy** registry keyed by drawer
  id (only `observation` ships tonight; an unknown drawer id fails loudly, and
  adding `intake` later needs no core edit), a **naming-transform** registry, and a
  **timestamp-encoding** registry. No vendor `if/elif` ladders; no metric list
  hardcoded in code — metrics come from the registry seed.
- **Validation, writer, scenario adapter.** `validate_fixture` enforces the
  ground-truth invariants (every CSV column enumerated exactly once; canonical
  metrics unique and registry-resident; ≥1 mappable and ≥1 declared-gap column;
  exactly `row_count` rows, all timestamps decodable in the declared encoding) and
  runs before `generate_fixture` returns, so an invalid fixture can never escape.
  `write_fixture` writes the pair (refusing to overwrite unless told) plus an
  explicit, writer-controlled **synthetic marker**, and `scenario_for` adapts a
  written pair into a `Scenario` the existing harness accepts unchanged — graded by
  the same `ObservationStrategy` as the committed fixture. The generated manifest
  matches the committed observation manifest shape exactly (it carries the
  GRADER-ONLY header and reads through the same YAML loader), so grader/manifest
  consumers need no changes.
- **Synthetic recognition without loosening the rule.** The harness's real
  persistence gate — `live_trial_ollama.is_synthetic_source`, the function the trial
  loop calls to decide scoreboard persistence — now also recognizes a generated
  fixture as synthetic by delegating to the writer-controlled marker beside its CSV
  (`fixture_gen.is_generated_synthetic_source`), so a generated source persists to
  the scoreboard. This is **additive**: it does not loosen the committed-source
  rule, so an arbitrary or real-looking marker-less operator path stays non-synthetic
  (pinned by an integrated test that routes a generated source through the gate while
  a marker-less path stays non-synthetic and the committed sources stay synthetic).
  Generated output lands only
  where the caller points `--out`, never silently into `tests/fixtures/`; with the
  generator never invoked, every existing fixture and live-trial test is byte-for-byte
  unaffected.
- **CLI.** `python -m premura.harness.fixture_gen --seed N [--drawer observation]
  [--out DIR] [--rows K] [--overwrite]` generates, validates, writes, and prints the
  written paths plus a one-line summary (drawer, source name, column count,
  mappable/gap split, encoding); exit code is nonzero on any failure. Mirrors
  `live_trial_ollama`'s `_main()`. All new tests run in the default offline suite;
  no new third-party dependency.

Mission detail:
[`docs/building/planning/fixture-auto-generator.md`](../building/planning/fixture-auto-generator.md).

## 2026-06-12 — Improvement hook (`improvement-hook`) — on branch, not yet merged

Written pre-merge (overnight solo mission on `overnight/m4-improvement-hook`); the
post-merge close-out flips tense and records the merge. The judge AI (m3) writes a
structured verdict into `log_judgment`, but nothing consumed it: a weak band or a
failed judgment was recorded and then ignored. This mission closes that loop one
step — it turns judgments into durable, agent-readable **improvement proposals**
("the operator keeps failing `economical-tool-use`; review the prompt's tool
guidance") so a maintainer agent or the human can decide what to change. The hook
**proposes; it never acts**: it does not edit prompts, harness code, rubrics, or
skills, and it never changes a run's verdict.

- **Improvement store surface (`log_improvement`).** A new additive
  `log_improvement` table plus `record_improvement(...)` and one closed vocabulary
  validated at the store boundary like the existing ones: `PROPOSAL_STATUSES`
  (`{open, dismissed, addressed}`). The store rejects an out-of-vocabulary status,
  a blank `summary`/`evidence`/`area`, or a dangling session/judgment reference.
  `criterion_id` is nullable and opaque (rubric-owned data, NULL for judgment-level
  proposals); `area` is **playbook-owned data, never enumerated in code**. This
  mission only ever writes `"open"`; the other statuses exist now so a later
  lifecycle mission needs no schema migration. The schema change is `CREATE TABLE
  IF NOT EXISTS`, so `init_schema` stays idempotent against existing local files.
- **Read-only judgment + proposal surfaces.** A `premura.session_log.improvement_read`
  read surface with `read_judgments` (the scan's input) and `read_improvements`
  (filterable by session and/or status) returning frozen dataclass rows in
  deterministic order, opening the log **strictly read-only** (same discipline as
  the m3 dossier) so an agent lists open proposals through it, never via raw SQL,
  and the harness stays the sole writer.
- **Versioned playbook, a level above.** The hook's improvement areas live in a
  versioned `IMPROVEMENT_PLAYBOOK.md` packaged with the harness (mirrors
  `JUDGE_RUBRIC.md`'s shape) — one area per closed rubric category plus two
  hook-owned areas (`harness_reliability` for a non-`complete` judgment status,
  `rubric_drift` for a judged criterion the current rubric no longer defines), each
  with a `suggested_focus` review pointer and grounding — **plus the explicit rule
  for adding an area**: edit the doc and bump `playbook_version`; no schema or store
  change is ever needed. Code never hardcodes area semantics; it parses the doc and
  fails loudly if the version header or any required area is missing.
- **Deterministic scan core.** `premura.harness.improvement.scan_session(...)` reads
  a session's judgments through the read-only surface, looks up each judged
  criterion's category via the **reused** m3 rubric parser (extended to expose
  criterion→category — not a second parser), and derives proposals by rule: a
  criterion banded `weak` → one proposal in its category's area carrying the
  rationale as evidence; a non-`complete` judgment status → one `harness_reliability`
  proposal; a judged criterion absent from the current rubric → one `rubric_drift`
  proposal; `strong`/`adequate`/`not_applicable` produce nothing. Persistence is
  idempotent on `(judgment_id, criterion_id, area)`: a re-scan writes nothing new and
  reports each proposal as pre-existing. The scan is **pure and deterministic** — no
  model calls, no network, no randomness, no clock reads beyond row timestamps — and
  keys only on the closed store vocabularies + parsed doc structure (no
  `if criterion_id == ...` ladders).
- **Harness wiring, opt-in, default OFF.** The cheap-model live-trial run gains an
  opt-in post-run improvement step (`improve_run=False` by default) that runs after
  the judge has recorded its judgment. Like the judge step it is fully guarded:
  hook failure of any kind never changes the trial verdict and never raises out of
  the harness; it lands as proposals, or a logged warning. `improve_run` WITHOUT
  `judge_run` is a loud `ValueError` at entry — the hook has nothing to consume.
  Pinned by a regression test.
- **Containment unchanged.** Only the harness writes `log_improvement` (pinned by the
  single-writer test); the read surfaces open the log read-only; committed tests are
  fully offline and deterministic (synthetic judgments written through the store API,
  scripted judge transport); synthetic fixtures only; no new third-party dependency.

Mission detail:
[`docs/building/planning/improvement-hook.md`](../building/planning/improvement-hook.md).

## 2026-06-11 — Judge AI (`judge-ai`) — on branch, not yet merged

Written pre-merge (overnight solo mission on `overnight/m3-judge-ai`); the
post-merge close-out flips tense and records the merge. The live-trial harness
grades a run *mechanically* — the grader recomputes `contract_pass` from
warehouse facts and the scoreboard records pass/fail — but nothing evaluated the
operator's *process*: whether it worked toward the goal, used its tools
economically, recovered from failures, or claimed things the grader facts
contradict. The session log already held everything needed to judge that (steps,
provenance, per-attempt telemetry, and — since `conversation-turn-capture` — the
full transcript), but nothing read it. This mission adds an AI judge: a
harness-side evaluator that assembles a read-only dossier of a recorded session,
asks a **local** model to assess it against a bounded rubric, and persists the
structured judgment back through the same sole-writer surface.

- **Judgment store surface (`log_judgment`).** A new additive `log_judgment`
  table plus `record_judgment(...)` and two closed vocabularies validated at the
  store boundary like the existing ones: `JUDGMENT_STATUSES`
  (`{complete, unparseable, model_unavailable}`) and `CRITERION_BANDS`
  (`{strong, adequate, weak, not_applicable}`). `criteria` is a mapping of
  rubric criterion id → `{band, rationale}` stored as JSON; every band is
  validated, but the criterion **ids are rubric-owned data, never enumerated in
  code**. A judgment attempt is always recorded honestly — on
  `unparseable` / `model_unavailable` the criteria are empty, `overall_band` is
  NULL, and `raw_output` preserves what the model actually said. The bands are
  **descriptive only**: no numeric scores, no language confusable with the
  mechanical grader verdict. The schema change is `CREATE TABLE IF NOT EXISTS`,
  so `init_schema` stays idempotent against existing local files.
- **Read-only session dossier.** A `premura.session_log.dossier` read surface
  assembles one session into a judge-readable dossier — session metadata, the
  grader's recomputed facts (`contract_pass`, row counts), per-attempt
  telemetry, and the full transcript in `turn_index` order — opening the log
  **strictly read-only** so the judge (and the future improvement hook) never
  reach into tables ad hoc and never write the log. A session with no recorded
  turns says so explicitly rather than failing.
- **Bounded rubric, a level above.** The judge's criteria live in a versioned
  rubric document packaged with the harness (`JUDGE_RUBRIC.md`, precedent: the
  research-trace-audit skill's `AUDIT_RUBRIC.md`) with four **closed** criterion
  categories — process honesty, goal adherence, tool-use economy, failure
  recovery — **plus the explicit rule for adding a criterion**: edit the rubric
  (id, question, band grounding) and bump `rubric_version`; no schema or store
  change is ever needed. Code never enumerates the criteria; it validates bands
  and records whatever criterion ids the rubric defined.
- **Judge core.** `premura.harness.judge.judge_session(...)` builds the prompt
  from dossier + rubric, calls a local model through an injectable transport seam
  (same pattern as the tool-loop `Transport`; the default reuses the existing
  local-only Ollama path verbatim, so the PHI-bearing prompt can never leave the
  machine), parses and validates the verdict, retries a malformed response a
  bounded number of times, and persists exactly one `log_judgment` row per
  invocation with the honest status. The judge *evaluates* the grader's facts but
  can never alter them — `contract_pass`, the scoreboard, and the trial verdict
  are out of its write reach.
- **Harness wiring, opt-in, default OFF.** The cheap-model live-trial run gains an
  opt-in post-run judge step (`judge_run=False` by default) that runs after the
  final session is recorded. Judge failure of any kind — model unavailable,
  unparseable output, or a bug — never changes the trial verdict and never raises
  out of the harness; it lands as an honest `log_judgment` status row, or (if even
  recording fails) a logged warning. Pinned by a regression test.
- **Containment unchanged.** Only the harness writes `log_judgment` (pinned by the
  single-writer test); the dossier opens the log read-only; committed tests are
  fully offline with a scripted transport (any real-model test would carry the
  `live_trial` marker); synthetic fixtures only; no new third-party dependency.

Mission detail:
[`docs/building/planning/judge-ai.md`](../building/planning/judge-ai.md).

## 2026-06-11 — Conversation-turn capture (`conversation-turn-capture`) — on branch, not yet merged

Written pre-merge (overnight solo mission on
`overnight/m2-conversation-turn-capture`); the post-merge close-out flips tense
and records the merge. The session log already recorded the *shape* of a
live-trial run (the step tree, per-attempt telemetry); this mission persists the
*conversation* — the operator's actual chat history — so the deferred judge AI
has the turns to read. The transcript lived only in Python memory and was
discarded when a run ended; it is now flushed to the session log post-run by the
harness, which remains the **sole writer**.

- **Store surface (`log_turn`).** A new additive `log_turn` table plus
  `record_turn(...)` and a fixed `TURN_ROLES` vocabulary
  (`{system, user, assistant, tool}`, the chat-API role standard) validated at
  the store boundary like the existing `result_status` / `run_kind` vocabularies.
  `turn_index` is the 0-based transcript position; `(session_id, turn_index)` is
  unique; `step_id` is a nullable link to the `log_step` node the turn occurred
  under (the run's root `agent_turn`). `content` is full turn content — the
  session log is the local, PHI-bearing store per ADR 0011, and no code path
  syncs or exports it. The schema change is `CREATE TABLE IF NOT EXISTS`, so
  `init_schema` stays idempotent against existing local files.
- **Transcript seam (a level above).** The live-trial seam defines a structural
  `TurnLike` protocol and an optional operator capability: any operator that
  exposes `transcript()` after `operate()` gets its turns persisted by the
  harness. The harness detects the capability **structurally** (no registry of
  tiers, no per-tier capture code); operators without it behave exactly as
  before (zero `log_turn` rows, unchanged verdict). Capture failure on an
  otherwise-successful run surfaces as a recorded `error`-status step, never an
  exception that flips the run verdict.
- **Both tiers feed the seam.** The tool-loop operator maps its final chat
  history 1:1 to `TurnLike` items (roles pass through; tool-result turns carry
  their `tool_name`); the one-shot operator exposes its final prompt/response
  exchange as a two-turn (`user` prompt, `assistant` response) transcript — so
  the judge AI reads every tier through the same surface.
- **Containment unchanged.** Only the harness writes `log_turn` (pinned by the
  single-writer test); synthetic fixtures only, never real transcripts; no new
  third-party dependency.

Mission detail:
[`docs/building/planning/conversation-turn-capture.md`](../building/planning/conversation-turn-capture.md).

## 2026-06-11 — Tool-loop live-trial tier (`tool-loop-live-trial-tier-01KTVG26`) — in progress, not yet merged

Written pre-merge (this mission's own doc-sync work package runs before the
merge); the post-merge close-out flips tense and records the merge. The mission
adds a second, separately-scored way of running the cheap-model live trial: a
**multiturn, tool-using loop** over the same sandbox / ingest-runner / grader /
scoreboard machinery, recorded as its own tier (`tier="tool_loop"`) alongside —
never replacing — the constrained one-shot floor, so the maintainer agent can
compare "one constrained shot" vs "tools and turns" per operator model.

- **Corrected premise.** It implements the
  [2026-06-04 follow-up audit](../history/audits/2026-06-04-live-trial-tool-loop-14b-followup.md)'s
  reversal: the earlier spike measured **harness context quality**, not a model
  capability floor — a capable local model passes when handed one coherent
  brief. So this tier is context-plumbing hardening plus a headroom
  measurement above the floor, not a capability remedy.
- **Sharpened renamed-field declared-gap rule.** A source column the operator
  consumes to populate a renamed output field (e.g. a `timestamp` column
  consumed as the UTC timestamp) must be declared accounted or be an explicit
  gap; a consumed-but-undeclared column fails self-reconciliation. The rule is
  now stated explicitly in the contract text shown to the operator in both
  tiers and pinned by a fixture test.
- **Containment unchanged.** Local-only model endpoint, synthetic-only
  persistence (a run over real data records nothing), and the `live_trial`
  marker — the tier can never block CI.

Mission detail:
[`kitty-specs/tool-loop-live-trial-tier-01KTVG26/`](../../kitty-specs/tool-loop-live-trial-tier-01KTVG26/spec.md).

## 2026-06-11 — Tag hygiene: `v1.0.0` retagged as `v0.1.0` (audit R6)

The first local-ingest pipeline's restore point (commit `538aaf1`) was tagged
`v1.0.0` before the release-line policy settled on `v0.x` until the
user-facing threshold; that made a bare tag listing sort it as the latest
release. Retagged `v0.1.0` (the milestone number it actually was — annotated
tag records the rename) and the old `v1.0.0` deleted locally and on origin.
Earlier entries and history docs that say "tagged v1.0.0" describe what was
true when written. Also removed the last stale branch
(`docs/split-by-audience`, merged) from origin.

## 2026-06-11 — First real vendor intake parser: MyFitnessPal

The platform-meets-reality milestone the roadmap called for: the first *real*
vendor export adapted onto the intake path shipped by the
usable-intake-dimensions mission. `src/premura/parsers/myfitnesspal.py` reads
the official MyFitnessPal file export (zip of summary CSVs, or the bare
`Nutrition-Summary-*.csv`) and emits an **intake-only** `ParseOutput` — one
`NutritionIntakeInput` per (diary date, meal) row with event-level quantities
(`energy`, `protein`, `fat_*`, `carbohydrate`, …; 17 keys).

- **Two-seam discipline held.** Exercise-Summary (expended kcal — observation
  meaning, and typically synced *from* the wearable already ingested) is
  deliberately not emitted: ladder-resolving columns surface as `skipped_rows`
  with the double-count reason, homeless ones as `vendor:myfitnesspal:*`
  entries in `unmapped_metrics`. Nothing is dropped silently.
- **No invented data.** Empty cells are unknown (never zero); the four
  unit-unlabeled columns (vitamins/calcium/iron) carry `unit=None`; the bare
  diary date becomes a midnight timestamp with `local_tz=None`, so the
  resolver's UTC-day fallback reproduces the MyFitnessPal diary date verbatim.
- **Routing.** Registered as `hpipe ingest --source mfp`; inbox autodiscovery
  sniffs MFP zips (so the Garmin zip glob skips them) and MFP CSVs (so they no
  longer fall through to BMT).
- **Proven on real data (build-and-use, no review).** The operator's real
  export loaded 37 events; re-ingest is a clean no-op (37 dup-skips);
  `nutrition_intake_trend` answers `available` over the loaded window with
  gaps named, not filled. Tests are synthetic-only; no real rows enter the
  repo.

## 2026-06-11 — Docs restructure: CHANGELOG + slim STATUS, single-home facts

Issue #21 / audit §5. STATUS.md had become a changelog wearing a snapshot's
clothes (~500 lines, every mission appending a narrative section). This change:

- created this CHANGELOG.md and moved the per-mission narratives here verbatim;
- rewrote STATUS.md as a short, fully rewritable snapshot with a **hard line
  cap** pinned by `tests/test_docs_structure.py`;
- made STATUS.md the **single home** for shipped-state counts — STAGES.md,
  ROADMAP.md, and FULL_APP_DEVELOPMENT_PLAN.md now link instead of restating
  (the plan doc was already stale at "twenty tools");
- moved the **audit-consumer contract** to its live home
  `docs/building/architecture/AUDIT_CONSUMER_CONTRACT.md` (a pointer remains at
  the old `kitty-specs/.../contracts/` path) and reframed the
  `CORRELATE_METHODOLOGY_RESEARCH.md` citations so the operative statistical
  rules are normative in `src/premura/engine/CONTRACT.md` and the frozen
  research note holds the rationale;
- added the single-home rule to DOCTRINE.md's design self-checks.

## 2026-06-11 — Engineering safety net: CI, mypy burndown, data guard, doctor checks

Issues #16, #18, #19, #20, from the
[2026-06-10 software-development health audit](../history/audits/2026-06-10-software-development-health-audit.md).
Not a spec-kitty mission — direct, machine-verifiable ops hardening:

- **CI on every push/PR** (`.github/workflows/ci.yml`): `uv lock --check`,
  `ruff check`, `ruff format --check`, `mypy src/`, and the default pytest
  suite, all blocking, with `age` installed on the runner so the encrypt
  round-trip tests run instead of skipping.
- **All 13 mypy errors burned down** (`types-python-dateutil` stubs; explicit
  kwargs replace the type-defeating `**dict` unpacking in
  `health_connect.py`; guards in `garmin_gdpr.py` / `engine/_query.py`).
  `mypy src/` is clean and now a blocking gate.
- **Tracked-data guard** (`ops/check_no_tracked_data.sh`, in CI and
  pre-commit): no data-like file (`.duckdb` / `.db` / `.sqlite*` / `.age`,
  `data/`) can be tracked or staged. The one-time scan of full git history
  came back clean — no data-like path was ever committed.
- **`hpipe doctor` now proves the backup story**: the age key check reads the
  key (not just stats it), and a new `backup round-trip` check encrypts a probe
  with the recipients file and decrypts it with the on-disk key, so a
  rotated/mismatched pair fails loudly while both files still exist.

## 2026-06-04 — Usable intake dimensions (`usable-intake-dimensions-01KT950A`)

Mission #19, merged `4d9a12e`. Turned the two intake domains from
*storable-but-unreadable* into first-class, agent-usable dimensions. Before it,
`nutrition_intake` / `supplement_intake` had storage tables and a load path but
every declared dependency resolved to `unsupported_domain`, and there was no
parser path from a source export to `IntakeBatch`. All six work packages merged
and done. What it shipped:

- **Both intake domains resolve through the existing seam.** Concrete resolvers
  (`engine/views/nutrition_intake.py`, `engine/views/supplement_intake.py`) ride
  the same `@resolver(domain=...)` seam as observation/profile — no new
  abstraction layer, no per-domain branch in the shared resolution path (asserted
  structurally by `tests/test_intake_resolvers.py`). A "no matching row" case
  returns an explicit missing / stale outcome and **never** falls back to a
  same-named observation row.
- **Two new descriptive signals, on the default surface.**
  `supplement_intake_adherence` (family `status`) answers "logged on K of the
  last N days" for a caller-declared supplement matcher; `nutrition_intake_trend`
  (family `trend`) answers up/down/flat for a caller-declared nutrient/energy key
  and **never imputes** missing days. Both return the standard four-state
  envelope and are exposed as default-surface tools (taking that surface to
  twenty-two).
- **A real runtime intake-parser path.** The parser contract and the
  `parser-generator` skill were updated together so a runtime agent can
  **build-and-use** an intake parser (`parse → IntakeBatch → persist`) for the
  operator's own data with no review — the same build-and-use boundary settled
  for observation parsers. A minimal reference intake parser + synthetic fixture
  prove the path end-to-end (FR-007/008).
- **The generalization is written down, not just asserted.**
  `docs/building/architecture/INTAKE_DIMENSIONS.md` records the four
  domain-agnostic steps for making any declared intake dimension usable,
  validated by both shipped domains; the go/no-go on a dedicated
  intake-dimension contract (deliberately **not** built — constraint C-003) is
  reasoned in
  `docs/building/planning/intake-dimension-contract-recommendation.md`.

Still deferred after this mission: adapting a *specific real vendor export* (an
actual meal-logging or supplement-log file) — fill-in-the-blank parser work
against the documented path — and age-adjusted interpretation.

## 2026-06-04 — Cheap-model live trial: seam closed and hardened (`cheap-operator-live-trial-01KT6PSA` + `live-trial-follow-up-hardening`)

Shipped the real cheap-model live trial over the session-log substrate's seam,
and a follow-up finished the cleanup the seam still carried:

- **Seam closed for real (FR-001/002).** `live_trial.real_model_operator()` /
  `real_model_driver()` are fully closed delegated factories — a bare call
  defaults to the committed synthetic fixture / default local model and returns
  a working object instead of raising `NotImplementedError`.
- **Inspection-grade attempt telemetry (FR-003).** Each attempt records a
  structured `SelfReconciliationResult` (source columns, accounted, unaccounted)
  plus any parser import/parse error carried separately, so a local inspector
  can see *why* an attempt failed, not just that it did.
- **Local-only backend enforced in code (FR-005 / NFR-002).** A non-local
  `OLLAMA_URL` is rejected before any network request, so prompt data and
  source samples cannot leave the machine through config drift.
- **Opt-in, synthetic-only inspection mode (FR-004 / NFR-004).**
  `keep_sandboxes` retains kept-sandbox trees for inspection, but **only** for a
  synthetic source; a real-data run always tears its sandbox down.

The matching real-model test stays behind the `live_trial` marker and runs
locally against Ollama; the default suite needs no model server and the
live-trial path can never block CI (NFR-001 / NFR-005).

## 2026-06-02 — Session-log substrate slice one + build-and-use doctrine (`session-log-substrate-01KT45S1`)

Merged to master in `798493b` with all eight work packages approved. Landed the
per-run **session log** (a local, PHI-bearing DuckDB store recording sessions,
steps, and ingest provenance) plus the runtime-contract checker, sandbox/ingest
runner, synthetic fixtures + good/dishonest reference parsers, a deterministic
three-rule grader, an offline repeatable check, and the live-trial seam (real
wiring was a named follow-up, closed 2026-06-04). The grader recomputes every
rule from ground truth (warehouse + fixture manifest) and never trusts a
parser's self-report, so a parser that silently drops a field is graded
**fail** by reconciliation even when its own metadata looks clean.

It also carried the **runtime build-and-use doctrine clarification** (FR-130).
The maintainer settled the runtime/dev-time boundary the docs previously
contradicted: at runtime an agent may build a parser and **use it immediately
for the operator's own data, with no reviewer** — this is part of using an
installed Premura. Review enters **only if the human consents to contribute
that parser back** as a public PR. Three docs now agree
(`operating-agent-roles.md` §"Dev-time boundary", ADR 0010,
[DOCTRINE.md](DOCTRINE.md)); "operating role" still means narrowly *a job the
orchestrator dispatches through Premura's MCP tools* — parser-building is
file-editing and not an MCP operating role. Pinned by
`tests/test_doctrine_build_and_use.py` (SC-007) so the docs cannot silently
revert to review-before-use.

## 2026-06-01 — Finished analytical tool set (`finish-analytical-tool-set-01KT0Y95`)

Completed the first bounded analytical tool set by adding the last two
deterministic tools, both on the default MCP surface and routed through the
same admissibility gate, result envelope, and trace recording as the earlier
three:

- **`rolling_mean` — a declared moving-window summary.** A moving level over
  one admitted ordered series across a **caller-declared window**, with visible
  per-point coverage and imputation counts. The window is fixed before the
  result exists; the tool never scans windows. Distinct from `smoothed_average`,
  not a rename. Refuses on a refused/stale/missing input, a bad window,
  insufficient coverage, or any window-scan request.
- **`paired_t_test` — a declared before/after anchor-date comparison.** Reports
  a **paired difference** (mean of after minus before) around one
  caller-declared anchor date, with observed vs expected direction, a
  descriptive **uncertainty band**, imputation visibility, and a confound
  checklist. **Not a significance test**: no p-value, no significance verdict,
  names no cause. Refuses on malformed anchors, out-of-bounds windows, too few
  valid pairs, constant differences, or any request for condition-label
  pairing, arbitrary pair maps, or anchor/window scanning.
- **Scope is anchor-date pairing only.** Broader condition-label pairing is a
  deliberately deferred extension requiring a new pairing contract, new
  trace-identity fields, and new refusal rules (see
  [`src/premura/engine/CONTRACT.md`](../../src/premura/engine/CONTRACT.md)).

## 2026-06-01 — PubMed literature grounding (`pubmed-grounding-tools-01KT1BPM`)

The first **literature grounding** slice: two Stage 3 tools on the default MCP
surface that let an agent find and cite published research, living in
`src/premura/mcp/pubmed.py` (a Premura-owned adapter):

- **`pubmed_search` returns candidates only.** Every hit carries
  `citation_status = candidate_only`; a search candidate is **never** citeable,
  even with a PMID. Search finds records to fetch, not to cite.
- **`pubmed_fetch` returns a citeable record.** Given one exact PMID, returns
  `citation_status = citeable_fetched_record` plus `pubmed_url` and `provider`
  provenance. A final answer may cite **only** a fetched record.
- **One native provider, no new dependency.** Both delegate to a minimal
  adapter over NCBI E-utilities (provider label `ncbi-eutils`) via the Python
  standard library. The candidate-vs-fetched rule is a *Premura* invariant.
  Provider/network failures return a structured `provider_error`, never an
  exception; tests are deterministic and offline.
- **Literature, not the user's data.** These tools never read, diagnose over,
  or compute on the operator's own `hp.*` health data, and run no SQL.

Explicitly not in this slice: full-text retrieval, deep paper analysis, other
sources (Europe PMC, Unpaywall), MeSH lookup, related-article discovery,
citation formatting, concept-to-metric mapping, and the
literature-to-warehouse bridge.

## 2026-06-01 — Fresh-clone bootstrap (`uv run hpipe bootstrap`)

Setup-only behavior for a freshly cloned checkout: prepares and verifies the
local environment + bundled skills, confirms the core surfaces (`hpipe`,
`premura-mcp`, `premura-mcp-operator`) import, and reports whether an
agent-session reload is needed. Never ingests, queries, analyzes, or uploads.

## 2026-05-31 — Research trace audit skill (`research-trace-audit-skill-01KSZC2J`)

A Premura-specific agent skill that consumes the audit-consumer contract
(read-only) to judge one final analytical answer against its session research
trace disclosure. Not a generic answer-audit product; it issues no network call
at runtime.

- Ships at `src/premura/skills/research-trace-audit/`: a prose `SKILL.md`
  (when-to-invoke, the two required inputs — the structured Session Disclosure
  object plus the final answer text — the review procedure, and the
  `pass` / `needs_revision` / `blocked` output shape) beside a bounded
  `AUDIT_RUBRIC.md`.
- **Bounded rubric, not a banned-phrase list**: criteria under four closed
  categories (search-effort disclosure, refused/unavailable handling,
  contradiction handling, overclaim boundary) plus the **rule for adding a
  criterion** — per DOCTRINE, it defines how the list grows.
- Five synthetic calibration fixtures (`pass`, `omitted-search-effort`,
  `hidden-refusal`, `surfaced-unavailable`, `overclaim`); no real `hp.*` rows.
- Installs via the existing `hpipe install-skills` to `.claude/skills/` — the
  one project skill home both Claude Code and OpenCode discover. A separate
  OpenCode installer target was evaluated and deliberately rejected.
- Reads the trace; changes no trace counts, schema, or analytical math.

## 2026-05-31 — Session research trace and multiplicity disclosure (`session-research-trace-01KSYT4A`)

An explicit, append-only ledger at the MCP boundary recording the analytical
calls an agent dispatches in a research session, deriving a *measured*
multiplicity disclosure. Locked architecture: design decision note
[`0009`](../building/adr/0009-session-research-trace-and-multiplicity-disclosure.md).
The stateful trace lives in `src/premura/trace.py` (pure, MCP-agnostic,
engine-agnostic) over `trace.*` tables (migration `005_trace_audit.sql`); the
analytical **engine stayed pure and stateless** — recording happens *around*
dispatch.

- **Explicit session lifecycle.** `research_trace_open` returns a stable
  `session_id` plus the warehouse fingerprint and schema version. The three
  trace tools live on the **default** surface because the trace IS the
  supported agent workflow.
- **Opt-in, byte-identical recording.** Each analytical tool gained an optional
  `session_id`; passing it records the call and attaches a `trace` object
  **beside** the unchanged engine envelope; omitting it writes nothing and the
  envelope is byte-identical.
- **Measured multiplicity disclosure.** `research_trace_disclosure` derives the
  raw call count and the **unique hypotheses examined** (N) from recorded rows —
  exact retries collapse, refusals still count. Framing is "K user-facing
  findings among N unique hypotheses examined"; never "significant results";
  no multiplicity-corrected statistics. JSON canonical; Markdown on demand.
- **Surfaced is an explicit agent mark.** `research_trace_mark_surfaced`
  records which calls the agent actually used. Calls but no marks → surfaced
  reported **unavailable** with an explicit message, never a guessed `0`.
- **Provenance, not health facts.** The trace stores call/result references,
  hashes, and a bounded validity summary — never raw `hp.*` rows. The stable
  structured surface is the
  [audit-consumer contract](../building/architecture/AUDIT_CONSUMER_CONTRACT.md).

## 2026-05-30 — Correlate as a pre-registered lagged association (`correlate-lagged-association-01KSWKV0`)

`correlate`, the first **multi-input** analytical tool, on the default MCP
surface. Locked architecture: design decision note
[`0008`](../building/adr/0008-correlate-pre-registered-lagged-association.md);
operative statistical rules in
[`src/premura/engine/CONTRACT.md`](../../src/premura/engine/CONTRACT.md)
(rationale in the frozen
[`CORRELATE_METHODOLOGY_RESEARCH.md`](../history/research/CORRELATE_METHODOLOGY_RESEARCH.md)).

- **Association, never significance.** A signed Spearman's-rho *association*
  with an effect size and an honest plausible **range** — never a p-value or
  the word "significant", names no cause. Forbidden quantities are refused
  *before* computation.
- **Caller-declared, directional, whole-day lag**, default 0, **never scanned**.
  The pre-registered hypothesis (metric pair, lag, expected direction) is a
  mandatory input.
- **Paired inputs through `prepare_paired_input`**: same-day-after-lag pairing,
  overlap narrowed to actual paired days, imputed-pair fraction recorded. The
  uncertainty band uses an autocorrelation-corrected effective sample size
  (`N_eff`); the tool refuses below the conservative floor. Added the
  `common_cause_plausible` confound key to the closed vocabulary.

## 2026-05-30 — Stage 3 analytical tools, first slice (`stage-3-analytical-tools-01KST48C`)

The first slice of Phase 3 (`v0.3 analytical depth`): a bounded analytical
contract plus two deterministic proof tools on the admissibility foundation.
`src/premura/engine/analytical_contract.py`, `analytical_inputs.py`, and
`analytical_tools.py` define the surface;
`docs/history/research/STAGE3_ANALYTICAL_TOOLS_RESEARCH.md` records the design.

- `change_point` (level-shift detection) and `smoothed_average` (conservative
  trailing smoothed pattern) shipped first; all tools delegate entirely to the
  engine, perform no statistics in the MCP layer, and **name no cause**.
- **Analytical question types are first-class.** Each tool routes to its own
  `QuestionType` with analytical `QuestionRules` on the family policies — not
  collapsed onto `recent_trend` (research note D4 rejected that; mission-review
  fix `42b0880` made the separation real and lock-tested).
- **Admissibility gate before computation.** `prepare_input_series` builds an
  `AnalyticalInputSeries`; inadmissible / stale / insufficient inputs flow
  through as a first-class **refusal** with no estimate.
- **Mandatory result envelope**: estimate **plus** validity metadata and a
  confound checklist from a closed, runtime-owned vocabulary (`ConfoundKey`).
  Agents cannot mint their own quality labels (addresses risk `R7`).

## 2026-05-29 — Evidence-admissibility foundation (`stage-2-evidence-admissibility-foundation-01KSSR40`)

Turned the research note's central finding — *the dangerous failure is using
the wrong evidence for the question, especially old evidence presented as if it
described the present* — into a deterministic policy layer deciding which
evidence is admissible **before** any later tool uses it:

- **Closed question-type vocabulary.** `premura.engine.policies.QuestionType`
  classifies a request before evidence selection (descriptive members plus the
  analytical members added later).
- **Metric-family policies** declare freshness windows and per-question-type
  sufficiency rules in `src/premura/engine/policies/`, per family rather than
  per metric.
- **Admissibility is a deterministic decision.** `evaluate_evidence` decides
  admissible / rejected / insufficient, preserves provenance and rejection
  reasons, and **refuses clearly** when no admissible evidence remains.
  `resting_hr_status` wired through as the proof integration.

## 2026-05-27 — Profile and intake storage + agent-mediated capture (`implement-profile-and-intake-storage-01KSMWV1`)

Gave the profile/intake meaning contract
([PROFILE_AND_INTAKE_CONTRACT.md](../building/architecture/PROFILE_AND_INTAKE_CONTRACT.md))
a concrete storage adapter and the first write path:

- **Concrete domain tables** (migration `004_profile_intake.sql`):
  `hp.profile_capture_session` + `hp.profile_context_assertion` (profile);
  event → item → quantity/dose chains for nutrition and supplements. One-home
  separation is structural — no JSON catch-all, nothing back-fills these
  meanings into `fact_measurement` / `fact_interval`.
- **Agent-mediated profile capture.** A bounded, closed allowlist
  (`birth_date`, `sex`, `standing_height_cm`) written one fact at a time
  through `record_profile_context` (append/supersede, history kept), stamped
  `source_kind="agent_profile_capture"`. Surfaced as the default MCP tools
  `profile_context_supported_fields` / `profile_context_record` and the expert
  CLI verbs `hpipe profile-fields` / `hpipe profile-record`. Unsupported or
  derived keys (e.g. `age`) rejected at the store boundary.
- **Normalized intake load path.** `persist_intake_batch` loads an
  `IntakeBatch` idempotently via the per-event `dedupe_key UNIQUE` constraint.

The BMI cross-domain proof consumer and the input-resolution seam
(`resolve_dependency`, `RESOLVERS`, `@resolver(domain=...)`) shipped on this
foundation, making BMI the first cross-domain Stage 2 signal — computed from
declared standing height plus a usable body-weight observation, refusing
honestly when either prerequisite is missing or stale.

## 2026-05-21 — Live encrypt round-trip + launchd installation verified

`hpipe export --month 2026-05` → `age -d` → `diff` against source = empty
(regression suite `tests/test_encrypt_roundtrip.py`, per-test keypair). The
launchd agent `com.nbrandizzi.premura.monthly` was bootstrapped, kickstarted
(macOS notification fired, `run-monthly` waited at `_wait_for_ready` without
ingesting, clean SIGTERM shutdown), and uninstall verified. Plist render
covered by `tests/test_launchd_plist.py` (incl. `plutil -lint`).

## 2026-05-20 — Drive upload becomes opt-in (policy change)

As the project starts looking like a real application for others, Drive upload
is **opt-in**, not part of the automated monthly run. `hpipe run-monthly` ends
with the encrypted `.age` artifact in `data/exports/YYYY-MM/`; the user decides
whether to `hpipe upload`. The `age` private key stays local by default, with a
password-manager recipe (Bitwarden as reference) in `ops/bootstrap.sh`.

## Earlier — v1 ingest foundation

The four-source ingest pipeline (Health Connect, Garmin GDPR, Sleep as
Android, BMT) into a local DuckDB warehouse with idempotent re-ingest,
cross-source dedupe, encrypted export artifacts, and the `hpipe` CLI. The
historical tag `v1.0.0` marks this foundation as a restore point; the product
line is treated as `v0.x` going forward. See
[ARCHITECTURE_HISTORY.md](../history/architecture/ARCHITECTURE_HISTORY.md) for
the per-source design record.
