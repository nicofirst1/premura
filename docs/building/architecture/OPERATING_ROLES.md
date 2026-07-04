# Operating roles and the runtime orchestrator

> Status: **authoritative specification** for Premura's Stage 4 runtime
> multi-agent surface. Promoted 2026-06-12 from the pre-spec draft
> ([`docs/building/planning/operating-agent-roles.md`](../planning/operating-agent-roles.md),
> kept for history) in a maintainer design-interview; the five locked
> decisions are decision note
> [0013](../adr/0013-operating-roles-promotion-decisions.md), on the concept
> locked by [0010](../adr/0010-runtime-orchestrator-and-operating-roles.md).
>
> Companion reading: [`DOCTRINE.md`](../../shared/DOCTRINE.md) (the two
> rules), [`STAGES.md`](STAGES.md) (Stage 4 owns interview/conversation/
> presentation and never reads `hp.fact_measurement` or calls the engine
> directly), [`docs/operating/RUNTIME_AGENT.md`](../../operating/RUNTIME_AGENT.md)
> (the runtime contract that binds operating agents to this surface).

## What this is

After Premura is installed, a human brings a health-data goal to an operating
agent. The **orchestrator** is how that agent operates Premura safely: it
routes the goal to bounded **operating roles**, records every cross-role
handoff, and — the piece nothing else provides — **structurally stops an
unaudited health answer from being presented as Premura-verified**.

This is runtime only: not the bootstrap agent that prepares a clone, and not
the dev-time workflow that changes Premura's code. The settled vocabulary
(orchestrator, operating role, improvement candidate/queue, share packet,
lifestyle context — and why `operator` is avoided) is inherited verbatim from
the draft and is not restated here.

## The hybrid shape (locked)

The operating agent stays the intelligence. A thin deterministic layer owns
exactly two things, because they must not depend on agent goodwill:

1. **The handoff trace.** Every role dispatch and handoff is recorded through
   the session log's sole-writer API (the separate session-log DuckDB of ADR
   0011) — *not* the warehouse research trace, so research multiplicity
   counts ("N hypotheses examined") stay uncontaminated by design. Trace
   entries carry compact references (`from`, `to`, `task_summary`,
   `inputs_ref`, `outputs_ref`, `surface_touched`, `status`, `reason`), never
   raw health data.
2. **The answer-audit gate.** See below.

Everything else — which role to dispatch next, what to ask the human, how to
phrase an answer — is agent judgment bound by the runtime contract, not code.

## Role declarations (guide, don't enumerate)

Roles register **declarations** in a bounded registry
(`premura.ui.roles`); the router is the registry plus the rule for adding an
entry, never an `if role == ...` ladder. A declaration carries:

- `role_id` — functional id (never a persona name)
- `job` — one-sentence runtime responsibility
- `surfaces` — governance surfaces / tool scopes the role may touch
- `handoff_outputs` — what it returns through the orchestrator
- `boundaries` — what it must not do (the assertion boundary)

The five reference roles — `ingest`, `analysis`, `human_facing`,
`answer_audit`, `improvement_scan` — ship as registry instances with the
jobs and boundaries the draft settled (ingest writes only through ingest
seams and surfaces gaps; analysis is read-only and names no causes;
human_facing never silently stores lifestyle context; answer_audit creates no
new evidence; improvement_scan writes only sanitized candidates). They are
examples of the contract, not a closed persona list: a new role is added by
registering a declaration that satisfies the fields above, with no central
edit. The orchestrator itself is not a role. Roles keep no private memory
across sessions; durable state lives only in explicit local stores.

Parser extension is not an operating role: parser-building is file-editing,
not a job the orchestrator dispatches through Premura's MCP tools. At runtime
an agent may build a parser and use it immediately for the operator's own
data with no reviewer; review gates only the optional contribute-back PR
(ADR 0010).

## The answer-audit gate (locked: blocking, deterministic core)

**Scope.** Any draft answer that interprets health data — comparison,
association, trend reading, next-step suggestion, PubMed-grounded narration —
is *health-interpreting* and must pass audit before presentation. Raw ingest
facts (row counts, load reports) are exempt.

**Mechanism.** Two tools on the default MCP surface:

- `answer_audit(draft, session_id)` — runs the deterministic checks below
  against the session's research trace and records the verdict (keyed by a
  hash of the draft) in the session log. It inspects; it never creates new
  evidence and never reruns analysis.
- `present_answer(draft, interprets_health, session_id?)` — the presentation
  gate. For a health-interpreting draft it **refuses** unless a passing audit
  verdict for exactly this draft is recorded; on success it returns the
  blessed envelope with the **measured search-effort disclosure attached by
  the gate itself** (computed from the trace, never trusted from prose) and
  the mandatory caveats. Non-interpreting drafts pass through marked as such.

The structural guarantee, stated honestly: no tool can stop an agent from
typing prose at a human. What the gate guarantees is that **anything carrying
Premura's verified envelope was audited, and anything that wasn't is visibly
not verified**. The runtime contract obliges operating agents to route final
health answers through `present_answer`; an agent that bypasses it is
violating its contract, and the absence of the envelope shows it.

**v1 deterministic checks (the gating core):**

1. A research-trace session is named for the draft, exists, and recorded
   analytical calls (no usable trace → the draft can only be presented with a
   prominent *not trace-verified* warning and downgraded, process-language
   claims — never as a verified health finding). Stated honestly: what v1
   verifies deterministically is that traced analysis happened in the named
   session. Binding each *individual claim* to the specific recorded calls it
   rests on is check 6 below (shipped slice 5); a claim written outside the
   recognized marker form stays the advisory rubric's territory.
2. The measured disclosure is computed from trace rows ("K user-facing
   findings among N unique hypotheses examined") and attached by the gate.
3. Refusals recorded in the session are not hidden: the verdict reports
   refusal counts, and the envelope discloses them.
4. Audit-fail routing: the orchestrator returns the draft to `human_facing`
   for one revision loop; remaining conflicts follow the fixed boundary
   priority `answer_audit` > `analysis` > `human_facing` — usefulness never
   overrides evidence.
5. **Citation binding (shipped slice 2):** every PMID the draft cites must
   have a *successful* in-session `pubmed_fetch`; search candidates and
   failed fetches are never citeable. The PubMed tools record into the
   research trace when given a `session_id` — as `call_kind =
   evidence_source` rows through the same record → dispatch → finalize seam
   the analytical tools use — and the multiplicity disclosure counts
   `analytical` rows only, so "N unique hypotheses examined" stays
   uncontaminated by literature lookups. What counts as "cites" is a fixed,
   documented extraction contract: a `PMID`/`PMIDs`/`PubMed ID` textual
   marker followed by one or more numbers, or a PubMed record URL on either
   host (`pubmed.ncbi.nlm.nih.gov/<id>`, legacy `ncbi.nlm.nih.gov/pubmed/<id>`).
   Stated honestly: a citation written outside those forms is **invisible to
   the gate** — so the runtime contract obliges operating agents to cite in a
   recognized form (the provider's own `pubmed_url` output is one), and the
   envelope's citation line scopes its own claim ("citations: none in the
   recognized PMID forms" / "K cited PMID(s) (recognized forms), all fetched
   this session") rather than asserting "none cited" outright. **Shipped:**
   the v1 advisory rubric now carries a citation criterion
   (`citations-verifiable-or-flagged`, `research-trace-audit`'s
   `AUDIT_RUBRIC.md`, `overclaim_boundary` category) that reads the out-of-form
   citations this gate structurally cannot see and flags them as advisory
   findings when the answer presents them as gate-verified without
   disclosure — it never gates and never restates check 5's own PMID-fetch
   binding.
6. **Claim-to-trace binding (shipped slice 5, [ADR
   0014](../adr/0014-claim-to-trace-binding.md)):** every claim the draft
   marks with a `[trace: <call_id>]` suffix must bind to a call this session
   recorded finishing `available`. The marker carries the recorded call(s) a
   claim rests on by `call_id` (`call_ab12`, comma-separated for several); a
   marked id that is unknown, belongs to another session, or names a
   refused/errored call is unbindable and **fails the gate** (named in the
   failures), the same fail-closed stance as an unfetched cited PMID. Unlike
   citation binding this does not filter on `call_kind` — a marker may rest on
   any `available` call, including an `evidence_source` row. What counts as a
   marked claim is a documented recognized-forms pattern set with an
   add-a-form rule (mirroring the PMID contract): the canonical
   `[trace: <call_id>]` suffix is the first and only shipped form. Stated
   honestly: a claim written outside those forms is **invisible to the gate**,
   so the runtime contract obliges operating agents to mark traced claims in a
   recognized form, and the envelope's claim line scopes its own coverage to
   *recognized marker forms only* ("claims: none in the recognized marker
   forms" / "K marked claim(s) (recognized forms), all bound this session") —
   never asserting total claim coverage. This is a new deterministic
   extractor-and-query pair **beside** check 5, never a fork of the audit flow.

The AI rubric (the existing research-trace-audit skill) runs **on top as
advisory only**; its judgment never gates in v1 and may be promoted later by
its own decision note.

**Slice 2 shipped citation binding** (check 5 above): PubMed trace
recording and the cited-PMID check landed together, as required. The shape
to preserve when adding a binding: a documented deterministic extractor over
the draft plus a bounded trace query it resolves against (cited-PMID →
fetched evidence row is the first instance) — a new binding adds its
extractor-and-query pair beside check 5, never a fork of the audit flow.

**Slice 5 shipped claim-to-trace binding** (check 6 above): the second
extractor-and-query pair beside check 5, landed as the shape above prescribes.
The open design question — what deterministically marks a "claim" in prose —
was answered by a maintainer design-interview (like the slice-1 promotion) and
**locked by decision note [0014](../adr/0014-claim-to-trace-binding.md)**: an
inline `[trace: <call_id>]` marker the runtime contract obliges the drafting
agent to emit, extracted by a documented recognized-forms pattern set
(`_extract_claim_trace_refs`) and resolved by a bounded per-marker trace query
(`premura.trace.bound_claim_calls` — the call exists in the named session with
`terminal_status = available`, no `call_kind` filter), fail-closed on any
unbindable marked claim, its disclosure line scoped to "claims in recognized
marker form only." A claim outside a recognized marker form stays the advisory
rubric's territory. **Advisory-rubric
citation criterion — shipped.** The research-trace-audit rubric's four
categories stay closed; adding a new *criterion* inside the existing
`overclaim_boundary` category is a normal rubric edit under the rubric's own
add-a-criterion rule, not a category-level spec amendment. The shipped
criterion (`citations-verifiable-or-flagged`) grounds only in quoted answer
spans — the Session Disclosure's `calls` list excludes `evidence_source`
rows by contract, so the criterion cannot and does not re-derive the
fetched-PMID set itself; it judges whether the answer's own wording
overclaims a citation's verification status, staying advisory and never
gating.

## Improvement scan, queue, sharing

The draft's improvement-queue item shape (`id`, `created_at`, `status`,
`kind`, `summary`, `suggested_action`, `privacy_level`, `trace_refs`,
`github_refs`; seeded kinds plus the rule for adding one) and the three
sharing levels (minimal / structural / synthetic example, with share packets
reviewed before any public GitHub write and real excerpts never committed)
are adopted into this spec unchanged. The dev-time boundary (build-and-use
needs no reviewer; only contribute-back is gated) is restated by decision
notes 0010/0013 and unchanged here.

**Slice 3 shipped the runtime queue itself** (the storage half, not sharing):
`improvement_scan` writes items through `improvement_queue_record` and reads
them back through the strictly read-only `improvement_queue_list`, both on
the default MCP surface. The item shape is exactly the draft's nine fields,
persisted in `log_improvement_item` — its own table in the session-log
store (ADR 0011), mirroring the handoff-trace seam slice 1 established. Two
fields carry a fixed vocabulary validated at the store boundary: `status`
(the draft's seven lifecycle values) and `privacy_level` (the draft's three
sharing levels — recording which one a candidate would need *if* it were
ever shared; slice 3 never reads this field to make a network call).
`kind`, by contrast, is a **bounded, open registry**
(`premura.ui.improvement_kinds`), never a fixed enum — the seeded six
(`parser_gap` / `analysis_gap` / `teaching_gap` / `workflow_gap` /
`docs_gap` / `other`) are examples, and `improvement_queue_record` registers
a new kind on the spot when called with a `kind_description`, so adding one
needs no central edit (DOCTRINE rule 2).

**This queue is PRIVATE and LOCAL by construction**, not by a lifecycle
gate: no code path in slice 3 reaches GitHub or any network — `github_refs`
is accepted and stored exactly as supplied, and nothing populates or reads
it to make a write.

**Slice 4 shipped share packets** — a generated, privacy-graded VIEW over one
stored queue item, mirroring `premura.trace`'s disclosure export pattern
exactly (`premura.share_packet.render_share_packet` + `share_packet_to_json`
/ `share_packet_to_markdown`, exposed as the default-surface MCP tool
`share_packet_render`). The item row stays canonical; a packet is never a
second copy of it. The three levels are the draft's:
`minimal` says only that a gap of the item's kind was encountered;
`structural` adds bookkeeping counts plus a couple of fabricated illustrative
field examples — the draft's named structural fields (source name, file type,
column names, units, error class) are not stored in the frozen nine-field
item shape, so they are not deliverable until the item shape evolves;
`synthetic_example` adds one fully fabricated record shaped
like a generic source export. Across ALL three levels the item's own
free-text `summary` / `suggested_action` is never echoed verbatim — that is
the actual PHI boundary, documented as a RULE beside each level's branch in
`premura.share_packet` rather than an enumerated allowlist (DOCTRINE rule 2);
fabricated content reuses the harness fixture generator's seeded-RNG and
`dim_metric.yaml` seams (FR-3) instead of inventing new fabrication code.
Producing a packet writes NOTHING to GitHub or off this machine — every
packet carries an explicit `notice` that publishing is a separate,
human-approved act (the Drive-upload two-acts split, mirrored here); this
slice ships packet production only, no GitHub API/posting code.

**Distinct from the harness-only `log_improvement` table.** Premura already
has an unrelated, dev-time-only improvement mechanism: the acceptance
harness's improvement hook (mission m4) derives proposals from an AI judge's
`log_judgment` verdict over one recorded repeatable-check/live-trial run,
keyed to a `judgment_id`, written only by the harness
(`premura.session_log.improvement_read` is its read surface). That table is
about *harness runs*, never touched by an operating agent. The runtime
queue described here (`log_improvement_item`) is about *live operating
sessions* — any operating agent may record an item mid-session through
`improvement_queue_record`, with no judgment or harness run involved. The
two tables share no rows, no code path, and no reader; a future agent that
wants "all improvement signal" reads both and says so explicitly.

## First build slice (locked)

1. Role-declaration registry with the five reference instances
   (`premura.ui.roles` — Stage 4's importable home; the UI-stage layering
   rule applies: no `hp.*` reads, no direct engine calls).
2. Handoff-trace tables + sole-writer functions in `premura.session_log`.
3. The blocking gate: `answer_audit` + `present_answer` on the default MCP
   surface, with the v1 deterministic checks and verdict storage above.

Out of slice 1: improvement queue, share packets, PubMed citation binding,
lifestyle-context capture, any UI beyond the tools themselves.
