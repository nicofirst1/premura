# Design note (DRAFT): orchestrated operating-agent roles

> Status: **pre-spec exploration.** Not authoritative. Captures the resolved
> shape from the June 2026 design grilling session about a runtime multi-agent
> surface for operating Premura. No code decisions are locked; this exists so a
> future spec can start from shared language instead of re-deriving the framing.
>
> Companion reading: [`AGENTS.md`](../../AGENTS.md) §"two rules",
> [`docs/product/DOCTRINE.md`](../product/DOCTRINE.md),
> [`docs/architecture/STAGES.md`](../architecture/STAGES.md),
> [`research-trace-multiplicity-audit.md`](research-trace-multiplicity-audit.md),
> `src/premura/mcp/server.py`, `src/premura/engine/_registry.py`,
> `src/premura/parsers/CONTRACT.md`, issue #10 (end-to-end agent acceptance
> sandbox), and issue #12 (adversarial narration eval).

## What this is

Premura should have a runtime **orchestrator**: the dispatcher a human invokes
after Premura is installed. The orchestrator routes a health-data goal to
bounded **operating roles**, records their handoffs, and keeps the final answer
inside Premura's evidence and privacy boundaries.

This is **runtime only**. It is not the bootstrap/setup agent that prepares a
fresh clone, and it is not the dev-time Spec Kitty workflow used to change
Premura's code. Runtime may discover that a codebase extension would help, but
that becomes an improvement candidate and a dev-time handoff, not an operating
role.

## Settled vocabulary

- **Bootstrap agent**: setup-time agent for a freshly cloned repo. It reads docs,
  checks or installs dependencies and skills, and tells the user if a session reload
  is needed. It is separate from this plan.
- **Orchestrator**: runtime dispatcher for a human's health-data goal.
- **Operating role**: bounded runtime responsibility dispatched by the
  orchestrator.
- **Improvement candidate**: a concrete gap found during operation that may turn
  into an issue or dev-time workflow.
- **Improvement queue**: private global JSON queue for one user, storing
  sanitized improvement candidates across sessions.
- **Share packet**: the exact public issue/PR content shown to the human before
  posting.
- **Lifestyle context**: user-declared habits or circumstances that may matter
  later, but are not baseline profile context and need their own future capture
  design.

Avoid `operator` in this design. The repo already has an operator MCP surface
for lower-guarantee raw SQL, and `CONTEXT.md` uses human/operator language for
the person whose facts are being captured.

## Runtime shape

```
                              human
                                │ goal / source artifacts / question
                                ▼
                      ┌───────────────────┐
                      │   ORCHESTRATOR    │
                      │ route + sequence  │
                      │ trace + handoffs  │
                      └───────────────────┘
                         │    │     │     │
                         │    │     │     └── improvement_scan
                         │    │     └──────── answer_audit
                         │    └────────────── analysis
                         └─────────────────── ingest
                                │
                                └── human_facing presents, asks, revises
```

The orchestrator owns routing, sequencing, and trace. It does **not** become the
permission system. Permissions stay attached to governance surfaces and tool
boundaries.

Operating roles may stay alive during one user goal, but every cross-role
handoff goes through the orchestrator. Roles do not keep private memory across
sessions. The orchestrator also keeps no hidden memory; durable state must live
in explicit local stores such as trace, profile/lifestyle context, or the
improvement queue.

## Reference roles

Use functional role IDs, not persona names:

| Role ID | Runtime job | Surfaces / boundaries |
| --- | --- | --- |
| `ingest` | Load source artifacts, surface unsupported or unmapped source data. | May write warehouse data through ingest seams; emits `unmapped_metrics`, `skipped_rows`, refusals, and parser gaps. |
| `analysis` | Read warehouse signals and produce bounded descriptive/comparative results. | Read-only warehouse access; no diagnosis, causation, or unsupported statistical claims. |
| `human_facing` | Ask optional clarifying questions, explain results, encourage contribution, and present share packets. | Uses broad answers inside the current session; persists only through approved stores. Must not silently store lifestyle context. |
| `answer_audit` | Inspect the draft answer against trace and evidence before health interpretation is shown. | Read-only over trace and draft answer by default; does not create new evidence. |
| `improvement_scan` | Turn runtime friction into private improvement candidates. | Writes sanitized candidates to the local JSON improvement queue unless capture is disabled for the session. |

The orchestrator itself is not a role.

## Role declarations

Roles should register declarations rather than requiring a hardcoded router
switch. Minimum declaration:

- `role_id`
- task predicate
- allowed governance surfaces
- tool-scope predicate
- handoff outputs
- trace events
- assertion boundary

This mirrors Premura's existing pattern of bounded registries and rules for
adding entries. The first reference roles are examples, not a closed persona
list.

## Human-facing behavior

The human-facing role should ask the minimum required to route safely, then ask
targeted or optional broad questions only when they help the current answer.
Broad health-history questions are allowed as optional explained context, not as
mandatory medical intake.

Broad answers may be used within the current session without separate
permission. They must not be automatically stored as baseline profile context.
Non-profile facts such as caffeine habits, shift work, supplements, newborn
care, or training plans need a separate lifestyle-context design before they
become persistent product state.

When proposing issues or PRs, the human-facing role should explicitly say that
Premura is designed to improve from real use, and that the human does not need
to write the issue or PR themselves. It must also say that private health data
will not be included in public GitHub content.

## Answer audit

Mandatory runtime answer audit applies to any answer that interprets health
data, makes a comparison or association, suggests next steps, cites PubMed, or
wraps source-grounded medical/nutrition/athletic-performance information in
prose. Raw ingest facts can skip audit.

The audit inspects the draft answer and trace. It does not rerun analysis or
PubMed searches by default. If trace is missing or incomplete, the orchestrator
reruns under trace when possible. If rerun is impossible, the answer may only be
shown with a prominent "not trace-verified" warning, and the claim must be
downgraded to process/status language rather than an unverifiable health
finding.

If audit fails, the orchestrator routes the answer back to `human_facing` for
one revision loop. Remaining conflicts follow fixed boundary priority:

1. `answer_audit`
2. `analysis`
3. `human_facing`

That means usefulness cannot override evidence. A correct final answer may say
what cannot be concluded and what data would make the question answerable.

PubMed narration has stricter audit rules: cited sources must be traceable to
`pubmed_fetch`, search candidates are not citeable, and one fetched abstract must
not be inflated into broad medical consensus.

By default, health answers show minimal caveats only. The user can ask "show how
you got that" to receive a compact grounding disclosure. Audit pass/fail is not
shown by default unless there was a problem that affects the answer.

## Improvement scan and queue

The improvement scan runs when trigger signals appear, including refusals,
unsupported sources, unmapped metrics, skipped rows, answer-audit failures,
missing analysis capability, repeated handoff loops, or user confusion. A scan
does not have to create a candidate; some refusals are correct behavior, not
product gaps.

Candidates are saved automatically to the private local improvement queue unless
queue capture is disabled for that session. If disabled, the system can still
mention a blocking/relevant gap but does not persist it.

Queue items use simple JSON fields:

- `id`
- `created_at`
- `status`
- `kind`
- `summary`
- `suggested_action`
- `privacy_level`
- `trace_refs`
- `github_refs`

Statuses:

- `open`
- `issue_proposed`
- `issue_created`
- `pr_proposed`
- `pr_created`
- `done`
- `dismissed`

Seeded kinds:

- `parser_gap`
- `analysis_gap`
- `teaching_gap`
- `workflow_gap`
- `docs_gap`
- `other`

New kinds may be added when a recurring gap does not fit the seeded values and
the new kind has a short description. Deduplication is best-effort agent
behavior, not a storage guarantee. The queue should stay quiet by default:
mention relevant unresolved candidates only when they directly affect the
current task, or when new candidates are added.

## Public sharing and PR/issue flow

Public GitHub writes derived from a health-data session require a reviewed share
packet. This applies to issues, PR descriptions, comments, commits, fixtures, and
docs. Public GitHub content uses structural summaries and synthetic examples,
not real health excerpts.

Supported sharing levels:

1. Minimal: say only that an unsupported source artifact or gap was encountered.
2. Structural: include source name, file type, column names, units, error class,
   and synthetic examples.
3. Synthetic example: include a synthetic record shaped like the source artifact.

Real excerpts may be used only in private/local debugging with explicit approval
of the exact excerpt and destination. They must never be committed as fixtures,
examples, tests, or docs.

Default improvement path is issue-first. Parser gaps with a concrete source
artifact and clear contract path may proceed from issue to a user-approved
dev-time draft-PR workflow. The dev-time agent should prepare a branch and PR
text, then ask before creating the GitHub draft PR unless the user has already
granted repo-write automation.

## Dev-time boundary

Parser extension is not an operating role. Runtime can discover and describe the
need for a parser, produce a share packet, and ask whether to start dev-time
work. The actual code change remains outside the runtime orchestrator and goes
through the existing development/review process.

The separate bootstrap agent is also outside this plan. It deserves its own
issue: make a fresh clone agent-installable, including dependencies, project
skills, and any required session reload guidance.

## Traceability

The orchestrator records every dispatch and handoff with compact references, not
raw health data. Trace entry shape:

```text
from
to
task_summary
inputs_ref
outputs_ref
surface_touched
status
reason
```

Use the existing trace substrate as inspiration, but do not overload analytical
research-trace tables. Orchestrator events should live in a sibling trace layer
so they do not corrupt research multiplicity counts such as "N hypotheses
examined."

## Smallest real next step

Write an operating-role contract doc mirroring `parsers/CONTRACT.md`. It should
define the declaration fields, trace event contract, answer-audit boundary,
share-packet rule, improvement queue item shape, and the five reference roles as
instances. No code is needed for that first step.
