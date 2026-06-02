---
affected_files: []
cycle_number: 2
mission_slug: session-log-substrate-01KT45S1
reproduction_command:
reviewed_at: '2026-06-02T13:46:19Z'
reviewer_agent: unknown
verdict: rejected
wp_id: WP03
---

# WP03 Review — Cycle 1 (CHANGES REQUESTED)

Verdict: **REJECT** — one blocking issue (an unnecessary, uncontracted deviation
from the tracked-only sandbox contract that creates a determinism/containment
smell). Everything else — envelope conformance, single-writer rule, teardown,
gates — is correct and verified. Fix Issue 1 and re-request.

---

## Issue 1 (BLOCKING) — Sandbox copies untracked-not-ignored files; contract says tracked-only

**Where:** `src/premura/harness/sandbox.py:64-67` (`_tracked_files`)

```python
paths = _git_paths(repo_root, "ls-files") + _git_paths(
    repo_root, "ls-files", "--others", "--exclude-standard"
)
```

The implementation copies **`git ls-files` PLUS `git ls-files --others
--exclude-standard`** (untracked-but-not-ignored files) into the sandbox. The
docstring justifies this as "so an agent's freshly-written, not-yet-committed
parser/harness edits are present."

### Why this is a contract deviation

Every authoritative statement of the sandbox input says **tracked paths only**:

- plan.md:180 (R2 mitigation): "copy only `git ls-files` tracked paths, exclude
  `data/`,`.venv`,`.git`,`kitty-specs/`,`.worktrees/`".
- research.md:53-54 (D2): "The copy is built from `git ls-files`-tracked paths so
  the input tree is deterministic from a clean checkout (NFR-002)."
- WP03 prompt, Context/grounding: "build the copy from `git ls-files` (tracked
  paths only) so the input is reproducible from a clean clone."
- WP03 T010 step: "Resolve tracked files via `git -C <repo_root> ls-files`."
- WP03 Risks/R2: "copy only tracked paths."

No contract permits untracked inclusion. There is no sandbox-contract markdown
under `contracts/` that overrides this; the tracked-only rule is the contract.

### Why the deviation is also unnecessary (so it cannot be waved through)

The justification ("freshly-written parser must appear") does not hold for either
flow that uses the sandbox:

- **Repeatable check (research.md D3, lines 58-70):** the reference parser lives
  under `tests/fixtures/` (a *tracked* path) and is installed **into** the
  sandbox via `install_parser()` — "installed only into the sandbox." The parser
  arrives by being copied IN, not by the sandbox scooping up parent-repo
  untracked files. Your own `install_parser()` (sandbox.py:131) is exactly this
  mechanism, and your tests use it.
- **Live trial (contracts/live-trial-seam.md):** `Operator.operate(sandbox,
  goal)` edits files **inside the already-built sandbox tree**. The agent's edits
  happen post-build, in the temp copy — never in the parent working tree.

So no consumer needs parent-repo untracked files in the sandbox. The docstring
even concedes the feature is inert on the contracted path: "From a clean clone
the untracked set is empty." That means it only changes behavior when the parent
tree is *dirty* — the exact non-deterministic case the contract excludes.

### Why it is a real determinism + PHI-containment smell (not hypothetical)

`EXCLUDED_TOP_LEVEL` only filters five top-level segments. Any untracked file
whose top-level segment is NOT one of those five gets copied. Demonstrated in
this very worktree:

```
$ git ls-files --others --exclude-standard
.spec-kitty/review-lock.json        # top-level ".spec-kitty" — NOT excluded → COPIED
```

A transient orchestration lock file lands in the sandbox. Whatever untracked
scratch an agent leaves at the repo root (a `notes.md`, a `tmp/` dir, a stray
`*.csv`) would likewise be copied. The sandbox is therefore reproducible only
from a *clean* tree — violating NFR-002 ("reproducible from a clean clone") in
spirit by adding a code path whose sole purpose is to ingest a dirty tree, and
weakening NFR-004 containment (arbitrary root-level untracked content enters the
isolation boundary).

### Required change

Build the tracked-file list from `git ls-files` **only**. Delete the
`--others --exclude-standard` call:

```python
def _tracked_files(repo_root: Path) -> list[str]:
    paths = _git_paths(repo_root, "ls-files")
    kept: list[str] = []
    seen: set[str] = set()
    for rel in paths:
        if rel in seen:
            continue
        seen.add(rel)
        top = rel.split("/", 1)[0]
        if top in EXCLUDED_TOP_LEVEL:
            continue
        kept.append(rel)
    return kept
```

Update the docstring accordingly (drop the "untracked-not-ignored … freshly
written parser" rationale; state tracked-only + the EXCLUDED_TOP_LEVEL filter).

If you believe untracked inclusion is genuinely needed, do NOT re-add it here —
raise a contract amendment (plan R2 / research D2) first and get it approved;
then it can land with a test.

### Add a regression test

`test_sandbox_contains_only_tracked_tree` currently asserts only presence of
known tracked files and absence of the five excluded dirs — it never asserts
untracked exclusion, which is why this slipped through. Add an assertion that an
untracked-not-ignored file created at the repo root before build does **not**
appear in the sandbox (or, more simply, assert the copied set equals the
`git ls-files` set minus `EXCLUDED_TOP_LEVEL`).

---

## Verified GOOD (no action needed)

These were checked rigorously and pass; recording so the next cycle need not
re-litigate them.

- **FR-021 single-writer (PASS).** Independent grep of `ingest_runner.py` for
  `session_log` returns nothing (exit 1). Runner imports only stdlib +
  `from premura.store import duck, loader` (lazy, inside `run()`). It writes only
  stdout (the envelope) and the sandbox warehouse via `loader.load`. The
  `sandbox.py` `session_log_path` attribute is fine (not an import in the
  runner). Covered both statically (`test_runner_source_has_no_session_log_import`)
  and behaviorally (`test_runner_does_not_write_session_log` asserts the
  session-log file never exists after the subprocess run).

- **Envelope schema conformance (PASS, both paths).** Tests load the schema FILE
  (`ingest-outcome-envelope.schema.json`) via `_load_envelope_schema()` and call
  `jsonschema.validate(instance=envelope, schema=schema)` on the OK path
  (`test_runner_emits_valid_envelope_good`) and the ERROR path
  (`test_runner_envelope_on_error`) — not a hand-rolled subset.
  `test_runner_envelope_has_no_extra_keys` independently asserts
  `set(envelope) <= schema.properties` (additionalProperties:false) and that all
  `schema.required` keys are present on the OK path. Field semantics match the
  real seam: `LoadStats.{batch_id,rows_inserted,rows_skipped_dup,rows_skipped_priority}`,
  `IngestBatch.{declared_metrics, emitted_metrics(→set, sorted in runner for
  determinism), unmapped_metrics, skipped_rows(SkippedRow dataclass→asdict),
  source_path, attach_source_artifact}`. Error path zeroes/empties payload, sets
  `error:{kind,message}`, exits non-zero.

- **Presence-vs-absence (PASS).** OK path asserts status/declared/emitted/unmapped/
  load_stats values; error path asserts status=error + populated error object +
  non-zero exit. Black-box on the parsed envelope dict and on filesystem state.

- **Teardown / FR-020 / NFR-004 (PASS).** `teardown()` + `__exit__` do
  `shutil.rmtree`; `test_teardown_removes_everything` asserts the root is gone,
  and `test_context_manager_guarantees_cleanup` asserts removal even when the
  `with` body raises. `data/` is created empty in the sandbox and the test
  asserts `list((root/"data").iterdir()) == []` — real `data/` (PHI/warehouse) is
  never copied (it is in EXCLUDED_TOP_LEVEL).

- **Gates (ALL GREEN).**
  - `ruff check src/premura/harness tests/test_sandbox.py` → All checks passed.
  - `ruff format --check …` → 4 files already formatted.
  - `mypy src/premura/harness` → Success: no issues found in 3 source files.
  - `pytest tests/test_sandbox.py -q` → 10 passed.

- **Scope (CLEAN).** `git show 0d69e0f --stat` touches only the four owned files.

Once Issue 1 is addressed (tracked-only copy + regression test, or an approved
contract amendment), this WP is ready to approve.
