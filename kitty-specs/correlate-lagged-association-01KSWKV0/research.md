# Research: Correlate Lagged Association

## Decision: Use Spearman's rho as the only v1 coefficient

**Rationale**: The research note finds personal health series are outlier-prone,
non-normal, and usually monotonic rather than cleanly linear. Spearman is robust,
signed, familiar, deterministic, and easier to explain than alternatives.

**Alternatives considered**: Pearson is too outlier-sensitive and implies a
linear model. Kendall tau-b is reasonable but would add a method menu and
disagreement policy in the first multi-input tool. Distance correlation is
unsigned and harder to narrate as an association.

## Decision: Pair by same local calendar day after one declared integer-day lag

**Rationale**: ADR-0008 locks lag as a directional physiological delay, not a
symmetric measurement tolerance. Pairing after one declared lag keeps the tool
hypothesis-driven and inspectable.

**Alternatives considered**: Symmetric timestamp tolerance blurs direction and
adds an arbitrary fudge factor. Lag scanning manufactures a strongest result and
is explicitly out of scope.

## Decision: Require pre-registered hypothesis before computation

**Rationale**: Metric pair, lag, and expected direction must exist before the
result so an agent cannot retroactively claim it predicted what it found.

**Alternatives considered**: Optional hypothesis metadata would rely on agent
discipline. Post-result annotation would not prevent p-hacking narration.

## Decision: Use effective sample size for the association band

**Rationale**: Rank correlation does not remove temporal autocorrelation. The
association band must widen when paired series carry less independent
information than raw paired days imply. The v1 rule uses rank-transformed sample
autocorrelation terms through lags `1..min(7, floor(raw_paired_sample_size / 4))`
to keep output byte-deterministic.

**Alternatives considered**: Block bootstrap is deferred because it adds block
length and resampling complexity. Prewhitening changes the thing being compared
and is unreliable on short personal series.

## Decision: Refuse below 20 raw pairs or effective sample size 12

**Rationale**: Below 20 paired days the estimate is too unstable to show a
non-expert. Even with enough raw pairs, heavily autocorrelated series can have
too little independent information; `N_eff < 12` is a refusal rather than a
caveat.

**Alternatives considered**: A lower raw floor such as 15 was rejected because
the safer error is refusal. Treating low `N_eff` as a caveat was rejected because
the band can otherwise look more informative than the data support.

## Decision: Emit marginal-support caveats below 50 raw pairs or 30 effective sample size

**Rationale**: The research note recommends a marginal band around 40-50 raw
pairs. Choosing 50 makes the cutoff deterministic and conservative. Effective
sample size below 30 also needs visible caution even when the hard floor is met.

**Alternatives considered**: A fuzzy "around 40-50" rule is not reviewable or
byte-deterministic. Refusing all marginal cases would hide potentially useful but
clearly hedged n-of-1 signals.

## Decision: Count imputed pairs at half weight and flag high imputation at 20%

**Rationale**: LOCF and other accepted imputation can manufacture apparent
agreement. Half weighting keeps imputed pairs visible without treating them as
fully independent support. A 20% imputed-pair threshold is strict enough to warn
early while still allowing sparse accepted windows to be evaluated.

**Alternatives considered**: Hard-excluding every imputed-adjacent pair could
turn many accepted analytical inputs into refusals despite upstream policy
allowing them. Full weighting would overstate support.

## Decision: Emit `common_cause_plausible` only when a candidate is pre-declared

**Rationale**: Common-cause risk is the central correlation confound, but always
emitting it would create flag fatigue. Requiring a caller-supplied candidate keeps
the rule open-ended without enumerating possible causes.

**Alternatives considered**: Always emit the key for every correlation result; it
is safe but too noisy. Enumerating known common causes is rejected by doctrine.

## Decision: Keep block bootstrap as a future deterministic extension

**Rationale**: The v1 method is deterministic and simpler. The result shape
should not block future bootstrap support, so the forward-compatibility rule is a
hypothesis-derived seed and block length `ceil(sqrt(raw_paired_sample_size))`.

**Alternatives considered**: Implementing bootstrap now would expand scope and
introduce extra parameters before the first paired-input seam is proven.

## Decision: Use "association band" wording

**Rationale**: The phrase communicates uncertainty around association strength
without implying significance testing or clean repeated-sampling coverage.

**Alternatives considered**: "Confidence interval" risks importing p-value
theater by implication. "Plausible range" is useful prose but less specific as a
machine-facing payload name.
