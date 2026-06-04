# Live-trial tool-loop + multiturn follow-up (14B) — 2026-06-04

> **Where this sits:** a second data point inside **issue #10** (end-to-end agent
> acceptance sandbox / capability-tier sweep), following
> [`2026-06-03-live-trial-first-real-model-spike.md`](2026-06-03-live-trial-first-real-model-spike.md)
> and the merged `cheap-operator-live-trial-01KT6PSA` slice. It exercises the
> live-trial seam of the design note
> [`docs/building/planning/agent-interaction-audit-substrate.md`](../../building/planning/agent-interaction-audit-substrate.md)
> with (a) a real cheap operator one-shot and (b) a throwaway tool-using,
> multiturn loop. **Reconstructed from the working session record** — the spike
> scripts were throwaway local files (`/tmp/premura_toolspike/`), not committed
> code; the durable conclusion is below and in agentmemory (`mem_mpz9i6gg`).

This note carries a **reversal**: a first read of the tool-loop spike concluded
"the cheap operator is below the floor, the tier needs a frontier model"; a
clean re-test showed that was a **harness-context artifact**, not a capability
limit. The corrected conclusion governs.

## What was run

1. **Production one-shot harness, 7B** (`src/premura/harness/live_trial_ollama.py`,
   `qwen2.5-coder:7b`) over the synthetic Fitbit fixture — two runs, both
   FAIL/FAIL/FAIL, and failing *differently* each time (temp=0.1): one fully
   broken (0 rows), the other honest (passed manifest-blind self-reconcile) but
   unloadable because `datetime.fromisoformat("...Z")` is tz-**aware** while the
   contract wants tz-naive UTC. The self-reconcile probe only parse+validates, so
   the tz bug is invisible in-loop; only the grader's warehouse insert catches it.
   The cross-run instability is itself a floor signal for the 7B.
2. **Throwaway tool-use spike, 7B** (`/tmp/premura_toolspike/spike.py`): gave qwen
   conversational memory (Ollama `/api/chat`), a READ tool (manifest **denied** for
   C-005), and a RUN tool doing a real warehouse ingest. Across 3 protocol
   variants the 7B never reached a loading parser in 8 turns — echoed the JSON
   schema placeholder, dithered re-reading files, made progress at turn 6 and
   regressed by turn 8.
3. **Stronger operator, 14B** (`spike_14b.py`, same tool loop): FAIL/FAIL/FAIL.
   The first-pass conclusion was *"below the floor, needs a frontier model."*

## The reversal: it was the harness, not the model

The first-pass conclusion was challenged — *context problem, not capability: did
we actually tell it what to do?* — and was wrong. Two real defects lived in the
**spike** harness (not the production one):

1. **Truncated context.** The spike's READ tool truncated `base.py` at 4000 chars
   (line 127), but `IngestBatch` is defined at line 282 — the model **never saw
   the class it had to build** and was fed irrelevant intake types instead.
2. **A self-contradicting brief.** The combined system prompt told the model both
   "no code fences, output only the module" (`_CONTRACT_PROMPT`) **and** "use a
   ```python fence and READ files first" (the tool-loop half).

Every 14B error was an **API-shape** mistake (`Measurement(value=)`, missing
`IngestBatch.source_kind`, `parse()` returning `None`) — *didn't-know-the-API*,
not weak reasoning.

## Decisive clean test

The **same 14B** was driven through the production `OllamaOperator` — a clean
brief (full API in `_CONTRACT_PROMPT` + an 8-line data sample + retry-on-error,
no contradiction), graded via `_grade_one` only (no scoreboard pollution):

| Run | Result |
| --- | --- |
| 1 | PASS / PASS / PASS (single attempt) |
| 2 | PASS / PASS / PASS (single attempt) |
| 3 | near-pass — silently consumed `timestamp` as `ts_utc` without declaring it a gap; its own self-reconcile missed it, the grader caught it |

A local 14B is comfortably **above** the floor with a coherent brief.

## Corrected conclusion

- The spike measured **harness context quality**, not operator capability.
- The tool-loop tier is **worth pursuing** and likely does **not** need a frontier
  model. The clean one-shot+retry design is validated.
- Any tool-loop slice must **first fix the context plumbing**: serve the API doc
  un-truncated (or a focused summary), carry **one** coherent brief, and show the
  data sample like the production operator does.
- `timestamp`-as-gap is a real contract subtlety worth a sharper prompt/contract
  line (the operator must declare a consumed-but-renamed source column as accounted,
  not silently absorb it).
- **Queue unchanged:** tier work sits **behind** the operator-visible intake
  source-adaptation mission. A frontier run is now a **headroom** question, not a
  **floor** one — optional, hold until intake ships.

## What this seeds

The reframed tier mission — **tool-loop live-trial harness hardening**, scoped in
[`docs/building/planning/tool-loop-live-trial-tier.md`](../../building/planning/tool-loop-live-trial-tier.md)
— inherits this note's corrected premise: it is a context-plumbing + separate-tier
**scoring** slice, not a capability remedy.
