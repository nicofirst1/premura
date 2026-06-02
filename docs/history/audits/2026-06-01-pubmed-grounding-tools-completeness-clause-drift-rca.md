# Implement-Review Drift Audit — pubmed-grounding-tools-01KT1BPM

> Method: [`docs/building/agents/implement-review-drift-audit.md`](../../building/agents/implement-review-drift-audit.md).
> This audit consumes a post-merge mission-review FAIL and asks *why the
> implement→review→merge loop admitted it*, then names the missing control so the
> next mission cannot repeat it. The bugs are already fixed; this is the
> post-mortem on the **control gap**, not a bug report.

## Audited subject

| Field | Value |
|---|---|
| Mission | `pubmed-grounding-tools-01KT1BPM` — PubMed Grounding Tools |
| Mission merge commit | `d80c724` (squash of WP01–WP04 into `master`) |
| Mission-review verdict | **FAIL** (OpenCode / GPT-5.5, senior mission reviewer, 2026-06-01) |
| Reviewer HEAD | `f7c8b2f` (pre-fix; post-merge test-sync + lint cleanup only) |
| Findings audited | DRIFT-1 (HIGH, FR-004) — `pubmed_fetch` never returns abstracts; DRIFT-2 (MEDIUM, Scenario 1) — `pubmed_search` returns PMID-only candidates with no titles |
| Remediation | **FIXED** in `78188ba` "fix(pubmed): return abstracts (EFetch) and candidate titles (ESummary)" (+ 5 positive/negative-path tests) |
| Audit HEAD | `78188ba` |

The mission-review **detector worked**: it FAILed the merged record on an
unaccepted HIGH drift. This audit targets the per-WP loop, so the post-merge
detector is not the *only* net that catches this class. Both drifts share one
root cause, so they are traced together.

## The two findings, traced through the method's five questions

### 1. Introduction — where/when they entered

- Both entered in **WP02** (`src/premura/mcp/pubmed.py`), the provider core. The
  code is entirely inside one WP's owned scope — neither is a hand-off omission
  between code WPs.
- **DRIFT-1 (abstract):** `pubmed_fetch` called only ESummary and **hardcoded**
  `abstract=None` with a comment that names the gap out loud: *"ESummary does
  not carry the abstract … EFetch would be needed for abstracts; out of the
  first slice."* (pre-fix `pubmed.py:373-376` at `d80c724`). ESummary structurally
  cannot return an abstract, so the field was `None` for **every** record, not
  just records that lack one.
- **DRIFT-2 (titles):** `pubmed_search` built `PubMedCandidate(pmid=pmid)` only
  (pre-fix `pubmed.py:226`). `PubMedCandidate` *has* `title`/`snippet` fields,
  but they defaulted `None` and no code path ever populated them — a
  defined-but-never-written cousin of dead code.
- **The contract did *not* create either gap by silence — it was correct.** The
  spec requires "abstract text when available" (`spec.md:49`, FR-004 `:78`) and
  search "candidate PMIDs and human-readable titles or summaries when PubMed has
  matches" (`spec.md:40`). The mission-local contract repeats both. These are
  **implementer slips against a correct contract**, accepted at review.

### 2. Controls the artifacts passed through

1. **WP01** (research gate) `Decision` section — chose "minimal native NCBI
   E-utilities build" as the provider path WP02 must implement.
2. WP02 implement prompt (TDD; "preserve missing optional fields as `None`";
   "do not synthesize abstracts, authors, journals, or dates"
   `WP02 task:145-146`).
3. The mission contract / `data-model.md` field definitions.
4. **WP02 per-WP review** (acceptance fixtures + scope + citation invariant).
5. **WP01 per-WP review** (decision clarity).
6. Orchestrator scheduling / merge gate.
7. Post-merge mission-review — **CAUGHT both** (the backstop, not the
   prevention).

### 3. Why each control missed

- **WP01 decision + WP01 review:** WP01 chose "native E-utilities" but never
  mapped each downstream FR clause to a concrete E-utilities **primitive**
  (search-titles → ESummary on the search PMIDs; fetch-abstract → EFetch;
  fetch-metadata → ESummary). It could not be expected to: **WP01's
  `requirement_refs` are `FR-007, FR-010` only — not `FR-001..FR-006`**
  (`tasks/WP01-*.md` vs `tasks/WP02-*.md` frontmatter). WP01's job was to make
  the decision *concrete and singular* so "a reviewer can answer *what should
  WP02 build?*" — and the WP01 review (this session) verified exactly that:
  **singularity and clarity, not capability coverage** of the FR clauses that
  live in a different WP. "Native E-utilities" is a *family* of primitives;
  choosing the family without enumerating which primitive each FR clause needs
  left WP02 free to pick the cheapest one.
- **WP02 prompt:** stressed missingness ("preserve missing optional fields as
  `None`"; "do not synthesize") — i.e. the **negative** path — and never
  demanded a **positive-path** fixture (provider supplies an abstract/title ⇒
  assert it is returned). It also pointed at scope-creep risks (full-text, MeSH)
  but not at availability-clause completeness.
- **Contract / data-model:** named the candidate title as *"optional … must not
  be fabricated"* (`contract:29`) and the abstract as *"when available"*
  (`data-model.md:48`). Framing both as **optional + never-fabricated** invited
  the reviewer to read the always-`None` implementation as *compliant
  missingness* rather than *an unimplemented availability path*.
- **WP02 review — the decisive miss.** The approval note conflates the two
  complementary halves of the same field in one sentence:
  *"missing metadata stays None/[] never fabricated **(abstract always None,
  EFetch deferred)**"* (`tasks/WP02-*.md:172`). The reviewer verified **FR-005**
  (missing → explicit `None`, correct) and, in the same breath, **accepted the
  unimplemented FR-004** ("abstract when available") as if the missingness
  behavior covered it. For DRIFT-2 the search test asserted only PMIDs +
  `candidate_only` and never asserted a title — so the title path was never
  exercised at all. A green **missingness-only** test gave false confidence the
  fields were "handled."
- **Orchestrator prompts (mine):** I pressed hard on the citation invariant
  (candidate vs fetched), the Stage-3 offline boundary, and scope-creep — but I
  never asked WP02 to **prove the availability half** of FR-004 / Scenario-1
  with a positive fixture, and I let the WP02 reviewer's "EFetch deferred" note
  stand instead of treating it as a spec deviation. The orchestrator prompt is
  itself a control, and it missed too.

### 4. The missing control

A **gated-decision capability-coverage map plus a positive-path fixture per
availability clause**, firing in three places:

- **At the gating WP (WP01):** its `Decision` must carry a **clause→primitive
  coverage map** for every downstream FR clause — filed against `FR-001..FR-006`,
  not only WP01's own `FR-007/FR-010` — e.g. *"FR-004 abstract ⇒ EFetch; Scenario-1
  titles ⇒ ESummary on search PMIDs; FR-003 metadata ⇒ ESummary."* The
  gating-WP review then checks **coverage**, not just **clarity/singularity**.
- **At the implementing WP (WP02) Definition of Done:** a **positive-path
  acceptance fixture for every "when available" clause** (provider returns the
  abstract/title ⇒ assert it is surfaced), kept **distinct** from the
  negative/missingness fixture — because a missingness-only suite passes while
  the availability path is entirely absent.
- **At the per-WP review:** a code comment that *defers a spec-required
  behavior* ("EFetch deferred; out of first slice") is a **deviation requiring a
  spec amendment or a rejection**, never a review-note acceptance. The reviewer
  recording the deferral in the activity log *was* the drift signal; the loop
  needs to act on it at the gate, not only at audit time.

This is exactly what the fix added: `78188ba` gives `pubmed_fetch` a best-effort
**EFetch** call for the abstract (`pubmed.py:318`, `_fetch_abstract` `:439`),
`pubmed_search` a best-effort **ESummary** enrichment for titles
(`pubmed.py:237`, `_candidate_summaries` `:404`), and **positive-path tests**
(`test_fetch_includes_abstract_when_available` `test_mcp_pubmed.py:313`,
`test_search_candidates_carry_human_readable_titles_when_available` `:212`)
alongside the retained missingness tests — both bases now separated under test.

### 5. Generalizable lesson → dimension

A new class, added to the registry as **D5 — Gated-decision capability
sufficiency**. The drift hides in two gaps at once:

- **between the gating WP and the implementing WP** — the gate (WP01) owns the
  *approach* but not the *FR clauses* the approach must satisfy (they live in
  WP02's `requirement_refs`), so the gate review verifies decision clarity while
  capability coverage is owned by no one; and
- **between an FR's missingness half and its availability half** — FR-005
  ("absent → explicit `None`") and FR-004 ("present → returned") are
  complementary, and satisfying the missingness half with an always-`None` field
  *looks* like the field is handled, masking that the availability path was never
  written. A missingness-only fixture is structurally blind to it.

## Evidence index

| Claim | Reference |
|---|---|
| Abstract hardcoded `None`, gap named in comment | `pubmed.py:373-376` (pre-fix at `d80c724`) |
| Candidates built PMID-only, title/snippet never set | `pubmed.py:226` (pre-fix); `PubMedCandidate` fields default `None` |
| Spec requires abstract "when available" | `spec.md:49` (Scenario 2 AC), `:78` (FR-004) |
| Spec requires search titles "when matches" | `spec.md:40` (Scenario 1 AC) |
| FR-005 missingness (the half that *was* met) | `spec.md:79` |
| WP01 owns only FR-007/FR-010 (not the provider FRs) | `tasks/WP01-research-gate-and-contract-finalization.md` frontmatter |
| WP02 owns FR-001..FR-006, FR-008 | `tasks/WP02-pubmed-core-provider-contract.md` frontmatter |
| WP02 review conflates missingness with availability | `tasks/WP02-pubmed-core-provider-contract.md:172` ("abstract always None, EFetch deferred") |
| Contract frames title/abstract as optional/never-fabricated | `contracts/pubmed-grounding-contract.md:29`, `data-model.md:48` |
| Fix: EFetch abstract + ESummary titles | `78188ba` (`pubmed.py:237,318,404,439`) |
| Fix: positive-path regression tests | `78188ba` (`tests/test_mcp_pubmed.py:212,313`) |
| Regression green at audit HEAD | `pytest tests/test_mcp_pubmed.py -k "abstract or title"` → 5 passed |

## Unifying root cause

A **research/decision WP is scoped to make a choice, not to deliver the
feature** — so its `requirement_refs` cover the *gate* (FR-007/FR-010), never the
*downstream functional clauses* (FR-001..FR-006) the choice must satisfy. Its
review therefore checks the decision is **singular and clear** and stops there;
**capability coverage of every downstream FR clause is owned by no control.** The
implementing WP then satisfies each FR's *missingness* half (always-`None`,
trivially green) while leaving the *availability* half unimplemented, and the
per-WP reviewer — reading an always-`None` field as compliant missingness —
records the shortfall as a "deferral" instead of a spec deviation. The post-merge
mission-review is currently the only place a gated approach's per-clause
sufficiency is exercised.

## Remediation status

| Item | Status |
|---|---|
| `pubmed_fetch` returns abstract when available (EFetch) | **FIXED** — `78188ba` (`pubmed.py:318,439`) |
| `pubmed_search` returns human-readable titles when matches (ESummary) | **FIXED** — `78188ba` (`pubmed.py:237,404`) |
| Positive-path fixtures for both availability clauses | **FIXED** — `78188ba` (`test_mcp_pubmed.py:212,313`) |
| Drift dimension registry extended | **DONE** — D5 added to `docs/building/agents/implement-review-drift-audit.md` |
| Systemic prevention (below) | **OPEN** — recommendations for the next missions |

## Prevention — stop the class, not just this instance

1. **Adopt the capability-coverage map (D5) at the gating WP.** Any research /
   adopt-vs-wrap-vs-build WP must end its `Decision` with a clause→primitive
   map covering **every downstream FR clause**, cross-referenced to the FR IDs
   that live in the *implementing* WPs — not only the gate's own
   `requirement_refs`. The gating-WP review verifies coverage, not just that one
   path was chosen.

2. **Require a positive-path fixture per "when available" clause as a DoD item.**
   For every FR clause of the form "include X when available / when present,"
   the owning WP must ship ≥1 acceptance fixture where the provider **does**
   supply X and X is asserted present, kept distinct from the negative fixture
   where X is absent → explicit `None`. Add this line to the implement-prompt
   validation block and the review checklist.

3. **Stop conflating missingness with availability in review.** FR-005-style
   ("absent → explicit") and FR-004-style ("present → returned") are two
   requirements, not one. A reviewer must verify **both halves separately**; an
   always-`None`/always-empty field satisfies only the missingness half and is a
   red flag for an unimplemented availability path, never evidence it is handled.

4. **Treat a "deferral" comment for a spec-required behavior as a deviation.**
   When an implementer writes "X deferred / out of first slice" for behavior the
   spec or contract requires, the per-WP reviewer must either reject the WP or
   require a spec/contract amendment that records the descope — not wave it
   through in the activity log. A correct-but-unreconciled deferral is a drift
   signal at the gate, not only at audit time.

5. **Cheap static smell as a backstop.** Flag any provider/serializer field that
   is assigned a constant `None`/`[]` on **every** path while the contract types
   it "when available" — a one-line grep/ruff-style check that surfaces an
   unimplemented availability clause before review.

6. **Run this audit method after every mission-review FAIL or PASS-WITH-NOTES**,
   not only on request, so a single HIGH drift or a "deferral" note becomes a
   durable control change rather than a one-off patch.
