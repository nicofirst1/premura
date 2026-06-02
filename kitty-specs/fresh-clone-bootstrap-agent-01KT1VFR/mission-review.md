# Mission Review Report: `fresh-clone-bootstrap-agent-01KT1VFR`

**Reviewer**: OpenCode `gpt-5.5`  
**Date**: 2026-06-01  
**Mission**: `fresh-clone-bootstrap-agent-01KT1VFR` — Fresh Clone Bootstrap Agent  
**Baseline commit**: `202e76178b43134ec0457f747522c94588d8224e`  
**Mission merge commit**: `e2c53687cfc2af5016920e223c7945325305657e`  
**HEAD at review**: `c13a1b7a095652fb6da6bbfaab55eb9176f577ef`  
**WPs reviewed**: `WP01`, `WP02`, `WP03`

**Verdict: FAIL**

The implementation is largely well-shaped, but it misses the central fresh-clone promise: the docs tell a fresh clone to run `hpipe bootstrap`, while `hpipe` itself is not available until the package/environment has already been installed. That is a blocking spec-to-delivery gap.

## Drift Findings

### DRIFT-1: Fresh-clone entry point depends on an already-installed `hpipe`

**Type**: PUNTED-FR  
**Severity**: HIGH  
**Spec reference**: `FR-001`, `SC-001`

**Evidence**:

| Artifact | Evidence |
|---|---|
| `spec.md:12` | Primary story is a freshly cloned repo where the agent installs Premura. |
| `spec.md:35` | `FR-001`: the bootstrap path must give an agent a single documented entry point for a freshly cloned checkout. |
| `spec.md:82` | `SC-001`: a fresh-clone agent can complete setup without inventing missing steps. |
| `plan.md:111-112` | The plan explicitly identified the risk: “A bootstrap command may be hard to run before dependencies are installed,” and said WPs should resolve the minimal first command needed to make `hpipe` available. |
| `README.md:14-18` | Fresh clone instructions say the first setup command is `hpipe bootstrap`. |
| `CONTRIBUTING.md:17-20` | Contributor setup says the fresh-clone agent-friendly path is `hpipe bootstrap`. |
| `quickstart.md:7-10` | Mission quickstart also says to run `hpipe bootstrap` from project root. |
| `pyproject.toml:40-41` | `hpipe` is a console script produced by package installation, not a shell command guaranteed in a fresh clone. |
| `tests/test_bootstrap_cli.py:472-488` | Console-script test skips if the installed `hpipe` binary is absent, so it does not constrain true fresh-clone bootstrapping. |

**Analysis**: The implementation created a good command once `hpipe` exists, but the mission promised a fresh-clone setup path. A freshly cloned repo with no local environment prepared will not generally have `hpipe` on `PATH`. The docs require the user/agent to already know an unstated pre-step, such as using `uv run hpipe bootstrap` or first installing the package. That is exactly the risk the plan identified and said should be resolved. This blocks the primary user story.

### DRIFT-2: Bootstrap does not verify core project surfaces promised by `FR-003`

**Type**: PUNTED-FR  
**Severity**: MEDIUM  
**Spec reference**: `FR-003`

**Evidence**:

| Artifact | Evidence |
|---|---|
| `spec.md:37` | `FR-003`: verification must report command availability, ability to start core project surfaces, and existing Premura health-check surface needed before normal operation. |
| `contracts/bootstrap-cli-contract.md:19-22` | Success path requires preparing/verifying the local environment and verifying command availability/readiness needed before normal operation. |
| `src/premura/bootstrap.py:383-478` | Implementation checks `uv`, runs `uv sync --extra dev`, installs/verifies skills, and checks optional `rclone`. It does not verify `hpipe doctor`, `premura-mcp`, `premura-mcp-operator`, or any equivalent core surface startup. |
| `tests/test_bootstrap_core.py:99-187` | Core tests cover dependency action, idempotency, missing `uv`, optional `rclone`, and reload guidance, but not core project surface startup. |
| `tests/test_bootstrap_cli.py:472-517` | Console-script coverage only proves `hpipe bootstrap` is invokable in a controlled blocked path, not that normal operational surfaces start. |

**Analysis**: The shipped command verifies local dependency sync and skill state, but not the “ability to start core project surfaces” that the spec made part of readiness. This is not as severe as DRIFT-1 because the command imports the CLI and the test suite covers its own entry point, but it still leaves part of `FR-003` effectively unimplemented.

## Risk Findings

### RISK-1: `project_root` is not used as the subprocess working directory

**Type**: BOUNDARY-CONDITION  
**Severity**: MEDIUM  
**Location**: `src/premura/bootstrap.py:345-392`, `src/premura/bootstrap.py:144-154`

**Trigger condition**: `run_bootstrap(project_root)` is called while the process current working directory is not the intended checkout root.

**Evidence**:

| Artifact | Evidence |
|---|---|
| `src/premura/bootstrap.py:345-351` | Public function accepts `project_root`. |
| `src/premura/bootstrap.py:375` | It normalizes `project_root = Path(project_root)`. |
| `src/premura/bootstrap.py:389-392` | It calls the command runner with `['uv', 'sync', '--extra', 'dev']` but does not pass `project_root` or cwd. |
| `src/premura/bootstrap.py:144-154` | Default runner calls `subprocess.run(argv, ...)` with no `cwd`. |
| `src/premura/cli.py:564` | CLI passes `Path.cwd()`, so the command works only if invoked from the intended root. |

**Analysis**: The CLI docs say to run from project root, so this is not immediately blocking. But the service contract implies `project_root` identifies the checkout to bootstrap. In reality, the local dependency action runs in the process cwd. If a caller passes a root explicitly or an agent runs the command from a subdirectory, dependency setup can target the wrong directory while skills install under the passed path.

### RISK-2: Dependency install subprocess has no timeout

**Type**: ERROR-PATH  
**Severity**: MEDIUM  
**Location**: `src/premura/bootstrap.py:144-154`

**Trigger condition**: `uv sync --extra dev` hangs because dependency resolution, network, or environment state stalls.

**Evidence**:

| Artifact | Evidence |
|---|---|
| `src/premura/bootstrap.py:149-154` | `subprocess.run(...)` is called without a timeout. |
| `spec.md:48` | `NFR-001`: successful bootstrap should complete in under 10 minutes on the supported workstation when network dependency downloads are available. |
| `tests/test_bootstrap_core.py` | Tests use a fake runner and do not constrain timeout or hang behavior. |

**Analysis**: This is not a command-injection issue because argv is a fixed list and `shell=True` is not used. The risk is operational: a fresh-clone bootstrap command can hang indefinitely rather than returning a bounded blocker/actionable failure. That weakens the agent-facing setup promise.

## FR Coverage Matrix

| FR ID | Description | WP Owner | Test File(s) | Test Adequacy | Finding |
|---|---|---|---|---|---|
| FR-001 | Single documented bootstrap entry point | WP02, WP03 | `tests/test_bootstrap_cli.py`, `tests/test_bootstrap_docs.py` | PARTIAL | DRIFT-1 |
| FR-002 | Install missing local project dependencies | WP01 | `tests/test_bootstrap_core.py` | ADEQUATE | — |
| FR-003 | Verify installed project environment and core readiness | WP01, WP02 | `tests/test_bootstrap_core.py`, `tests/test_bootstrap_cli.py` | PARTIAL | DRIFT-2 |
| FR-004 | Install/verify Premura skills | WP01, WP03 | `tests/test_bootstrap_core.py`, `tests/test_bootstrap_docs.py` | ADEQUATE | — |
| FR-005 | Report reload guidance | WP01, WP02, WP03 | `tests/test_bootstrap_core.py`, `tests/test_bootstrap_cli.py` | ADEQUATE | — |
| FR-006 | Distinguish local actions from external prerequisites | WP01 | `tests/test_bootstrap_core.py` | ADEQUATE | — |
| FR-007 | Avoid runtime health-data operation | WP01, WP02, WP03 | `tests/test_bootstrap_core.py`, `tests/test_bootstrap_cli.py`, `tests/test_bootstrap_docs.py` | ADEQUATE | — |
| FR-008 | Produce final handoff summary | WP01, WP02, WP03 | `tests/test_bootstrap_core.py`, `tests/test_bootstrap_cli.py` | ADEQUATE | — |

## Review History Notes

All WPs are `done`.

No review-cycle files were present under `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/tasks/`.

The event log shows clean approval reviews for all three WPs, followed by forced transitions from `approved` to `done` after merge:

| WP | Review summary | Done transition |
|---|---|---|
| WP01 | Approved with core tests, no shell-outs in tests, optional `rclone` warning not blocker | Forced `approved -> done` after merge commit `e2c5368` |
| WP02 | Approved with thin presenter, blockers separated, exit codes, setup-only tripwire | Forced `approved -> done` after merge commit `e2c5368` |
| WP03 | Approved with docs routing and boundary wording | Forced `approved -> done` after merge commit `e2c5368` |

The done overrides are consistent with post-merge status repair, not evidence of unresolved review disputes.

## Silent Failure Candidates

| Location | Condition | Silent result | Spec impact |
|---|---|---|---|
| `src/premura/bootstrap.py:155-156` | Local subprocess spawn raises `OSError` or `ValueError` | Converts to `CommandOutcome(returncode=127, detail=str(exc))` | Acceptable by contract: ordinary setup failures are report data, not tracebacks. |
| `src/premura/bootstrap.py:157-164` | Local command emits long stdout/stderr | Keeps only the last line as detail | Non-blocking; could hide useful resolver context, but output stays concise per `NFR-002`. |

No “return empty success” silent failure was found.

## Security Notes

| Finding | Location | Risk class | Recommendation |
|---|---|---|---|
| No shell injection found | `src/premura/bootstrap.py:149-154` | SUBPROCESS | Uses fixed argv list and no `shell=True`; acceptable. |
| Unbounded subprocess | `src/premura/bootstrap.py:149-154` | UNBOUNDED-SUBPROCESS | Add a timeout or bounded failure path so bootstrap cannot hang indefinitely. |
| Wrong cwd risk | `src/premura/bootstrap.py:149-154`, `src/premura/bootstrap.py:389-392` | PATH/WORKDIR | Run local setup commands with cwd anchored to the intended project root. |

## Validation Run

Targeted mission tests pass:

```text
uv run --extra dev python -m pytest -q tests/test_bootstrap_core.py tests/test_bootstrap_cli.py tests/test_bootstrap_docs.py --tb=short
25 passed in 0.64s
```

## Final Verdict

**FAIL**

The code is cohesive and most behavioral slices are well-tested, but the mission does not satisfy its primary fresh-clone promise. `FR-001`/`SC-001` require an agent in a fresh clone to have a single documented entry point; the shipped docs say to run `hpipe bootstrap`, but `hpipe` is only available after environment/package setup. The plan explicitly identified this bootstrap paradox and it was not resolved. `FR-003` is also only partially delivered because readiness does not verify core project surfaces. These are release-blocking fidelity gaps for this mission.
