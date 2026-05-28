# Quickstart: Validate Stage 2 Input Resolution And BMI

## Purpose

This quickstart describes the intended validation path for the later
implementation mission. It focuses on the proof consumer and the honest refusal
behavior rather than broad analytical polish.

## Preconditions

- Work from the repository root on `master` per the mission branch contract.
- Use synthetic or non-PHI fixtures only.
- Keep tests black-box through public engine interfaces.

## Validation flow

1. **Red step: add failing BMI success-path test**
   - Describe a fixture with declared standing height and usable weight.
   - Assert that the public Stage 2 entrypoint can return a successful BMI result
     for the chosen anchor time.

2. **Red step: add failing refusal-path tests**
   - Missing declared height
   - Missing or stale weight
   - Declared nutrition or supplement dependency with no shipped resolver

3. **Implement the resolver seam**
   - Add the resolver registry pattern.
   - Add observation resolver.
   - Add profile-as-of resolver.
   - Add explicit unresolved behavior for nutrition/supplement declarations.

4. **Implement the BMI proof consumer**
   - Resolve both declared inputs through the new seam.
   - Return success only when both are usable.
   - Return explicit refusal or missing-input behavior otherwise.

5. **Update the docs in the same change**
   - Stage 2 boundary wording
   - Domain-vs-shape rubric
   - Trigger for extending answer families later

6. **Run quality gates**
   - `uv run python -m pytest -q`
   - `uv run ruff check .`
   - `uv run ruff format --check .`
   - `uv run mypy <changed-paths>`

## Expected acceptance evidence

- BMI success works with declared height + usable weight.
- BMI refusal works when either declared prerequisite is absent or stale.
- Declared nutrition/supplement dependencies fail explicitly rather than being
  silently satisfied through another domain.
- The resolver pattern is visibly extensible in-tree.
- The docs point future contributors toward the right review questions.
