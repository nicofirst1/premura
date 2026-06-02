# Treat evidence admissibility as a declared contract with domain packs, health first, pure-declarative in v1

Premura is operated and extended by agents, and its core safety problem is not
just generic model error — it is an agent using the *wrong* evidence for a
question (stale, too sparse, or the wrong kind) and stating it with confidence
(see [DOCTRINE.md](../../shared/DOCTRINE.md) and
[`STAGE2_EVIDENCE_ADMISSIBILITY_RESEARCH.md`](../../history/research/STAGE2_EVIDENCE_ADMISSIBILITY_RESEARCH.md)).
A deliberate search of the public record
([`AGENT_OPERATED_SOFTWARE_PRIOR_ART.md`](../../history/research/AGENT_OPERATED_SOFTWARE_PRIOR_ART.md))
found that the building blocks exist in pieces, but nothing off-the-shelf
decides *whether a piece of personal-health evidence is admissible for a given
question* in a deterministic, reviewable way. The Stage 2 Evidence Admissibility
Foundation mission (`stage-2-evidence-admissibility-foundation-01KSSR40`, now in
implementation) builds the first version. This note records the shape that work
is taking and why, so later missions extend it consistently instead of
re-deciding.

The decision:

- **Admissibility is a *declared contract checked by a deterministic evaluator*,
  not a hardcoded table and not a model judging another model.** A small set of
  *policy classes* describe, per *metric family*, which question types the
  family can honestly support, how fresh and how dense the evidence must be, what
  provenance is required, and when to refuse. A deterministic evaluator reads
  those declarations and labels each candidate piece of evidence `admissible`,
  `rejected`, or `insufficient`, with a reason drawn from a closed list
  (`stale_for_question`, `wrong_evidence_kind`, `too_sparse`, `missing_provenance`,
  …). Same warehouse state + same request + same policy version → same result.
- **Health is the first *domain pack*, not the whole design.** The general core
  — the contract shape, the outcome words, the evaluator — is domain-agnostic.
  What is health-specific (the question types such as current-status vs
  long-term-control, the evidence kinds, the per-family freshness and
  sufficiency rules) lives in a health pack that *fills in* the core's closed
  vocabularies. A second domain would arrive as a new pack, not as new branches
  inside the evaluator. This keeps the door open to generality without paying for
  it before a second domain actually exists.
- **Separate temporal meaning from freshness.** "This marker integrates over
  months" (what the number means) is recorded distinctly from "this reading is
  current enough for N days" (how recent it must be). Conflating them is the most
  common way these rules go wrong.
- **v1 policies are pure-declarative: values only, no embedded logic.** A policy
  may set fields (a window in days, a minimum count, a required provenance field,
  a refusal mode) chosen from closed vocabularies. It may **not** contain
  expressions, conditions, or code. All combining logic lives in the evaluator.
  If a real family needs a rule the fields cannot express, the disciplined
  response is, in order: (1) add a new *typed field* to the contract, or (2) only
  if ad-hoc fields keep multiplying, revisit this decision and consider a small,
  sandboxed expression form as a deliberate v2 change. The tell that v2 is needed
  is when policies start needing boolean *combinations* of conditions
  ("this OR that"), not just independent thresholds.

This combination won because each alternative reopens a problem the project is
explicitly trying to avoid:

- **Enumerating a policy for every metric and question** would not scale, would
  be unreviewable, and contradicts the project's "design a level above — guide,
  don't enumerate" rule (DOCTRINE.md). Policy classes over families are the
  abstraction; representative families are delivered, not an exhaustive table.
- **A probabilistic truth-check** (one model scoring whether another model's
  answer is supported) is exactly what every shipping "fact-checking" guardrail
  does today, and it is non-deterministic and not auditable — the opposite of
  what a health context needs. Turning "is this true?" (undecidable in general;
  see Xu et al. 2024, "Hallucination is Inevitable") into "is this evidence
  *admissible*?" (a checkable structural property) is the only dependable path.
- **A general expression language now** would buy flexibility at the cost of
  reviewability — the one property that makes agent-authored policies safe to
  accept — and would be premature generality drawn from a single domain.

The deeper reason for the hard constraint: **Premura does not control which
agents operate it.** A low-capability or careless agent could run here. Safety
therefore cannot rest on the agent's judgment; it must live in the substrate.
The pure-declarative form is a floor — even a weak agent physically cannot
introduce unsafe logic, because there is nowhere to put it. The design target is
the least-capable agent that could plausibly run here, not the most capable.

The primary risk being optimized against is **the system stating something
wrong** (not the system taking a destructive action), made worse because the
human beneficiary typically has no medical knowledge to catch the error. The
governing consequence: **when evidence is not admissible, refuse — "not enough
trustworthy evidence to say" — rather than produce a hedged answer.** A
hedged-but-wrong statement is more dangerous than a refusal when the reader
cannot tell the difference, so the bias is conservative: silence over a shaky
guess, and the evidence layer's job is to *withhold* untrustworthy evidence, not
to caveat it into use.

Consequences: the evaluator runs as a Stage 2 engine function behind the
existing "no raw fact reads; go through the engine" boundary; it *labels*
evidence rather than gating the agent's words directly, so later surfaces are
contractually limited to narrating over `admissible`-labelled evidence. The
result shape and policy-class vocabulary are meant to be referenced by the next
deterministic-tools mission without breaking changes.
