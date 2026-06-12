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
   session — it cannot verify that the draft's *claims* rest on those
   specific calls. Binding each claim to the recorded calls it rests on is
   the advisory rubric's territory until promoted, and deterministic
   claim-to-trace binding is named later-slice work below.
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
   the gate**, and the v1 advisory rubric has no citation criterion either —
   so the runtime contract obliges operating agents to cite in a recognized
   form (the provider's own `pubmed_url` output is one), and the envelope's
   citation line scopes its own claim ("citations: none in the recognized
   PMID forms" / "K cited PMID(s) (recognized forms), all fetched this
   session") rather than asserting "none cited" outright. Wiring a citation
   criterion into the advisory rubric is named follow-up work below.

The AI rubric (the existing research-trace-audit skill) runs **on top as
advisory only**; its judgment never gates in v1 and may be promoted later by
its own decision note.

**Slice 2 shipped citation binding** (check 5 above): PubMed trace
recording and the cited-PMID check landed together, as required. The shape
to preserve when adding a binding: a documented deterministic extractor over
the draft plus a bounded trace query it resolves against (cited-PMID →
fetched evidence row is the first instance) — a new binding adds its
extractor-and-query pair beside check 5, never a fork of the audit flow.

**Named later-slice work (so it is not assumed shipped):**
**claim-to-trace binding** — deterministically tying the draft's individual
claims to the specific recorded calls they rest on. Today check 1 proves
only that the named session recorded analytical work — an audited draft
could in principle cite a session whose calls are unrelated to its claims;
the advisory rubric is what reads the draft against the trace content until
binding is promoted by its own decision note (the open design question —
what deterministically marks a "claim" in prose — needs a maintainer
design-interview, like the slice-1 promotion got). **Advisory-rubric
citation criterion** — the research-trace-audit rubric's categories are
closed by its own contract, so teaching it to read out-of-form citations is
a spec amendment of its own, not a rubric edit; until then out-of-form
citations are covered by the runtime contract's cite-in-recognized-form
obligation, not by any checker.

## Improvement scan, queue, sharing (specified, later slices)

The draft's improvement-queue item shape (`id`, `created_at`, `status`,
`kind`, `summary`, `suggested_action`, `privacy_level`, `trace_refs`,
`github_refs`; seeded kinds plus the rule for adding one) and the three
sharing levels (minimal / structural / synthetic example, with share packets
reviewed before any public GitHub write and real excerpts never committed)
are adopted into this spec unchanged. They build in later slices; the
dev-time boundary (build-and-use needs no reviewer; only contribute-back is
gated) is restated by decision notes 0010/0013 and unchanged here.

## First build slice (locked)

1. Role-declaration registry with the five reference instances
   (`premura.ui.roles` — Stage 4's importable home; the UI-stage layering
   rule applies: no `hp.*` reads, no direct engine calls).
2. Handoff-trace tables + sole-writer functions in `premura.session_log`.
3. The blocking gate: `answer_audit` + `present_answer` on the default MCP
   surface, with the v1 deterministic checks and verdict storage above.

Out of slice 1: improvement queue, share packets, PubMed citation binding,
lifestyle-context capture, any UI beyond the tools themselves.
