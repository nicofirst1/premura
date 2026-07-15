# AI-chat recall interchange contract (`premura.ai_chat_recall.v1`)

> Status: live reference, authoritative for the `ai_chat_recall` source class.
> Companion to [`src/premura/parsers/CONTRACT.md`](../../../src/premura/parsers/CONTRACT.md)
> (the federated parser contract) and
> [`PROFILE_AND_INTAKE_CONTRACT.md`](PROFILE_AND_INTAKE_CONTRACT.md) (the intake
> seam this source lands in).

People discuss supplements and oral medications with AI assistants. This
contract defines **one JSON interchange format** an assistant can produce from
the user's own chat history, and which Premura ingests through the standard
federated-parser seam as supplement intake.

The deliverable is this contract, not any particular prompt: a paste-prompt for
a specific assistant is a small artifact **derived from** this document (see
§"Deriving a paste-prompt"), and anyone can write one for a new assistant
without a central edit. The parser (`src/premura/parsers/ai_chat_recall.py`)
consumes only this format and never knows which assistant produced it.

## What this source class can honestly answer

Recalled intake is an AI's *recollection of what the user told another AI* —
hallucination risk included. Two consequences are built into the contract:

- **Evidence grade is queryable.** Every row lands under
  `source_kind = "ai_chat_recall"`, never mixed with app-logged intake.
  Signals over this data can (and should) disclose the evidence grade.
- **Inventory, not adherence.** This source supports the *inventory* question
  ("what do I take, roughly since when"). It does **not** support consistency
  questions: `supplement_intake_adherence` ("logged on K of N days") is
  misleading over recollections, because one recalled entry is one event, not
  a log. The parser therefore emits **one event per recalled item** and never
  synthesizes daily events from "I take it every day".

## The format

A single JSON object (UTF-8, `.json` file):

```json
{
  "format": "premura.ai_chat_recall.v1",
  "assistant": "claude.ai",
  "exported_on": "2026-06-12",
  "entries": [
    {
      "product_label": "Magnesium Glycinate 400",
      "ingredient_label": "magnesium glycinate",
      "form_label": "capsule",
      "dose": {"amount_num": 400.0, "unit": "mg"},
      "since": {"date": "2026-03", "precision": "month", "ongoing": true},
      "quote": "I started taking magnesium glycinate around March and still take it nightly.",
      "chat_date": "2026-05-10"
    }
  ]
}
```

### Top level

| Key | Required | Rule |
| --- | --- | --- |
| `format` | yes | Exactly `"premura.ai_chat_recall.v1"`. Anything else: the file is rejected wholesale (it is not this format). |
| `assistant` | yes | Free-text name of the assistant that produced the export (e.g. `"claude.ai"`, `"chatgpt"`). Premura slugs it into the source identity `ai_chat_recall:<slug>`, so each assistant is a distinct provenance source without any registry edit. |
| `exported_on` | yes | `YYYY-MM-DD` date the recall was generated. Fallback time anchor for entries with no `since` (see fuzzy time). |
| `entries` | yes | List of recalled items. May be empty (an honest "nothing found"). |

Unknown top-level keys are declared in `unmapped_metrics`
(`vendor:ai_chat_recall:<key>`), never silently dropped — the same posture as
every Premura parser.

### Entry

One entry = one recalled supplement or oral-medication item = one
`SupplementIntakeInput` event with one item. Medications are represented
exactly like supplements (a product and/or ingredient label); the warehouse
home is the supplement-intake seam either way.

| Key | Required | Rule |
| --- | --- | --- |
| `product_label` / `ingredient_label` | at least one | What was taken, as the chat named it. Brand-vs-ingredient uncertainty stays representable: fill only what the chat actually says. |
| `form_label` | no | e.g. `"capsule"`, `"powder"`. |
| `dose` | no | Object with `amount_num` (+ optional `unit`) and/or `amount_text` (e.g. `"one scoop"`). If present it must carry at least one of the two amounts; free text is first-class, never coerced to a number. |
| `since` | no | When intake started — see fuzzy time below. Omit entirely if the chats never say. |
| `quote` | **yes** | The source chat's own wording, verbatim or near-verbatim. This is the provenance and the hallucination check: an entry without it is rejected (skipped with a reason), because recalled intake with no traceable wording is unverifiable. |
| `chat_date` | no | `YYYY-MM-DD` date of the conversation the quote comes from. |

Unknown entry keys are declared as `vendor:ai_chat_recall:entry.<key>` in
`unmapped_metrics`. A malformed entry (missing labels, missing `quote`,
contradictory `since`, malformed `dose`) becomes a `skipped_rows` entry with a
reason — loud, reviewable, never a silent drop and never a fabricated row.

### Fuzzy time: the `since` object

Chat-recalled intake comes as "since around March", not as a timestamp. The
exporting assistant must **never invent a date**; it declares the precision it
actually has:

```json
{"date": "2026-03", "precision": "month", "ongoing": true}
```

- `precision` is one of `"day"` / `"month"` / `"year"`.
- `date` must match the declared precision **by shape**: `YYYY-MM-DD` for
  `day`, `YYYY-MM` for `month`, `YYYY` for `year`. A shape/precision mismatch
  is a contradiction and the entry is skipped with a reason.
- `ongoing: true` means the chats indicate the user still takes it.
- If the chats give no start at all, **omit `since`**; Premura anchors the
  event at `exported_on` and records the precision as `"unknown"` ("known to
  be taken as of the export date").

How Premura maps this onto the warehouse (`ts_utc` is a point timestamp):
the event is anchored at the earliest instant of the declared period —
`month` → first of month, `year` → January 1 — at midnight, as a naive
timestamp with no invented timezone (the same posture as other bare-date
sources). The declared `precision`, `ongoing` flag, original `quote`,
`chat_date`, `assistant`, and `exported_on` are persisted verbatim in the
event's `raw_payload`, so no consumer has to trust the anchored timestamp as
more precise than it is. The queryable honesty marker is `source_kind`;
the full precision detail rides in `raw_payload`.

### Idempotency

`dedupe_key = sha256("ai_chat_recall|<assistant_slug>|<labels>|<since>")` —
one event per assistant + item + declared start. Re-running the export later
(a new `exported_on`) re-states the same inventory facts and is a no-op for
already-loaded items. The store is append-only: a later export that corrects a
dose does not retroactively update the first write (first write wins, same as
the other intake sources). A duplicated entry *within* one export — the
assistant recalling the same item twice — is skipped with a reason (first
occurrence wins), never a fatal error.

Known limit: the same item exported once *without* `since` and later *with*
one produces two rows (their keys differ — the first was anchored at
`exported_on` as precision `"unknown"`). Inventory consumers should treat
label equality as the item identity and prefer the more precise row.

## Deriving a paste-prompt for an assistant

A paste-prompt is any prompt that makes a specific assistant emit valid
`premura.ai_chat_recall.v1` JSON from the user's chat history. To write one
for a new assistant, satisfy these requirements — this list is the contract;
the wording per assistant is free:

1. **Recall, don't infer.** Only items the user themselves stated taking (or
   unambiguously implied, e.g. "my daily magnesium"). No inferring intake from
   symptoms, interests, or questions ("asked about creatine" is not intake).
2. **Quote or drop.** Every entry carries the chat's own wording in `quote`.
   If the assistant cannot point to wording, it must omit the entry.
3. **Precision over completeness.** Dates use the truncated form matching what
   the chats actually establish; `since` is omitted when unknown. Doses use
   `amount_text` when no number was stated. Never round up to fake precision —
   in particular, a relative time ("two weeks ago", "since last spring") must
   **not** be resolved into a `day`-precision date by arithmetic against the
   chat date; it stays at the precision the wording itself carries (`month` or
   `year`). The first live exercise of this contract showed assistants do
   exactly this arithmetic unless told not to.
4. **Valid JSON, nothing else.** The reply must be exactly one JSON object in
   this format (so the user can save it to a file unedited), with
   `format`, `assistant`, `exported_on`, and `entries` set.
5. **Scope statement.** The prompt should tell the assistant this is the
   user's own data, exported at the user's request, for ingestion into their
   personal health store.

### Reference paste-prompt (one assistant: Claude.ai)

> Search our entire conversation history for every supplement and oral
> medication I have told you I take or took (including things like "my daily
> magnesium"). Do not infer intake from questions I asked or symptoms I
> mentioned — only include items I actually said I take, and for each one keep
> my own wording. Reply with exactly one JSON object and nothing else, in this
> format:
>
> `{"format": "premura.ai_chat_recall.v1", "assistant": "claude.ai",
> "exported_on": "<today, YYYY-MM-DD>", "entries": [{"product_label": ...,
> "ingredient_label": ..., "form_label": ..., "dose": {"amount_num": ...,
> "unit": ...} or {"amount_text": "one scoop"}, "since": {"date":
> "YYYY-MM-DD" | "YYYY-MM" | "YYYY", "precision": "day" | "month" | "year",
> "ongoing": true/false}, "quote": "<my words, verbatim>", "chat_date":
> "YYYY-MM-DD"}]}`
>
> Rules: include at least one of product_label/ingredient_label per entry;
> `quote` is mandatory (drop the entry if you can't quote me); truncate
> `since.date` to the precision you actually know and omit `since` entirely if
> I never said when I started — if I used a relative time like "two weeks ago"
> or "since last spring", do NOT compute an exact date from it, keep month or
> year precision; use `amount_text` for non-numeric doses; omit any field you
> don't know rather than guessing. This is my own data, exported at my
> request, for my personal local health store.

## Ingesting the result

Save the assistant's JSON reply to a file and ingest it like any other source
artifact (`premura ingest --source aichat <file>`, or drop it in the inbox).
A reply wrapped in one whole-document markdown code fence (assistants do this
despite the "nothing else" instruction) is tolerated; JSON buried in
surrounding prose is not — re-ask the assistant for the bare object.
The parser follows the federated parser contract: intake-only
`ParseOutput(intake=IntakeBatch)`, no observation rows, no `dim_metric`
additions, gaps declared via `unmapped_metrics` / `skipped_rows`.

Never commit a real exported recall (or any real chat content) to this repo —
fixtures are synthetic only, the same rule as every other parser.
