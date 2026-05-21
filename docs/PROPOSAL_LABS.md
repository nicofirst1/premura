# premura — Proposal: Blood / Urine / Stool Lab Ingestion

> Status: proposal/archive. Forward-looking lab-ingestion proposal, not current shipped behavior.
>
> Companion to [SPEC.md](SPEC.md), [ARCHITECTURE_HISTORY.md](ARCHITECTURE_HISTORY.md), [VISION.md](VISION.md), [STAGES.md](STAGES.md), [ROADMAP.md](ROADMAP.md).
> Captured 2026-05-21. Forward-looking — not v1 work. Scopes the addition of clinical lab results as a first-class source class.

## Why

The current four sources (Garmin, HC, SAA, BMT) all describe **physiology in motion** — heart rates, sleep, body composition, training load. They are dense (minute-level), continuous, and tell us how the body is *running*.

Clinical labs are the orthogonal axis: **physiology at rest, sparsely sampled, deeply informative.** A single CBC panel encodes more about haematologic state than a year of HRV traces. Blood lipids predict cardiovascular risk in ways no wearable can. Specialty stool microbiome panels describe gut state. Vitamin / mineral panels reveal what intake and absorption are doing.

**Without lab data the warehouse is missing an entire dimension of "what the body is."** With it, the warehouse becomes the substrate the operator actually wants — the place where "I just got my blood drawn" is queryable against "what was my sleep doing the month before."

A typical operator profile is a many-years backlog of lab PDFs across multiple labs and languages; ingest is therefore a backfill problem, not a streaming one.

## Source profile

| Trait | Value |
|---|---|
| Format | PDF (most), PNG (one), XLSX (one historical) |
| Languages | Multi-language (operator-specific; commonly Italian, German, English) |
| Volume | Tens of blood PDFs, a handful of stool PDFs, growing 1–4× / year |
| Text-extractable vs scanned | Mixed — text-extractable for recent labs, scanned image-only for older ones |
| Cadence | Sparse and irregular: months to years between samples |
| Variability | Test name varies across labs (`LEUCOCITI` / `Leukozyten` / `WBC`); units mostly consistent; reference ranges drift |
| Provenance | Lab name, date of draw, sometimes ordering physician |
| Free-text | Some labs (microbiome/specialty) emit multi-page clinical commentary and therapy recommendations beyond the numeric tables |

## Stage placement (per [STAGES.md](STAGES.md))

### Stage 1 — Ingest

**New parser: `parsers/lab_pdf.py`.**

Schema fit is free. The long-format star schema (`hp.fact_measurement` + `hp.dim_metric` + `hp.dim_source`) already accepts arbitrary `(metric_id, ts_utc, value, source)` tuples. Each lab marker becomes one new `dim_metric` row; each result becomes one `fact_measurement` row.

Per result row:
- `metric_id` — canonical name, prefix `lab:` to namespace (e.g. `lab:hemoglobin`, `lab:vitamin_d_25oh`, `lab:ferritin`).
- `ts_utc` — date of draw (preferred) or earliest available timestamp from the report.
- `value_num` — numeric result in canonical unit.
- `value_text` — for qualitative results (`negativ`, `assenti`, `traces`).
- `unit` — canonical unit per `dim_metric`.
- `source_id` — laboratory (e.g. `lab:<lab-slug>`, namespaced per provider).
- `raw_payload` — `{ original_test_name, original_unit, reference_range_string, lab_flag, page_n }`.

Reference ranges: stored **per-row in `raw_payload`** (because they vary by lab and over time) plus an aspirational canonical range on `dim_metric` for display. Not used for analysis — analysis uses the lab's own range when it matters.

Free-text clinical commentary (specialty-lab interpretation pages): new table `hp.fact_clinical_note` with `(note_id, ts_utc, source_id, language, text, ingest_batch)`. Kept separate from numeric facts because querying it is a different problem.

Open: namespacing for canonical names. The prior repo defaults to the lab's source language (e.g. Italian `LEUCOCITI`); the wider project leans English. Default position for this repo: **English canonical names** for `dim_metric.metric_id` (e.g. `lab:wbc`, `lab:hemoglobin`); display name in `dim_metric.display_name` carries the localised form. Per-language variants live in a `dim_metric_alias` table for the parser's normalisation step.

#### PDF extraction technique — three candidates

The dominant engineering question is **how to turn the PDF into reliable typed rows**. An operator-local prior-art OCR repo (kept out of source control) is the baseline. Three candidates:

1. **Prior repo's stack — `pymupdf` + Tesseract + Claude vision with caching.**
   - `pymupdf` extracts text layers cleanly when present; a "scanned page" detector falls through to OCR. Tesseract output is fed *as context* to Claude vision, which corrects OCR errors against the image. Per-page JSON cache keyed on `md5(first_4096_bytes)_p{n}`.
   - Already proved out on a real multi-year lab-PDF corpus (hundreds of cached pages, ~140 markers × ~35 dates extracted).
   - Cost: ~$0 across the existing corpus (cache-heavy). Future cost: small per new draw.
   - Weakness: Claude vision is non-deterministic; the structured table extraction is prompt-engineered, not modelled. Tables with bar-chart noise (specialty labs) need careful prompting.
   - Privacy: PHI is sent to the Anthropic API. Acceptable for the prior repo; would need re-evaluation here against Pillar 6 ("user-held key, no upsell").

2. **Docling** (https://github.com/docling-project/docling) — IBM/LF AI & Data, MIT, actively maintained.
   - Purpose-built for PDFs → structured Markdown / JSON with **native table-structure extraction**, reading-order detection, OCR for scanned pages via included VLM (GraniteDocling). Runs **fully locally** — no network call. Python API + CLI.
   - Match for our profile: handles both text-extractable and scanned PDFs in one pipeline; treats tables as first-class (lab reports *are* tables); no PHI ever leaves the machine. Pillar-6-clean by construction.
   - Unverified: per-language content quality. The VLM is multilingual but the README doesn't quantify per-language. **Required spike**: run on a representative sample (recent text-extractable PDF, an older scanned PDF, a multi-language report) and compare row-level extraction accuracy against the prior repo's outputs.
   - If docling wins on the spike: it becomes the default extractor, the prior repo's Claude-vision path becomes a fallback for pages docling can't read.

3. **Trafilatura** — not applicable. It is a web-page boilerplate stripper, not a PDF tool. Listed here only because it came up in conversation; ruled out.

**Recommendation:** spike docling first. If it's competitive on a real lab-PDF corpus and runs locally, it solves the privacy concern that the prior repo's stack carries. The prior repo remains the reference implementation for (a) post-extraction structuring — turning extracted text into `TEST | VALUE | UNIT | RANGE`, (b) per-language test-name normalisation tables, (c) date-of-draw vs date-of-print heuristics. Those are extraction-engine-agnostic and we adopt them verbatim regardless of which engine wins.

#### Adoption from the old repo

We **do not** wire the old repo in as a dependency. We **do** lift, into this repo:

- The **test-name alias map** (Italian/German → English canonical) — port `SPECS.md`'s "Italian name mapping" table to `dim_metric_alias.yaml`.
- The **date-extraction heuristics** — "Accettazione del" (IT sample date) beats "Referto stampato" (IT print date); "Entnahmetag" (DE sample date) beats "Eingang" (DE receipt); filename `YYYYMMDD` is last-resort fallback.
- The **value-quirk handling** — comma-as-decimal, `<1.0 x 10^4` → `10000`, `negativ` / `ASSENTI` / `NR` → `value_text='negativ'`, `folgt` (German "to follow") → skip.
- The **clinical-summary structure** — chronological grouping by year; cite source file; English translation kept alongside original.

If the prior repo has an already-digitised CSV (per-test × per-draw matrix), it can be imported as a one-shot backfill the first time the new lab parser runs against the existing PDFs — but we ingest from the **PDFs** as the source of truth, not from the CSV. The CSV is a cross-check, not the contract.

### Stage 2 — Signal processing

Lab data forces three signal-processing rules the wearable-dominated v1 didn't need:

1. **Long validity windows.** A vitamin D level in March is not telling you about your vitamin D in November. Per-metric `validity_window` (declared in `dim_metric`) for common markers:
   - Acute-phase / inflammatory (CRP, calprotectin): days–weeks.
   - Lipids, glucose-related (LDL, HDL, fasting glucose, HbA1c): 1–3 months (HbA1c reflects 3-month average; that's not the same as "valid for 3 months going forward" — open question).
   - Minerals / vitamins (ferritin, B12, vitamin D, magnesium): 2–6 months.
   - Genetics, blood type, one-off panels: effectively infinite.
2. **No imputation, by default.** Lab markers get `missing_data_policy = none`. Two draws a year apart are two observations, not a series with 363 imputed days in between. The signal selector must respect "you have N=2 points; do not pretend you have N=365."
3. **Cross-marker derived signals.** Derived metrics like `derived:ldl_hdl_ratio`, `derived:ast_alt_ratio`, `derived:anion_gap`, `derived:tg_hdl_ratio` are materialised when both inputs are present on the same draw (`ts_utc` matches within tolerance). When only one input is present, the derived value is **not computed** — no imputation across markers.

### Stage 3 — MCP

The MCP layer needs no blood-specific changes provided Stage 2 is honest about sparsity. The existing `correlate`, `change_point`, `rolling_mean` tools work on lab series the same way they work on HRV series — provided they consume the validity-checked, **not-imputed** series from Stage 2.

PubMed tools become more important here: a finding about ferritin and exercise capacity should be queryable; the LLM must cite by PMID via round-trip, never invent.

### Stage 4 — UI

The teaching layer matters more for blood than for wearable signals because the user has less intuition for "WBC 6.2 K/µL" than for "10,000 steps." Every lab marker introduced by the UI must carry:

- Plain-English one-liner (what it measures, why it matters).
- The user's own value with the lab's reference range, clearly marked.
- A range visual (not a number-only display).
- Trend chart over time — explicitly marked sparse where N is low.
- If a derived ratio is the more meaningful signal (e.g. LDL/HDL > absolute LDL alone), surface the derived signal first and the components on disclosure.

The interview adds at least these tracks:
- **Cardiometabolic labs** — LDL/HDL/triglycerides/glucose/HbA1c/blood pressure.
- **Iron status** — ferritin/transferrin/sideremia.
- **Vitamins & minerals** — vitamin D, B12, magnesium, zinc, etc.
- **Liver function** — AST/ALT/ALP/GGT/bilirubin.
- **Kidney function** — creatinine/urea/eGFR.
- **Thyroid** — TSH/fT3/fT4/antibodies.
- **Gut** — stool microbiome panel (specialty-lab class).

## Build order (when this becomes active work)

1. **Spike docling** on a real lab-PDF corpus. Compare table-extraction accuracy and per-language quality to the prior repo's pymupdf+Tesseract+Claude pipeline. ≤1 day.
2. Port the prior repo's **test-name alias map** + **date heuristics** + **value-quirk handlers** to this repo as `dim_metric_alias.yaml` and `parsers/lab_pdf/normalise.py`. ≤1 day, no PDF parsing yet.
3. Implement `parsers/lab_pdf.py` against the chosen extractor. Emit `Measurement` records per existing `parsers.base.Parser` contract. Add `hp.fact_clinical_note` migration for free-text. ≤2 days.
4. Backfill the operator's historical lab corpus. Reconcile against the prior repo's CSV (if any) as a sanity check. ≤0.5 day.
5. Add `validity_window` + `missing_data_policy` columns to `dim_metric` (migration `004`). Seed values for the lab markers introduced in step 4. ≤0.5 day.
6. First three derived ratios: `derived:ldl_hdl_ratio`, `derived:ast_alt_ratio`, `derived:tg_hdl_ratio`. Persistence + recomputation hook. ≤0.5 day.

Stages 3 (MCP exposure) and 4 (UI / interview tracks) flow from VISION.md's existing roadmap and don't need blood-specific build items beyond seeding the metric vocabulary.

## Out of scope

- **Live API pulls from labs.** Most labs (especially in EU jurisdictions) do not expose a usable patient API; PDFs are the only contract.
- **OCR for handwriting.** Some old reports have margin notes — those go into `fact_clinical_note` as raw text or are skipped.
- **Diagnosis.** Nothing in this feature outputs anything that could be read as a diagnosis. Reference ranges and derived ratios are reported; interpretation is left to the user and their doctor.
- **EHR / FHIR interop.** This is a personal warehouse, not a clinical record. Deliberate.
- **Writing back to labs.** No vendor offers it; not interesting.

## Open questions

1. **Canonical-name language** — English (recommended above) vs the prior repo's source-language choice. Affects `metric_id` strings forever; pick once, alias the rest.
2. **HbA1c validity window** — it integrates ~3 months retrospectively; that is not symmetric with "valid for the next 3 months." Probably the window should encode that asymmetry. Per-metric forward/backward validity may be needed.
3. **Reference range over time** — labs change their ranges. Do we store every range we've seen and pick the most-recent for display, or the one belonging to the specific draw? Default: the draw's own range (per-row `raw_payload`), with the most-recent surfaced for current-state UI.
4. **Privacy threshold for OCR** — docling spike resolves this. If docling is good enough, no PHI ever leaves the machine for lab ingest. If we fall back to the prior repo's Claude-vision approach, the operator must explicitly opt in (Pillar 6 contract).
5. **Prior repo's clinical_summary.md** (if present) — do we ingest its long-form free-text translation as `fact_clinical_note` rows, or re-extract from PDFs? Re-extracting is cleaner; ingesting the existing summary saves work. Default: re-extract, keep the prior summary as a cross-check artifact in `data/archive/`.
6. **Stool panel cardinality** — specialty stool reports have many tens of organism-level rows per panel. Every organism becomes a `metric_id`? Default yes; `dim_metric` is cheap.
