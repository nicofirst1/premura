# Pre-merge Review — overnight/release-candidate (v0.4.0-rc.1, missions m2–m8)

> Method: [`docs/building/agents/implement-review-drift-audit.md`](../../building/agents/implement-review-drift-audit.md),
> run **pre-merge** over the consolidated release-candidate branch as seven
> parallel per-mission spec→code→test reviews plus a cross-mission seam pass.
> Each mission was built solo on its own overnight lane; per-WP review owned
> local correctness only, so this audit targets the between-the-scopes gaps
> (cross-mission contracts, doc-count drift, the one schema migration).

## Audited subject

| Field | Value |
|---|---|
| Branch | `overnight/release-candidate` — staging bundle of missions m2–m8 |
| Reviewed HEAD | `d0938048ecc1d99870be4e13ed793c8b838bfb97` |
| Base (master) | `5d6449ead9ec22fef4fbb19a7afda1a5b07216d8` |
| Scope | ~13k added lines, 79 files, 33 commits, all additive/backward-compatible |
| Deterministic floor | ruff clean, mypy clean, 1,386 tests pass (12 deselected live-model/network) |
| Trigger | User request for a consolidated review before merging to master and tagging |

## Verdict

**Merge-ready. Zero blocking findings across the seven missions.** Two
documentation-level findings were fixed on this branch before merge (see
"Findings fixed pre-merge"); everything else is deferred-by-design or cosmetic.

| Mission | Verdict | Worst finding |
|---|---|---|
| m2 conversation-turn capture (`log_turn`) | PASS-with-concerns | schema comment contradicted its own DDL (doc bug; **fixed pre-merge**) |
| m3 judge-AI (`log_judgment`) | PASS-with-concerns | rubric grounding text claimed a dossier field that does not exist (**fixed pre-merge**) |
| m4 improvement hook (`log_improvement`) | PASS | clean — one nit |
| m5 synthetic fixture generator | PASS-with-concerns | no ingest round-trip test (impossible by design until a reference parser exists; deferred) |
| m6 analyze-and-answer task kind | PASS-with-concerns | findings all nit-grade |
| m7 small follow-ups (inspect / gc previews / migration 006) | PASS | clean — migration verified safe |
| m8 condition_paired_t_test (sixth tool) | PASS | two nits |

## Cross-mission checks (the gaps per-WP review cannot see)

These were the audit's primary targets, per the recurring lesson that drift
hides *between* solo-reviewed scopes:

1. **Five-vs-six tool-count reconciliation (`cba9328`) is complete.** Every
   authoritative surface — the `trace.py` docstring, `STAGES.md`,
   `FULL_APP_DEVELOPMENT_PLAN.md`, the engine `CONTRACT.md`, `STATUS.md`, and
   the pinned tool-count test — says six and lists `condition_paired_t_test`.
   No stragglers found.
2. **The m3→m4 seam matches field-by-field.** m4's improvement scan reads
   exactly what m3's judge writes: the `criteria_json` column, the
   `{band, rationale}` per-criterion shape, and the positional decode all
   line up. The rubric/status vocabularies shared across m3/m4/m6 are
   consistent.
3. **Migration 006 (`fact_interval.unit`) is safe.** Idempotent
   (`ADD COLUMN IF NOT EXISTS` + `WHERE unit IS NULL` backfill), no migration
   number collision, and all ~9 parser sites that previously passed the
   silently-dropped in-memory `Interval.unit` are confirmed cleaned (zero
   `Interval(unit=` occurrences remain).
4. **The honesty boundary holds for the new tool.** m8's forbidden-language
   sweep passes (no "significant", no p-value, no causal claim, no
   population-norm comparison); constant per-episode differences refuse
   rather than print a zero-width band; the existing `paired_t_test` is
   byte-for-byte untouched.
5. **The safety defaults hold.** The m3 judge and m4 improvement hook both
   default OFF and are guarded so a failure inside them can never flip a
   harness run's verdict.

## Findings fixed pre-merge (this branch, post-review)

1. **m3 — `JUDGE_RUBRIC.md` grounding claim was false.** The
   `analytical-claims-match-engine` criterion said the judge grounds against
   "recomputed analytical facts carried in the dossier" — but
   `SessionDossier` carries no such field; the engine's results reach the
   judge only as tool-result *turn content* inside the transcript. At runtime
   the judge self-corrects (it reads the transcript), so this was misleading
   instruction text, not a defect. Fixed the grounding line and bumped
   `rubric_version` to `2026-06-12.2` per the rubric's own evolution rule.
2. **m2 — `schema.sql` comment contradicted the DDL.** The `log_turn`
   comment said `step_id` "is NOT a hard FK" while the column declares
   `REFERENCES log_step(step_id)`, which DuckDB enforces. Production-safe
   (the harness always flushes the step row first), but the comment promised
   order-independence the schema does not provide. Comment corrected to
   match the DDL.

## Non-blocking residue (deferred, on the record)

- **m5:** no fixture→ingest round-trip test exists because no reference
  parser for the synthetic vendor shape exists yet; the round-trip belongs to
  whichever mission first builds one.
- **One sandbox artifact during review:** the m7 reviewer's sandboxed run
  reported a failure in `test_live_trial_tool_loop_edges.py` that the
  canonical full run (1,386 passed, 0 failed) does not reproduce — consistent
  with the known network-isolated-sandbox interaction, not a real failure.
- **Issue linkage:** the branch closes no GitHub issue mechanically (no
  `Closes #N` trailers) and none on substance; it materially advances #10
  (acceptance-sandbox umbrella: m2/m3/m4/m5/m6 are its building blocks) and
  touches #12. #9 (RESULT_FAMILIES extension trigger) remains open — m8's
  CONTRACT extension rule covers the analytical tool set, **not** the Stage-2
  answer-shape families; the similar wording should not be read as closing it.
