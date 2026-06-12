# First full-stack live trial — v0.4.0 harness, real local models

> Follow-up in the live-trial series
> (2026-06-03 first-real-model spike → 2026-06-04 tool-loop 14B follow-up →
> this). First time the entire v0.4.0 self-watching chain ran together with
> real models: fixture generator (m5) → tool-loop operator tier → transcript
> capture (m2) → AI judge (m3) → improvement hook (m4). Run the same day
> v0.4.0 merged, against master `d4b6985`. Throwaway driver script (not
> committed); kept artifacts under git-ignored `data/live_trials/`.

## Setup

| Field | Value |
|---|---|
| Fixture | generated, seed 42 → `qelband.csv` (3 cols, 1 mapped: `sensorOneReading` → `lab:hdl`) |
| Run A operator | `qwen2.5-coder:14b` (the tier's default model family) |
| Run B operator | `mistral:7b-instruct` |
| Judge (both) | `qwen2.5-coder:14b` |
| Outcome (both) | 8 turns, first-parser FAIL, final FAIL, judgment `complete` (all criteria weak), 4 improvement proposals |

## Headline

**The chain held end-to-end — no crash, honest verdicts, judge and
improvement hook produced sane output on their first real exercise — but
neither pulled local model can actually operate the tool loop, and the run
surfaced four real harness defects that per-mission reviews could not see.**
This repeats the 2026-06-04 lesson exactly: the blocker is harness plumbing,
not model capability tier.

## What worked (first real exercise for most of it)

- m5 fixture: valid, never-seen, registry-drawn, accepted by the grader
  machinery unchanged; the synthetic marker correctly made the runs
  persistable (runs + scoreboard rows under `data/live_trials/`).
- Tool registry dispatch: a native tool call executed and an allowlist
  refusal came back correctly (Run B turn 3–4).
- m2 transcript capture: both conversations persisted faithfully through the
  sole-writer harness, readable post-run via the dossier.
- m3 judge: `complete` on both runs; correctly banded both sessions weak,
  caught the thrashing and the text-claimed-success-without-evidence
  pattern; `analytical-claims-match-engine` correctly `not_applicable`.
  (Run A quirk: `overall_band` came back NULL despite per-criterion bands.)
- m4 improvement hook: four proposals per run, each mapped to the right
  playbook area, idempotency flags correct.
- Safety contracts: cap exhaustion → graded FAIL → judged → proposals, no
  exception ever escaped, no verdict flipped by the post-run steps.

## Harness defects found (each invisible to per-WP review)

1. **m5↔tool-loop seam: generated scenarios cannot run.**
   `fixture_gen.scenario_for` documents a scenario "the harness accepts",
   but the live-trial entry resolves drawer probes by **scenario name**
   against the closed two-entry `_DRAWER_PROBES` registry
   (`src/premura/harness/live_trial_ollama.py`), so `generated:<name>`
   raises `KeyError` before any model runs. The probe's `goal` is also
   hardcoded to the committed fixture ("heart-rate … Fitbit CSV"), wrong for
   any generated fixture (here: an HDL lab metric from "qelband"). The two
   missions merged through different paths; nothing ever ran them together.
   Workaround used: register a probe per the registry's own add rule with a
   fixture-derived goal. Durable fix: generated scenarios should resolve to
   their drawer's probe (they carry the strategy) with a generated goal.
2. **Content-borne tool calls are silently treated as "no tool calls".**
   `qwen2.5-coder` (7b **and** 14b — i.e. the tier's `DEFAULT_MODEL` family)
   never emits native Ollama `tool_calls`; it puts the call JSON in
   `content` (verified standalone against `/api/chat`, Ollama 0.30.7, tool
   template present). The loop only reads `reply["tool_calls"]`, so every
   such turn degrades to a gate round: in Run A the model executed **zero**
   tools across 8 turns — it never saw the CSV — while making sensible moves
   (read → write → run → rewrite, with a blind parser draft that used the
   real `IngestBatch` API). The default configuration of the tier therefore
   cannot work today. Fix options: a fenced-JSON fallback parser in the
   loop, or at minimum corrective feedback ("your tool call was not
   recognized; emit native tool calls") instead of a gate round.
3. **Absent-parser gate feedback is unactionable.** When no parser was ever
   written, the gate feeds back the harness's own internal traceback
   (`ModuleNotFoundError: premura.parsers._live_trial_parser`) verbatim,
   eight times. The model is told to fix an import it never wrote. It should
   say: "no parser is on disk yet — write one with `write_parser`."
4. **Availability probe misreports cold models.** `ollama_available()` pings
   `DEFAULT_MODEL` with a 10s timeout regardless of the model the run was
   asked for; under model-swap load it timed out and the run aborted as
   `model_unavailable` while Ollama was up and serving.

## Capability-floor reading (with defect 2 in mind)

- `qwen2.5-coder:14b`: right coding instincts, wrong tool transport — it is
  exactly the model the fenced-JSON fallback would unlock.
- `mistral:7b-instruct`: right tool transport (native calls work), wrong
  everything else — hallucinated an off-task first turn, pasted its parser
  as markdown prose instead of calling `write_parser`, repeated the same
  turn five times. A genuine floor result, not plumbing.
- Net: today no pulled local model passes the tool-loop tier; the
  highest-leverage move is defect 2, which re-admits the coder family before
  any "bigger model" conversation.

## Judge quality note

Directionally right on both runs, with one soft spot: some evidence strings
are plausible-but-loose paraphrases (Run A's "repeatedly claimed success"
overstates what the transcript shows — tool-call attempts, not success
claims). Fine for proposal derivation; worth remembering when judgments are
read as ground truth. This is the adversarial-narration concern of issue #12
showing up in the judge itself.
