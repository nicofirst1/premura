# Land concrete profile/intake storage as separate domain tables, with agent-mediated profile capture

Premura had already fixed the *meaning* of baseline profile context, nutrition
intake, and supplement intake in a strict contract while leaving storage open
(see [ADR 0005](0005-profile-and-intake-contract.md) and
[`PROFILE_AND_INTAKE_CONTRACT.md`](../architecture/PROFILE_AND_INTAKE_CONTRACT.md)).
This mission picks the storage and the first write path. The decision:

- **Separate concrete domain tables, not a generic bucket.** Migration
  `src/premura/store/migrations/004_profile_intake.sql` adds dedicated `hp.*`
  tables: `hp.profile_capture_session` and `hp.profile_context_assertion` for
  profile context; `hp.nutrition_intake_event` → `hp.nutrition_intake_item` →
  `hp.nutrition_quantity` for nutrition; `hp.supplement_intake_event` →
  `hp.supplement_item` → `hp.supplement_dose` for supplements. Each domain has
  its own provenance, supersession, and dedupe columns. The "one-home" rule from
  the contract is now **structural**: there is deliberately no JSON catch-all
  column and nothing back-fills these meanings into `hp.fact_measurement`,
  `hp.fact_interval`, or note storage.
- **Append/supersede for profile history, never overwrite.** A new assertion for
  the same `attribute_key` closes the prior open row's `effective_end_utc` and
  links back via `supersedes_assertion_id`. The earlier row stays in history.
- **Agent-mediated bounded profile capture as the only write path that ships.**
  `src/premura/profile_fields.py` is a small closed allowlist
  (`birth_date`, `sex`, `standing_height_cm`); `record_profile_context`
  (`src/premura/store/profile_intake.py`) validates against it at the store
  boundary and stamps `source_kind="agent_profile_capture"`. The surface is the
  default MCP tools `profile_context_supported_fields` /
  `profile_context_record` (`src/premura/mcp/`), mirrored by the expert CLI
  `premura profile-fields` / `premura profile-record`. The derived key `age` is
  rejected, not stored — it is computed from `birth_date` and the evaluation
  date so the two can never drift.
- **Nutrition/supplement source adaptation is parser/plugin follow-on work.**
  The intake tables exist and `persist_intake_batch` loads a normalized
  `IntakeBatch` idempotently (dedupe on the `dedupe_key` UNIQUE constraint), but
  no built-in importer (MyFitnessPal, label scanner, supplement catalog) ships.
  Populating these tables is future federated-parser work, exactly like the
  existing wearable sources.

This combination won because the alternatives each reopen a problem the contract
already closed:

- A **generic context blob / JSON bucket** would have let any future writer drop
  arbitrary keys in one place — reintroducing the `misc` bucket the contract
  forbids and making the one-home rule unenforceable.
- **Reusing the measurement tables** (`fact_measurement` / `fact_interval`)
  would collapse a *declared* attribute or a *consumed* quantity into an
  instrument *observation*, which is the exact back-door ADR 0005 was written to
  block.
- **A form-first or one-off-importer-first assumption** would have re-introduced
  the human-form/manual-entry story the doctrine rejects. The doctrine's primary
  operational client is the agent; bounded baseline facts are captured through an
  agent-mediated interview against a closed allowlist, and bulk source data
  arrives through the parser seam — not a built-in importer wired up first.

Builds on [ADR 0005](0005-profile-and-intake-contract.md) (strict meaning,
flexible storage), [ADR 0001](0001-ingest-batch-parser-seam.md) (the batch/parser
seam this reuses for intake), and the Stage boundaries in
[`STAGES.md`](../architecture/STAGES.md). Intentionally still deferred: built-in
nutrition/supplement importers, and any profile-dependent signal (BMI,
age-adjusted interpretation) — those remain implementation *over* this storage
seam, not part of it.
