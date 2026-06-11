# Improvement Playbook

`playbook_version: 2026-06-12.2`

This file is the bounded registry of **improvement areas** the deterministic
improvement hook maps a judgment's evidence to when it derives durable, agent-readable
improvement **proposals** (see `premura.session_log.store.record_improvement` and the
`log_improvement` table). The hook reads `log_judgment` rows (plus the judge rubric for
criterion→category lookup), and for each piece of weak/failed evidence emits one proposal
in the area this playbook maps that evidence to.

It is the improvement-hook analogue of `JUDGE_RUBRIC.md`: a **registry of areas plus the
rule for adding an area** — deliberately *not* a frozen list of fixes. Per Premura's
DOCTRINE (guide, don't enumerate), code never hardcodes what each area *means* or how to
fix it; it parses this document and records whatever area the playbook maps a judgment to.
Each area carries a `suggested_focus` prose line a proposal carries forward; the *fix* is
for a maintainer agent or the human to decide. The hook **proposes; it never acts** — it
does not edit prompts, harness code, rubrics, or skills, and it never changes a run's
verdict.

## What a proposal is — and is NOT

A proposal is a **durable, descriptive pointer**: "the operator keeps failing this
criterion / the judgment did not complete / the rubric drifted — look here." It carries a
`summary`, the `evidence` that grounds it (the judge's rationale, or the offending
status / criterion id), the `area` below, and the `playbook_version` that produced it.

A proposal **never**:

- acts on itself (no issue/PR creation, no prompt/harness/rubric/skill edit);
- changes `contract_pass`, the scoreboard, the judgment, or the trial verdict — those are
  read-only inputs the hook consumes, exactly as the judge consumes the grader's facts;
- invents a numeric score or a health/clinical claim — it is a descriptive process pointer.

## How evidence maps to an area

The hook derives proposals by these rules; each rule names the area below it maps to.

| When the judgment carries… | …the hook emits one proposal in area |
|---|---|
| a criterion banded `weak` | the area mapped from that criterion's **rubric category** (the four category areas below) |
| a judgment `status` other than `complete` (e.g. `unparseable`, `model_unavailable`) | `harness_reliability` |
| a judged criterion id the **current rubric does not define** | `rubric_drift` |

Bands `strong` / `adequate` / `not_applicable` produce nothing. The mapping from a
criterion to its category is read from the judge rubric (`JUDGE_RUBRIC.md`), never
hardcoded here — this playbook only maps a **category** (or a hook-owned condition) to an
area, so adding a rubric criterion never requires a playbook edit as long as its category
already has an area.

## Improvement areas

Each area has a stable `area` id (the value stored in `log_improvement.area`), the
**category or condition** it maps from, a `suggested_focus` line the proposal carries, and
grounding guidance. The four category areas are the closed rubric categories; the two
hook-owned areas cover the conditions the categories cannot (a judgment that did not
complete, and a criterion the rubric no longer defines).

### `process_honesty`

- **maps from category:** `process_honesty`
- **suggested_focus:** Review whether the operator's prompt and tool guidance let it claim
  outcomes the recomputed facts contradict; tighten the honesty guidance or the self-check.
  For an *analyze-and-answer* session this covers analytical honesty too — whether the prompt
  lets the operator state numbers the analytical tools did not return, smuggle a forbidden
  statistical claim ("significant", a p-value, a cause, a population-norm comparison), or claim
  an estimate the engine refused; tighten the answer-honesty guidance accordingly.
- **grounding:** the judge's rationale on the weak criterion, compared against the dossier's
  recomputed facts — for a parser session `contract_pass` / `rows_inserted` / `unaccounted`;
  for an analyze-and-answer session the engine's returned analytical results vs. the answer's
  claimed numbers and any forbidden statistical claim in the answer text (read by the judge,
  carried as evidence).

### `goal_adherence`

- **maps from category:** `goal_adherence`
- **suggested_focus:** Review whether the driver's goal was stated clearly enough and the
  prompt kept the operator on it; consider sharpening the goal framing or guardrails.
- **grounding:** the judge's rationale on the weak criterion plus the goal in the dossier.

### `tool_use_economy`

- **maps from category:** `tool_use_economy`
- **suggested_focus:** Review the prompt's tool guidance — what to read, when to stop,
  how to avoid redundant or thrashing calls; consider tightening the tool-use instructions.
- **grounding:** the judge's rationale on the weak criterion plus the transcript's tool turns.

### `failure_recovery`

- **maps from category:** `failure_recovery`
- **suggested_focus:** Review whether failure feedback (parse errors, unaccounted columns)
  is surfaced legibly enough for the operator to correct course; consider improving the
  feedback the harness feeds back between attempts.
- **grounding:** the judge's rationale on the weak criterion plus per-attempt `parser_error` /
  `unaccounted` across attempts.

### `harness_reliability`

- **maps from condition:** a judgment `status` other than `complete` (`unparseable`,
  `model_unavailable`, or any future non-`complete` status in `JUDGMENT_STATUSES`).
- **suggested_focus:** Investigate the judge backend / prompt — a judgment that did not
  complete means the *evaluation* failed, not the operator; check model availability, the
  judge prompt, and the retry budget.
- **grounding:** the judgment's `status` and its preserved `raw_output`.

### `rubric_drift`

- **maps from condition:** a judged criterion id that the **current rubric does not
  define** (the judgment was produced under a rubric version whose criterion set has since
  changed).
- **suggested_focus:** Reconcile the rubric — a judged criterion the current rubric no
  longer defines means the rubric drifted under recorded judgments; decide whether to
  restore the criterion or re-judge under the current rubric.
- **grounding:** the off-rubric criterion id and the judgment's `rubric_version`.

## Rule for adding an area (what makes this a playbook, not a list)

A new area is admissible **iff** it:

1. maps from **exactly one** of the closed rubric categories above, OR from a single
   hook-owned **condition** expressible over the closed store vocabularies
   (`CRITERION_BANDS`, `JUDGMENT_STATUSES`, `PROPOSAL_STATUSES`) and the parsed rubric —
   never from ad-hoc string matching on transcript content;
2. carries a `suggested_focus` line that points a maintainer at *what to review*; it never
   prescribes an automatic edit, and it never recommends changing `contract_pass`, the
   judgment, the scoreboard, or the trial verdict — the hook consumes those, never repairs
   them;
3. is added by editing **this file** — adding the `area` id, the category or condition it
   maps from, its `suggested_focus`, and its grounding — and **bumping `playbook_version`**
   at the top. No schema change and no store change is ever needed: the store validates the
   `status` against `PROPOSAL_STATUSES` and records whatever `area` id appears here, exactly
   as it records whatever criterion ids the rubric defines.

## Anti-pattern (rejected at review)

An area that hardcodes a fixed checklist of operator behaviors ("propose this when the
transcript contains the word *works*…") or that emits a fix to apply automatically. That
hardcodes a list where it should map a category/condition to a review pointer, and it
crosses the propose/act boundary. New tiers will fail in ways no behavior list anticipates;
mapping the rubric *category* (or a vocabulary-expressible condition) to an area is what
keeps the hook a level above. An area must also never act on its own proposal or touch the
grader facts, the judgment, the scoreboard, or the trial verdict.
