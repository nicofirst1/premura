# Research: Implement Profile And Intake Storage

## Decision 1: Make the doctrine ambiguity explicit now

- **Decision**: Treat the recurring confusion about human forms/manual entry as a
  real documentation defect and correct it before implementation planning.
- **Rationale**: The doctrine already said the agent is the primary operational
  client, but it did not say plainly enough how that changes data-capture
  defaults. The mission spec drifted back into a human-entry framing, which is
  exactly the repeat failure the user wants to stop.
- **Alternatives considered**:
  - Leave doctrine wording as-is and rely on memory. Rejected because the same
    misunderstanding already happened again.
  - Fix only the current mission spec. Rejected because the next mission could
    drift the same way.

## Decision 2: MCP is the primary profile write surface

- **Decision**: Use bounded MCP tools as the main runtime path for profile
  capture, with CLI only as a thin fallback and test surface.
- **Rationale**: The product doctrine and charter both say the MCP/tool surface
  is the default analytical interface. The user also clarified that the agent
  should ask for bounded profile facts and then write them through commands or
  MCP functions.
- **Alternatives considered**:
  - CLI-only. Rejected because it treats the fallback path as the primary one.
  - Human-facing local form. Rejected because it assumes a UI-first product the
    doctrine explicitly rejects.

## Decision 3: Nutrition and supplements stay on the parser / plug-in path

- **Decision**: Do not ship built-in MyFitnessPal import or supplement CSV import
  in this mission. Instead, create the storage and persistence seam those future
  parser/plugin missions should target.
- **Rationale**: The user clarified that nutrition and supplement ingestion
  should keep Premura's plug-in play model: users bring vendor-shaped data,
  agents adapt Premura by creating parsers, and those parser changes move through
  review.
- **Alternatives considered**:
  - Hardcode a MyFitnessPal importer now. Rejected because it solves one vendor
    by bypassing the product's chosen extension path.
  - Add manual nutrition/supplement entry now. Rejected because it pulls the
    mission toward a human-entry product surface that the user did not ask for.

## Decision 4: Use concrete domain tables, not a generic context blob

- **Decision**: Choose a real warehouse migration with separate profile,
  nutrition, and supplement tables rather than a generic JSON bucket or note
  store.
- **Rationale**: This mission is the first real implementation over the meaning
  contract. If storage stays vague here, future parser and signal missions will
  still be tempted to reuse `hp.fact_measurement` or notes. Separate tables make
  the one-home rule concrete.
- **Alternatives considered**:
  - Generic key/value or JSON store. Rejected because it weakens the reviewable
    boundary and makes drift easier.
  - Reuse `hp.fact_measurement`. Rejected because it collapses declared context
    and intake semantics into observation history.

## Decision 5: Separate profile capture from parser persistence

- **Decision**: Use one bounded write service for profile capture and a related
  but parser-ready persistence seam for nutrition/supplement records.
- **Rationale**: Profile capture is agent-mediated and does not start from a
  source artifact. Nutrition and supplement records do start from source
  artifacts in the long run, so they should plug into a normalized persistence
  path that future parsers can emit.
- **Alternatives considered**:
  - Force profile capture through the current `IngestBatch` flow. Rejected
    because it assumes a file-backed ingest shape where none exists.
  - Create one-off importer logic for each intake source. Rejected because it
    works against the plug-in / parser model.
