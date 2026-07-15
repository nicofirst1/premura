# premura — Changelog

> One block per released version, newest first, capability-level highlights only. The current-state snapshot (counts, tables, what works today) lives in [STATUS.md](STATUS.md); the per-change narrative history lives in git.

## 2026-07-14 — v1.0.0

The user-facing threshold: v1 tagged once the release-confidence gates closed.

- **Health answers explained safely to a non-expert.** A `human_facing` role presents findings only through the audited `present_answer` path, governed by the four-dimension `DISCLOSURE_RUBRIC.md` (calibration, gist fidelity, load management, boundary integrity) as an advisory drafting self-check — never diagnosing, naming a cause, or inventing an effect.
- **First-run interview that routes to real analysis.** An open registry of interview directions (sleep, cardio, metabolic, stress, mental, gut, lab, overview) resolves each chosen direction to a signal selector; a direction with no live analysis behind it is refused rather than offered, so the interview never leads to a dead end. Exposed as `interview_route`.
- **Adversarial release-confidence acceptance.** An `adversarial_narration` acceptance tier judges hostile health prompts against the rubric's boundary-integrity criteria, with refusal as a first-class pass; the suite was parallelized (~3x) after fixing an engine module-reload leak (#85, #87).
- **Answer-audit hardened.** The gate now binds individual draft claims to the analytical calls they rest on (`[trace: …]` markers), verifies every cited PMID was actually fetched in the session, and flags out-of-form citations — all fail-closed through the single revision loop.
- **Runtime improvement queue + shareable gaps.** Runtime friction (refusals, unmapped metrics, audit failures) becomes a durable private improvement item any operating agent can record and read back; an item can be rendered as a privacy-graded share packet, with publishing kept a separate human-approved act.
- **Wider reach and a public front door.** Withings CSV as the first real observation-seam vendor and an AI-chat supplement/medication recall intake source (#23, #33); operator-declared condition episodes persisted so off/on questions stop re-declaring; per-app MCP setup for Claude Code, OpenCode, and Codex (#22); Apache-2.0 license with a plain-language "not medical advice" disclaimer (#15).

## 2026-06-12 — v0.4.0

Seven additive feature missions consolidated and tagged; the analytical tool set and first real vendor parsers landed here.

- **The full analytical tool set (six deterministic tools).** `change_point`, `smoothed_average`, `correlate`, `rolling_mean`, `paired_t_test`, and `condition_paired_t_test` — each routed through the same admissibility gate and result envelope, reporting associations and paired differences with honest uncertainty bands, never a p-value, never "significant", never a cause.
- **Correlate as a pre-registered lagged association.** A signed Spearman association over a caller-declared, never-scanned whole-day lag, with an autocorrelation-corrected effective sample size and a conservative refusal floor.
- **Session research trace + measured multiplicity disclosure.** An append-only ledger at the MCP boundary records the analytical calls a research session dispatches and derives "K findings among N unique hypotheses examined" from real rows, backed by the stable audit-consumer contract.
- **First real vendor parsers.** MyFitnessPal on the intake seam and PubMed literature-grounding tools (search returns candidates only; only a fetched record is citeable) both shipped, proving the federated parser and citation seams end to end on real export formats.
- **Self-improving harness.** The cheap-model live trial gained conversation-turn capture, an opt-in local-model judge scoring runs against a versioned rubric, an improvement hook turning verdicts into proposals, a deterministic synthetic-fixture generator, and an analyze-and-answer task kind graded for honesty and grounding.
- **Operating surface follow-ups.** `premura inspect` routing preview, `premura gc --dry-run`/`--raw`, and a warehouse `unit` column for intervals sourced from the metric registry.

## 2026-06-04 — v0.1.0 and earlier — foundation

The v1 ingest pipeline through the Stage 2/3 analytical foundation. The historical `v1.0.0` tag marks the ingest pipeline as a restore point; the product line was treated as `v0.x` until the user-facing threshold above.

- **Four-source local ingest.** Health Connect, Garmin GDPR, Sleep as Android, and BMT into a local DuckDB warehouse with idempotent re-ingest, cross-source dedupe, encrypted (`age`) monthly export artifacts, and the `premura` CLI. Drive upload is opt-in, never part of the unattended monthly run; the private key stays local.
- **Profile and intake storage with agent-mediated capture.** Concrete domain tables give profile facts and nutrition/supplement intake a one-home store; a bounded allowlist captures profile facts one at a time (append/supersede, history kept), making BMI the first cross-domain Stage 2 signal. Both intake domains resolve through the existing seam as first-class agent-usable dimensions.
- **Evidence-admissibility policy layer.** A deterministic gate decides which evidence is admissible for a question before any tool uses it — rejecting stale evidence presented as if it described the present — and refuses clearly when none remains.
- **Stage 3 analytical tools, first slices.** The bounded analytical contract with `change_point` and `smoothed_average`, first-class analytical question types, and a mandatory result envelope with a closed confound vocabulary so agents cannot mint their own quality labels.
- **Session-log substrate + build-and-use doctrine.** A per-run PHI-bearing session log, a runtime-contract checker, a deterministic grader that recomputes every rule from ground truth (never trusting a parser's self-report), and a cheap-model live-trial seam. The settled boundary: at runtime an agent may build a parser and use it immediately for the operator's own data with no reviewer; review enters only for an optional contribute-back PR.
- **Research-trace audit skill + fresh-clone bootstrap.** A Premura-specific skill judging one answer against its session trace disclosure via a bounded rubric, and `uv run premura bootstrap` to prepare and verify a fresh checkout.
- **Engineering safety net.** CI on every push/PR (lock check, ruff, mypy, pytest), a tracked-data guard, and a `premura doctor` backup round-trip check (#16, #18, #19, #20).
