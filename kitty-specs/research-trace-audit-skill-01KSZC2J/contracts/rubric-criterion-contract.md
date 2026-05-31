# Contract: Audit Rubric Criterion (the "guide, don't enumerate" surface)

This contract is the Design-Altitude gate for the mission. The audit rubric is a **bounded
registry of criteria with a documented rule for adding a criterion** — not a closed list of
banned phrases. `AUDIT_RUBRIC.md` ships the criteria; this contract is the rule a reviewer
checks the rubric against.

## Closed vocabulary: criterion category

Every criterion belongs to exactly one category. The **categories** are closed (they map to
the spec's review dimensions); the **criteria within them are open** and grow by the rule below.

| Category | The question it answers | Grounding disclosure fields |
|---|---|---|
| `search_effort_disclosure` | Did the answer disclose how much was examined? | `raw_analytical_call_count`, `unique_hypothesis_count` (`N`), `surfaced`, disclosure framing |
| `refused_or_unavailable_handling` | Were refused / errored / unavailable calls hidden? | `refusal_breakdown`, per–`Call Record` `terminal_status` / `refusal_reason` / `error_kind`, `surfaced.status` |
| `contradiction_handling` | Were contradictory findings suppressed? | `calls`, surfaced `marks`, answer spans |
| `overclaim_boundary` | Did the answer claim more than the tools support? | answer spans vs tool semantics (association/change/smoothed only) |

## Required fields per criterion

- `id` — stable kebab-case identifier.
- `category` — one of the four closed categories above.
- `question` — the yes/no review question an agent answers.
- `evidence_source` — which disclosure field(s) or answer span grounds the judgment.
- `failure_modes` — what a failing answer looks like (illustrative, not exhaustive).
- `suggested_revision_hint` — what safer wording / disclosure looks like.

## Rule for adding a criterion (the part that makes this a rubric, not a list)

A new criterion is admissible **iff** it:

1. names exactly one of the four closed categories (a genuinely new category requires a spec
   amendment, not a rubric edit);
2. grounds its `evidence_source` in a **structured** audit-consumer field or a quoted answer
   span — never in `disclosure_text` prose, effect size, or an inferred surfaced count
   (C-002);
3. introduces **no** forbidden semantic (no p-value, significance label, multiplicity
   correction, or causal/diagnostic/treatment/prediction framing of its own — C-003, C-004);
4. ships with at least one fixture (existing or new) that the criterion changes the verdict on,
   so the criterion is exercised, not aspirational.

## Anti-pattern (rejected at review)

A criterion that hardcodes a fixed list of forbidden tokens ("flag the words *significant*,
*causes*, *diagnoses*…") instead of asking the category question. Per project DOCTRINE, that
hardcodes a list where it should define the rule for adding to the list. New analytical tools
will introduce overclaim modes no token list anticipates; the category question must catch them.
