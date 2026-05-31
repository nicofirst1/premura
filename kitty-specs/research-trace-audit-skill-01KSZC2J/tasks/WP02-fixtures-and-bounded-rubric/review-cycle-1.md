# WP02 Review — Cycle 1 (changes requested)

Strong work overall. The rubric is a genuine bounded registry (categories + a real
rule-for-adding-a-criterion), PHI/synthetic hygiene is clean, scope is exactly the owned
files, and all five expected verdicts are correctly derivable from the rubric. One
internal-consistency defect blocks approval.

## Blocking issue

**`calls_truncated` is `false` while the inlined `calls` list is a strict subset of
`raw_analytical_call_count` in four of five fixtures — internally inconsistent with the
producer's actual semantics.**

The producer (`src/premura/trace.py`, `_call_records`) inlines **every** recorded call up to
`DEFAULT_CALL_LIMIT = 1000` and sets `calls_truncated = True` *only* when the session has more
records than the cap. So on the real `research_trace_disclosure` output, `calls_truncated: false`
asserts "this inlined list is complete" and its length therefore equals
`raw_analytical_call_count`. The data-model says the same from the consumer side: "When
`calls_truncated` **is set**, summary counts are authoritative — the skill does not require every
raw call." The contrapositive: when it is **not** set, the list is the full set.

Current state:

| fixture | raw_analytical_call_count | len(calls) | calls_truncated | consistent? |
|---|---|---|---|---|
| pass.json | 14 | 3 | false | NO |
| hidden-refusal.json | 6 | 3 | false | NO |
| surfaced-unavailable.json | 8 | 2 | false | NO |
| overclaim.json | 10 | 1 | false | NO |
| omitted-search-effort.json | 23 | 1 | true | yes |

`omitted-search-effort.json` is correct: it inlines one representative call, sets
`calls_truncated: true`, and is internally consistent (summary counts authoritative). The other
four claim a complete list (`false`) that does not match their own `raw_analytical_call_count`.

### Fix (keep the small fixtures — that intent is correct)

The WP prompt explicitly wants small fixtures ("do not add sprawling call histories when one or
two representative calls prove the point"), so do **not** balloon the call lists. Instead, set
`calls_truncated: true` on the four fixtures whose inlined `calls` list is a deliberate
representative subset of `raw_analytical_call_count` (pass, hidden-refusal, surfaced-unavailable,
overclaim). That makes each disclosure honestly state "this inlined list is capped; the summary
counts are authoritative," which is exactly the path the rubric and data-model already rely on
for counts — and it does not weaken any criterion (every criterion grounds on a structured count
or a per-call record that is still inlined).

If instead you intend a fixture to assert a complete list, set `raw_analytical_call_count` equal
to `len(calls)` for that fixture. Either resolution is fine; the current mix of `false` +
shorter-than-raw list is not.

## Non-blocking observations (no action required, noted for completeness)

- Rubric passed the banned-token / Design-Altitude gate: four closed categories, open criteria,
  an admissibility rule, and an explicit anti-pattern section. Not a banned-phrase list.
- No forbidden semantics introduced by the rubric itself (C-002..C-004): it only *flags*
  causation/diagnosis/treatment/significance in the audited answer.
- PHI/risk-boundary-5 clean: no `hp.*` rows, no real health readings; all ids/hashes obviously
  fake; `result_ref` carries opaque ids/hashes only.
- `contradiction_handling` is reviewed-and-clear on `pass.json` and documented as exercisable by a
  future fixture under the add-a-criterion rule — acceptable.
