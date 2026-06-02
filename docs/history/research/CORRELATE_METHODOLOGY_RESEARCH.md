# `correlate` — Scientific-Methodology Research Findings

> Status: pre-mission research input. Produced 2026-05-30 by a research agent to
> inform the future `correlate` mission spec and resolve the scientific choices
> deliberately left open by design decision note
> [`0008`](../../building/adr/0008-correlate-pre-registered-lagged-association.md). The
> architecture/honesty contract is settled in 0008; this note settles the
> *statistical* choices (coefficient, uncertainty band, sample floor, confound
> key, lag ceiling) and lists what the implementing mission must still pin down.

Scope: n-of-1 association between two prepared daily health series; deterministic
engine; no p-value, no "significant"; effect size + honest uncertainty band;
same-day pairing with caller-specified integer-day lag.

---

## Q1 — Coefficient choice

**Recommendation: default to Spearman's rho; do not offer Pearson as a user-facing choice. Optionally expose Kendall's tau-b as an advanced alternative.**

- Personal health series are outlier-prone (sick day, travel day, bad-sleep night), non-normal (RHR, training load, weight are skewed/heavy-tailed), and the true relationships are typically *monotonic but not linear*. Pearson assumes linearity and is the only one of the three with an **unbounded influence function** — a single outlier can arbitrarily move it. Spearman and Kendall have **bounded influence functions**, so they are robust to outliers and capture any monotonic relationship ([Croux & Dehon 2010](https://link.springer.com/article/10.1007/s10260-010-0142-z)).
- Spearman vs Kendall: both robust and roughly equally efficient. Kendall tau-b is marginally more robust with many ties and very small n and has a cleaner interpretation (probability of concordance minus discordance); Spearman is more familiar, faster, slightly more efficient on continuous data ([SAS/IML](https://blogs.sas.com/content/iml/2023/04/05/interpret-spearman-kendall-corr.html)).
- Distance correlation is not the honest default: always non-negative (no sign/direction), harder to explain, and poorly characterized under autocorrelation. The contract wants a signed, directional "they tend to move together / apart" — a monotonic-association measure.

Pick one; don't ask a non-expert to choose a coefficient. Default **Spearman**; surface **Kendall tau-b** only as an opt-in advanced flag (emit a note when the two disagree materially — itself a tie-heavy/short-series signal). Tradeoff: rank correlations discard magnitude, so a genuinely linear relationship reports a slightly attenuated effect vs Pearson — conservative, which is a feature here.

Sources: [Croux & Dehon 2010](https://link.springer.com/article/10.1007/s10260-010-0142-z) · [SAS IML blog](https://blogs.sas.com/content/iml/2023/04/05/interpret-spearman-kendall-corr.html)

---

## Q2 — Honest uncertainty without significance, corrected for autocorrelation

**Recommendation: report the point estimate plus an effective-sample-size–corrected interval via a Bartlett/Quenouille-type variance inflation. Simplest-yet-honest, composes with the no-p-value / deterministic constraints. Reserve block bootstrap as a future upgrade.**

### The autocorrelation problem (crucial finding)

Switching to a rank coefficient does **not** fix autocorrelation. When two individually autocorrelated series are paired, the sampling variance of *Spearman and Kendall* inflates exactly as Pearson's does — in a VAR(1) sim with AR(1)=0.8 and *no real dependence*, the naive rank test fired ~31% of the time instead of 5% ([Lun et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10557552/)). The band must be widened regardless of coefficient. This is the single most important point for the spec.

### The simplest honest correction (recommended for v1)

Compute an effective sample size and use it in place of n:

  **N_eff = N / (1 + 2·Σ_k ρ_xx(k)·ρ_yy(k))**

where ρ_xx, ρ_yy are sample autocorrelations of the two (rank-transformed) series summed over lags k — exactly the long-run-variance factor **σ̂² = 1 + 2·Σ ρ̂ˢˣ(h)·ρ̂ˢʸ(h)** ([Lun et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10557552/); foundational EDF treatment for Pearson in [Afyouni, Smith & Nichols 2019, *NeuroImage*](https://pmc.ncbi.nlm.nih.gov/articles/PMC6693558/)). Form the band by Fisher's z using N_eff (not N): SE_z = 1/√(N_eff − 3), back-transform to r-space. Both series autocorrelated ⇒ N_eff < N ⇒ SE grows ⇒ band widens.

Why this for v1:

- **Deterministic by construction** — closed-form, no resampling, byte-identical output.
- **Honest about *spread* without testing** — report the band, never threshold it. Frame as "plausible range given how little independent information this short, day-to-day-correlated window contains," not "95% confidence interval."
- Guards: clamp the autocorrelation sum (truncate noise lags, cap k ≈ N/4); **floor N_eff at ~4–5** so a near-random-walk can't break Fisher's z domain; raise `temporal_autocorrelation` when N_eff falls far below N (e.g. < N/2).

### Alternatives (rejected for v1)

- **Circular block bootstrap (seeded).** Can be made deterministic, but unstable at N≈30–120, adds a block-length knob, percentile CIs biased at small N. Later opt-in, not v1 ([FPP block bootstrap](https://otexts.com/fpp2/bootstrap.html)).
- **Prewhitening (ARIMA-filter, then correlate residuals).** On short series the fitted model is unreliable and it *changes what is being correlated* (innovations, not the metrics the human asked about). Literature says for limited data adjust DoF for effective sample size rather than fit a model ([Afyouni et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6693558/)). Reject.

### LOCF-imputed points

LOCF manufactures artificial autocorrelation (flat runs) and fake agreement. Two deterministic moves: (1) **down-weight imputed pairs in N_eff** (exclude imputed-on-either-side pairs from the numerator, or fixed fractional weight) — widens the band automatically; (2) **flag** `high_imputation` when imputed fraction exceeds a threshold.

Sources: [Lun et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10557552/) · [Afyouni, Smith & Nichols 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6693558/) · [block bootstrap (FPP)](https://otexts.com/fpp2/bootstrap.html)

---

## Q3 — Minimum paired-sample floor

**Recommendation: REFUSE below N_paired = 20. Report with a mandatory "short overlap / low sample" caveat in 20 ≤ N_paired < ~40–50. Treat autocorrelation-corrected N_eff, not raw N, as the real currency — refuse if N_eff < ~12 even when raw N clears the floor.**

- Correlation point estimates are wildly unstable at small n: the corridor-of-stability work shows trajectories only settle inside a ±0.10 corridor near ~250 for small effects (r≈0.2), dropping to ~50 only for strong effects (r≥0.7) ([Schönbrodt & Perugini 2013](https://www.psy.uni-muenchen.de/allg2/download/schoenbrodt/pub/stable_correlations.pdf)). Unattainable for n-of-1 daily overlap — a reason for humility and a non-trivial floor.
- **20** is the defensible hard minimum; below it the estimate carries essentially no information and the Fisher band spans nearly the whole range. Above 20 but below ~40–50, report **with** `low_sample_size` (+ `short_overlap_window` if the calendar window is short) — don't refuse, a clearly-hedged signal helps the non-expert.
- The floor must be checked on **N_eff**: a 60-day overlap of two near-random-walk series can have N_eff ≈ 8 and should be refused.

Tradeoff: 20 is conservative (one could argue 15); choose 20 because the failure mode is a confident-looking spurious association shown to a non-expert — refuse-by-default is the safer error.

Sources: [Schönbrodt & Perugini 2013](https://www.psy.uni-muenchen.de/allg2/download/schoenbrodt/pub/stable_correlations.pdf) · [2021 replication](https://www.researchgate.net/publication/352244123_Sample_size_and_stability_of_correlation_coefficients_A_replication_of_Schonbrodt_Perugini_2013)

---

## Q4 — Third-variable / common-cause confound key

**Recommendation: YES — add one dedicated key, `common_cause_plausible`.**

> `common_cause_plausible` — a third, unmeasured variable (a lurking/common cause) could plausibly drive both series, so the reported association may be confounded rather than a direct relationship between the two metrics.

- The lurking-variable / common-cause case is *the* canonical confound of correlation and is a different axis from everything in the vocabulary: existing keys are about data quality / estimator limits or interpretation context, none carries "the relationship itself may be spurious due to a third variable" — the *inferential* validity of the association ([Statistics By Jim](https://statisticsbyjim.com/basics/lurking-variable/); [Spurious relationship](https://en.wikipedia.org/wiki/Spurious_relationship)).
- It's the natural hook for an agent "consider X" note (RHR↔weight both rise during illness/training block) and reinforces association-not-causation at the data layer.
- Prefer `common_cause_plausible` over `lurking_variable` (jargon) or `confounded` (overclaims). Per "guide, don't enumerate": one rule-shaped flag, **not** an enumerated confounder list — candidate causes stay open and agent-supplied.

Sources: [Statistics By Jim — Lurking Variable](https://statisticsbyjim.com/basics/lurking-variable/) · [Spurious relationship (Wikipedia)](https://en.wikipedia.org/wiki/Spurious_relationship)

---

## Q5 — Lag justification threshold

**Recommendation: default unjustified-lag ceiling of ±3 days. Beyond |lag| > 3, require explicit caller-supplied justification; refuse (or hard-flag) otherwise. Hard maximum ~14 days even with justification.**

- Acute autonomic/cardiovascular responses largely resolve within ~1–2 days; HRV/RHR are suppressed acutely and recover over a day or two ([Whoop, HRV training](https://www.whoop.com/us/en/thelocker/heart-rate-variability-training/); [MDPI 2026 review](https://www.mdpi.com/1424-8220/26/1/3)). 0–3 days covers next-day/short-carryover effects.
- Cumulative effects (training-load buildup, sleep debt) appear over ~1–2 weeks but as *rolling-window* phenomena, not a single fixed k-day shift ([MDPI 2025](https://www.mdpi.com/2076-3417/15/19/10547); [PMC11768492](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11768492/)). A 10-day raw lag is a poor model of a cumulative process — which is *why* large lags should demand justification (often the honest answer is "use a rolling-window input, not a big raw lag").
- So: |lag| ≤ 3 free; 4–14 requires a stated rationale (recorded in metadata); > 14 implausible-without-strong-justification, hard ceiling. Pair any accepted large lag with a note that a fixed single-day shift may be the wrong model.

Tradeoff: 3 days is deliberately tight to discourage lag-fishing (complements the no-scan rule); could relax to ~7 if field experience shows legitimate next-week effects.

Sources: [MDPI 2026 HRV review](https://www.mdpi.com/1424-8220/26/1/3) · [MDPI 2025 training & HRV](https://www.mdpi.com/2076-3417/15/19/10547) · [PMC11768492](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11768492/)

---

## Open questions — for the implementing mission

1. **N_eff lag-truncation rule** (cap at N/4? first-noise-crossing? fixed max like 7?) and the N_eff floor value — must be specified exactly for byte-deterministic output.
2. **LOCF weighting scheme** — hard-exclude imputed-adjacent pairs vs fractional weight — and the `high_imputation` threshold.
3. **N_eff-based refusal threshold** — confirm N_eff < 12, and whether sub-floor N_eff is a refusal or a hard caveat when raw N clears 20.
4. **Spearman vs Kendall** — confirm Spearman default; decide whether Kendall ships in v1, and the disagreement-note threshold.
5. **Band presentation language** — exact non-expert wording so it never reads as a confidence/significance statement (the ban is on the *concept*, not just the word).
6. **`common_cause_plausible` trigger policy** — always, or only when a specific plausible candidate is identified (recommended, to avoid flag fatigue)? Rule must be written, not enumerated.
7. **Block bootstrap as future opt-in** — define deterministic seeding + block-length formula now for forward-compatibility.
8. **Marginal-band upper bound** — commit a single number for dropping the `low_sample_size` caveat (the ~40–50 figure).
