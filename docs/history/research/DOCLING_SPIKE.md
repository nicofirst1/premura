# Docling Spike For Lab Reports

Status: completed 2026-05-23.

## Question

Is docling good enough to be Premura's extraction path for the operator's real lab-report corpus, including older Italian blood PDFs, newer scanned German blood PDFs, and Biovis stool reports with both result tables and long-form commentary?

## Corpus Sample

The spike used three representative private reports from the operator's local corpus. The source PDFs and any extracted PHI stayed outside this repo.

- `data/v2/Blood Tests/20091107.pdf`
  - Italian blood panel
  - text-extractable
- `data/v2/Blood Tests/20260209.pdf`
  - German blood panel
  - scanned / OCR-heavy
- `data/v2/Stool Tests/20240131.pdf`
  - Biovis stool report
  - mixed result tables plus multi-page clinical commentary

## Paths Tested

1. Standard docling PDF pipeline on CPU.
2. Docling with `TesseractCliOcrOptions`.
3. Docling with `RapidOcrOptions`.
4. Docling VLM pipeline with `GRANITEDOCLING_MLX`.

The CPU override was necessary on this Mac because docling's default accelerator choice selected MPS and crashed in layout with a `float64`-on-MPS failure.

## Result

### 1. Standard docling on CPU

- `20091107.pdf`: usable enough for a first pass once the parser was taught docling's markdown-table shape. Premura recovered core CBC and chemistry values such as WBC, RBC, hemoglobin, hematocrit, MCV, MCHC, platelets, BUN, and triglycerides.
- `20260209.pdf`: also usable enough for a first pass. Premura recovered WBC, RBC, hemoglobin, hematocrit, MCV, MCH, RDW, and platelets from the scanned German blood report.
- `20240131.pdf`: not sufficient for the result-table half of the stool report. Standard docling extracted commentary and metadata, but the stool tables did not arrive in a shape the current parser could consume.

### 2. Docling + Tesseract CLI

- On the Biovis stool report this did not materially improve table extraction.
- It still mostly surfaced commentary and summary text, not a usable row-wise result table.

### 3. Docling + RapidOCR

- On the Biovis stool report this also failed to recover the result table in a useful row-wise form.
- It behaved similarly to the Tesseract fallback: commentary improved, tables did not.

### 4. Docling VLM (`GRANITEDOCLING_MLX`)

- This was the first path that surfaced actual stool-result rows clearly enough to inspect.
- Extracted examples included:
  - `Pankreaselastase im Stuhl | 91,32 | ...`
  - `Gallensauren im Stuhl | 46,85 | ...`
  - `Hamoglobin im Stuhl immunologisch | <10 | ...`
  - `Calprotectin | <17,90 | ...`
  - `Alpha 1-Antitrypsin | 6,0 | ...`
  - `Anti-Transglutaminase AK i. Stuhl | 60,76 | ...`
- However, feeding that VLM output into Premura's current `lab_pdf` parser still yielded zero measurements. At that point extraction was no longer the main blocker; ontology coverage, row-shape handling, and stool-specific alias/unit normalization became the bottleneck.

## Recommendation

- Keep standard docling as the active extraction path for blood PDFs.
- Do not treat standard docling as a universal default for the current corpus yet; the Biovis stool report class remains the hard case.
- Treat stool reports as a split problem:
  - numeric result tables
  - free-text clinical commentary
- The commentary half is already well served by standard docling and likely maps to the future `hp.fact_clinical_note` destination described in `PROPOSAL_LABS.md`.
- The measurement-table half currently looks most promising with the VLM path, but that path is Apple-Silicon-specific today because it depends on `mlx-*` packages.

## Trade-Offs

- `GRANITEDOCLING_MLX` is the strongest result-table extractor tested for the Biovis stool report, but it is platform-coupled to Apple Silicon / Metal.
- Standard docling remains simpler and more portable, but it loses the stool tables that matter most for M3.
- The bottleneck has moved from "can we extract anything?" to "which extractor should run for which report class, and how do the extracted rows map into Premura's ontology and review channels?"

## What This Changes

- The extraction-path decision is no longer blocked for blood reports.
- The remaining M3 extraction risk is concentrated in Biovis-style stool reports.
- Before more parser work lands, Premura should decide:
  - whether stool reports get separate measurement-table and clinical-note flows
  - whether extractor dispatch is per report class or fallback-based
  - whether the Apple-only VLM path is acceptable for this operator-local repo
