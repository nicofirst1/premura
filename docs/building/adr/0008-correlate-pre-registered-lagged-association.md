# Correlation reports a pre-registered, lagged *association* — never significance — and pushes multiplicity accounting out to a session-layer audit trace

`correlate` is the first **multi-input** Stage 3 analytical tool (Phase 3,
`v0.3 analytical depth`). It sits on the admissibility contract from
[ADR-0007](0007-evidence-admissibility-as-a-declared-contract.md) and the
analytical result/confound contract shipped by the stage-3-analytical-tools
mission. Because it relates *two* metrics over time, it is the first place where
the n-of-1 dangers the project keeps guarding against — spurious correlation,
autocorrelation, multiple comparisons, and causal over-reading — all arrive at
once. This note records the shape the tool is taking and why, so the
implementing mission (and the audit/trace mission after it) extend it
consistently instead of re-deciding. The *statistical* choices (which
coefficient, how to express and widen uncertainty, the paired-sample floor) are
deliberately **not** settled here; they are delegated to a research
investigation and will be recorded separately.

The decisions:

- **Pairing is by same local calendar day; a relationship across time is modeled
  as a directional, caller-specified *lag*, never a symmetric tolerance and never
  a scan.** Two observations pair iff they fall on the same calendar day; the
  `overlap` window of the prepared series then means "the days both metrics were
  actually measured." A delayed relationship (lactose today → gut symptoms a day
  later; a hard training day → suppressed overnight HRV tomorrow — both
  physiologically real, see the mission research note) is expressed by shifting
  one series by a whole number of days and pairing on the same day again. Lag is
  **asymmetric and caller-declared**, defaulting to 0. It is the opposite of a
  "close-enough timestamp" tolerance, which would blur direction, double-count,
  and rest on an arbitrary fudge. (See `Lag` and `Association` in
  [CONTEXT.md](../../../CONTEXT.md).)

- **The lag is hypothesis-driven, and large lags require justification the
  *agent* supplies — the deterministic engine never does research.** Beyond a
  small unjustified range (the exact threshold is a research/spec detail), a
  requested lag is refused unless the caller passes an explicit justification,
  which the agent obtains by doing literature research *outside* the engine. The
  engine remains pure: stateless, deterministic, no clock, no network. This is
  also the first natural hook for the later PubMed-grounding work.

- **Never scan lags and keep the best fit.** Choosing the lag (or metric pair)
  that maximizes the coefficient *manufactures* a correlation — it is p-hacking
  by another name and the "statistical theater" the roadmap forbids. A lag is a
  hypothesis to test, not a parameter to optimize.

- **Every call is *pre-registered*.** The caller must declare its hypothesis —
  metric pair, lag, and *expected direction* — as a mandatory input, recorded
  *before* the result exists. Declaring the expected direction before seeing the
  outcome is the strongest anti-p-hacking discipline that costs no state, and it
  guarantees "no lie": an agent can never retroactively claim it predicted what
  it found. The declaration is the stable identity a later audit trace counts
  over.

- **Results report *association*, with an effect size and an honest uncertainty
  band — never a p-value and never the word "significant."** This is not a
  display rule; the tool must not *compute or return* a significance, so a
  narrating model cannot launder one into false certainty (the mirror of R7's
  "return CIs/effect sizes so the model cannot fabricate them"). The reasons a
  p-value is refused here, in increasing severity: (1) on autocorrelated,
  non-stationary, multiply-tested personal time series the number would be
  **numerically false** — the effective sample size is far below n, so any
  honestly-computed p-value overstates certainty; (2) "significant" does
  importance/causal rhetorical work the data cannot back, which is exactly the
  health-context harm the project exists to prevent; (3) frequentist significance
  is a *category error* for one person's life — there is no repeated-sampling
  frame. The uncertainty band we *do* report must be widened for
  autocorrelation/imputation (or carry the `temporal_autocorrelation` /
  `high_imputation` confound) rather than claim clean 95% coverage — otherwise it
  is the same lie in softer clothes. The rule is matched to the *data-generating
  process*, not dogma: significance could be valid in a properly designed,
  randomized n-of-1 *trial* with washout, and that — not observational
  correlation — is the moment to revisit it.

- **Multiplicity / p-hacking accounting is a stateful, session-layer concern,
  split into a following mission.** Per-call honesty cannot see an agent that
  ran 47 hypotheses and surfaced the one that fit; that is a property of the whole
  investigative session. The honest response is **disclosure of search effort**
  ("the 1 notable result among 47 examined"), not a fake multiplicity-corrected
  statistic (which we couldn't compute honestly, having refused the p-value, and
  which is meaningless when the tests are non-independent). That accounting needs
  *state*, so it lives one layer out — a **session-scoped test ledger / reproducible
  research trace at the MCP boundary** — keeping the analytical engine stateless.
  The count must be **measured, not self-reported**, for the same reason ADR-0007
  refuses to trust the operating agent's judgment. An **audit skill** consumes the
  trace; it is the per-user, per-session twin of the agent-acceptance sandbox
  (issue #10), and can turn findings into issues / PRs / suggestions.

This combination won because each alternative reopens a problem the project is
explicitly trying to avoid:

- **A symmetric tolerance window** (the original framing) conflates measurement
  clock-drift with physiological delay, hides direction, and bakes in an arbitrary
  tolerance. Directional integer-day lag is both more honest and strictly more
  expressive.
- **Auto-selecting the best lag** is the single most likely way this tool would
  produce a confident falsehood; forbidding it is non-negotiable.
- **Reporting significance** is the canonical instrument of statistical theater
  and, on this data, often numerically wrong — the opposite of honest n-of-1
  analysis.
- **A stateful engine** would break the determinism invariant the whole analytical
  layer depends on; **self-reported test counts** would rest safety on the
  agent's honesty, which the project's threat model (any agent, including a weak
  or careless one, may operate Premura) refuses to do.

Consequences and forward-compatibility: the contract's `dispatch(*args, **kwargs)`
is already variadic, so passing two prepared series needs no shape change;
`AnalyticalToolSpec.input_shape` gains a paired value; the
`overlap_start/overlap_end/overlap_sample_size` fields — left explicit on
`AnalyticalInputSeries` for exactly this — are finally narrowed to the
intersection of the two series. `correlate` adds a new first-class
`AnalyticalQuestionType` (a reviewed change, with its own freshness/sufficiency
`QuestionRules` on the relevant family policies) rather than reusing a
single-series shape. Whether the closed confound vocabulary needs **one new key**
for the third-variable / common-cause risk (the defining correlation confound,
only partly covered by `life_event_sensitive`) is an open question for the
implementing mission — and, like the question types, would be a reviewed
extension, not an ad-hoc string. *(Resolved: the answer was yes —
`common_cause_plausible`, the rule-shaped lurking/common-cause flag settled by
the research note ([`CORRELATE_METHODOLOGY_RESEARCH.md`](../../history/research/CORRELATE_METHODOLOGY_RESEARCH.md)
Q4) and shipped on the closed `ConfoundKey` vocabulary in the
`correlate-lagged-association` mission, 2026-05-30.)* The pre-registered-hypothesis input and the
provenance it lands in are the seam the later audit-trace mission builds on
without a breaking change.
