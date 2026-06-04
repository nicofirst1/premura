# Contract: Intake Parser Runtime Support

Purpose: define the mission-local contract for making runtime intake parser
authoring implementable, not just documented.

## Problem this contract closes

The authoritative parser prose already documents two persistence seams
(`IngestBatch` and `IntakeBatch`), but the actual parser protocol and runtime
entrypoints still assume `parse(path) -> IngestBatch` only. This contract closes
that gap.

## Required runtime behavior

1. The supported parser/runtime path must handle:
   - observation output only
   - intake output only
   - and it must not structurally preclude mixed observation and intake output
     from one source artifact when a source genuinely carries both
2. Runtime parser invocation must persist each output through the correct seam:
   - observation output -> observation loader path
   - intake output -> `persist_intake_batch(...)`
3. Intake output must never be coerced into `Measurement`, `Interval`, or
   `ClinicalNote` rows just to fit the older runtime path.
4. The parser-generator skill must document the same supported runtime path that
   the authoritative contract and protocol implement.

## Acceptance conditions

- A parser producing intake-only output is valid and loadable.
- Existing observation-only parsers remain supported.
- Runtime invocation points used by CLI/harness paths accept the supported intake
  output path.

## Non-goals

- Shipping a production nutrition or supplement vendor parser.
- Redesigning intake storage.

## Evidence expectation

- parser contract/protocol tests
- runtime invocation tests proving correct seam dispatch
- reference parser + synthetic fixture proof
