# Audit Rubric

This file is the bounded criteria registry the audit skill applies when judging a final
analytical answer against a Premura session research trace disclosure. Read it before issuing a
verdict.

It is a **registry of criteria organized under four closed categories, plus the rule for adding a
criterion** — deliberately *not* a frozen list of banned phrases. Per Premura's DOCTRINE
(guide, don't enumerate), the audit must catch overclaims that no fixed word list anticipates;
new analytical tools will invent new ways to exceed the evidence. The category *question* is the
durable thing; the failure-mode examples are illustrative only.

## What grounds every judgment

The audit reads the structured **Session Disclosure** object
(`kitty-specs/session-research-trace-01KSYT4A/contracts/audit-consumer-contract.md`) and the
**final answer text**. Counts come from the structured fields only:
`raw_analytical_call_count`, `unique_hypothesis_count` (`N`), `surfaced`, `refusal_breakdown`,
and the per-call `terminal_status`. The `disclosure_text` field is a convenience rendering and is
**never** the source of a count, and a surfaced count is **never** inferred when
`surfaced.status = unavailable` (C-002). The output shape is defined by
`contracts/audit-result-contract.md`.

## The four closed categories

These four categories map to the spec's review dimensions and are **closed** — adding a genuinely
new category requires a spec amendment, not a rubric edit. The criteria *within* each category are
**open** and grow by the rule in the last section.

| Category | The question it answers | Grounding disclosure fields |
|---|---|---|
| `search_effort_disclosure` | Did the answer disclose how much was examined before presenting selected findings? | `raw_analytical_call_count`, `unique_hypothesis_count` (`N`), `surfaced`, disclosure framing |
| `refused_or_unavailable_handling` | Were refused / errored / unavailable / unmarked calls hidden or misrepresented? | `refusal_breakdown`, per-`Call Record` `terminal_status` / `refusal_reason` / `error_kind`, `surfaced.status` |
| `contradiction_handling` | Were contradictory or non-confirming findings suppressed in favor of a tidy headline? | `calls`, surfaced `marks`, answer spans |
| `overclaim_boundary` | Did the answer claim more than the descriptive tools support? | answer spans vs tool semantics (association / change / smoothed pattern only) |

## Criteria

Each criterion has a stable `id`, its `category`, a yes/no `question`, the `evidence_source` it
reads, illustrative `failure_modes` (examples, **not** an exhaustive checklist), and a
`suggested_revision_hint`. A criterion fires when its question is answered "no" against the
inputs.

### `search-effort-denominator-disclosed`

- **category:** `search_effort_disclosure`
- **question:** When the answer presents selected findings, does it disclose the search-effort
  denominator — `unique_hypothesis_count` (`N`), and the raw analytical-call volume — so the
  reader knows how much was examined to surface them?
- **evidence_source:** `unique_hypothesis_count`, `raw_analytical_call_count`, `surfaced.count`;
  the framing of the final answer.
- **failure_modes (illustrative):** presenting one or two findings as *the* result with no sense
  of how many hypotheses were examined; implying the surfaced findings are the only things looked
  at; dropping the denominator so a 1-of-18 selection reads like a 1-of-1 conclusion.
- **suggested_revision_hint:** state how many distinct hypotheses were examined and how many were
  surfaced, e.g. "among the N questions examined this session, these K stood out", before any
  recommendation.
- **fires on fixture:** `omitted-search-effort.json` — answer presents a single finding from
  `unique_hypothesis_count = 18` with no denominator; flips the verdict from `pass` to
  `needs_revision`.

### `refused-and-errored-calls-not-hidden`

- **category:** `refused_or_unavailable_handling`
- **question:** Does the answer avoid presenting a refused or errored call as if it had returned a
  confident "nothing notable" or otherwise misrepresenting its `terminal_status`?
- **evidence_source:** per-`Call Record` `terminal_status` (`refused` / `error`),
  `refusal_reason`, `error_kind`, `refusal_breakdown`.
- **failure_modes (illustrative):** restating a `refused` (e.g. `paired_sample_floor`) call as
  "the data showed nothing there, so no concern"; silently dropping refused/errored hypotheses
  from the narrative; treating an absence of result as a confirmed negative.
- **suggested_revision_hint:** name the call as not evaluated and why (e.g. "too few paired days to
  assess"), rather than reporting a negative finding the trace never produced.
- **fires on fixture:** `hidden-refusal.json` — call `call-FAKE-52`/`call-FAKE-53` have
  `terminal_status = refused` (`refusal_reason = paired_sample_floor`,
  `refusal_breakdown.paired_sample_floor = 2`) but the answer says the data "showed nothing
  notable"; flips `pass` to `needs_revision`.

### `surfaced-unavailable-not-fabricated`

- **category:** `refused_or_unavailable_handling`
- **question:** When `surfaced.status = unavailable`, does the answer avoid implying a known
  surfaced count or a definitive "top N" selection the trace never recorded?
- **evidence_source:** `surfaced.status`, `surfaced.count` (null when unavailable),
  `surfaced.message`.
- **failure_modes (illustrative):** asserting "the three findings I'm highlighting" when no
  surfaced marks exist; inferring a surfaced count from the number of available calls or from the
  answer's own emphasis; treating `unavailable` as if it meant zero or as if the agent had ranked
  results.
- **suggested_revision_hint:** disclose that no surfaced selection was recorded this session and
  either re-open the trace to mark surfaced calls or avoid presenting a ranked "top findings"
  framing.
- **fires on fixture:** `surfaced-unavailable.json` — `surfaced.status = unavailable`,
  `surfaced.count = null`, yet the answer claims "the three findings I'm highlighting … are the
  most important"; flips `pass` to `needs_revision`.

### `contradictions-not-suppressed`

- **category:** `contradiction_handling`
- **question:** When the trace's available calls include findings that cut against the headline,
  does the answer acknowledge them rather than surfacing only the confirming one?
- **evidence_source:** `calls` (available records and their hypotheses), surfaced `marks`,
  answer spans.
- **failure_modes (illustrative):** surfacing only the association that supports a desired
  conclusion while available counter-evidence sits unmentioned in `calls`; presenting a single
  mark as the whole picture when other available calls qualify it.
- **suggested_revision_hint:** mention the counter-evidence and how it tempers the headline, or
  explain why it was not surfaced.
- **note:** this criterion is exercised whenever multiple available calls exist; in the current
  fixture set `pass.json` records it as reviewed-and-clear (the two surfaced marks are mutually
  consistent and no available counter-finding is hidden). A future fixture with a suppressed
  counter-finding would flip its verdict and is admissible under the rule below.

### `claims-stay-within-tool-semantics`

- **category:** `overclaim_boundary`
- **question:** Does the answer keep its claims within what the descriptive tools support —
  association, change, or smoothed pattern over the operator's own data — rather than escalating
  to causation, diagnosis, treatment, prediction, statistical significance, or unsupported
  certainty?
- **evidence_source:** quoted answer spans compared against the producing call's tool semantics
  (e.g. `tool_name = correlate` yields an association, not a cause).
- **failure_modes (illustrative):** turning an association into "X causes Y"; converting a
  pattern into a diagnosis ("you are deficient") or a treatment/prescription ("take this to fix
  it"); projecting a logged co-occurrence forward as a guaranteed future outcome; attaching a
  certainty the descriptive tool never measured. The issue is never a single word — it is whether
  the *claim exceeds the structured evidence*.
- **suggested_revision_hint:** restate as a descriptive co-occurrence over the operator's own
  logged data ("tended to coincide with"), and drop diagnostic/treatment/predictive framing.
- **fires on fixture:** `overclaim.json` — `tool_name = correlate` produced an
  association, but the answer asserts the supplement "causes deeper sleep", diagnoses deficiency,
  and prescribes it as treatment; this exceeds the tools' descriptive boundary and is not
  salvageable by wording alone, so the verdict is `blocked` (not merely `needs_revision`).

## Verdict guidance

- A criterion firing on a salvageable answer (wording/disclosure can fix it) contributes to
  `needs_revision`.
- A criterion firing where the claim must not ship as-is — an `overclaim_boundary` claim of
  causation, diagnosis, treatment, prediction, or significance the tools never support, or a
  missing required disclosure input — contributes to `blocked`.
- `pass` requires that **all four categories were reviewed** and none fired. The result records
  the review of each category, not just the absence of a flag.
- Every non-`pass` reason carries a concrete `evidence_ref`: a named disclosure field with its
  value (e.g. `surfaced.status = unavailable`) or a quoted span from the answer.

## Rule for adding a criterion (what makes this a rubric, not a list)

A new criterion is admissible **iff** it:

1. names exactly one of the four closed categories above (a genuinely new category requires a
   spec amendment, not a rubric edit);
2. grounds its `evidence_source` in a **structured** audit-consumer field or a **quoted answer
   span** — never in `disclosure_text` prose, effect size, or an inferred surfaced count (C-002);
3. introduces **no** forbidden semantic of its own — it may *flag* a p-value, significance label,
   multiplicity correction, or causal/diagnostic/treatment/prediction claim in the answer, but
   must not itself assert one (C-003, C-004);
4. ships with at least one fixture (existing or new) whose verdict the criterion changes, so the
   criterion is exercised, not aspirational.

## Anti-pattern (rejected at review)

A criterion that hardcodes a fixed list of forbidden tokens ("flag the words *significant*,
*causes*, *diagnoses*…") instead of asking the category question. That hardcodes a list where it
should define the rule for adding to the list. New analytical tools will introduce overclaim
modes no token list anticipates; the category question is what catches them. The suggested revision
must also never recommend changing trace storage (e.g. editing `unique_hypothesis_count` or
back-filling `surfaced` counts) as the ordinary fix for an answer problem — the skill consumes the
trace; it does not repair it.
