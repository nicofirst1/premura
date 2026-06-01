# Research: Fresh Clone Bootstrap Agent

## Decision: Add `hpipe bootstrap` as the explicit agent-facing command

**Rationale**: The user chose explicit CLI commands. The repo already exposes setup and operation through `hpipe`, and `pyproject.toml` declares `hpipe = "premura.cli:app"`. Keeping bootstrap under `hpipe` makes the fresh-clone path discoverable from the same operator surface as `doctor`, `install-skills`, and normal operation.

**Alternatives considered**:

- Extend only `ops/bootstrap.sh`: rejected because the user asked for explicit CLI commands, and the shell script currently mixes dependency install, age-key ceremony, optional rclone, and interactive prompts. It is useful source material but not the clean agent-facing handoff.
- Create a separate `premura-bootstrap` console script: rejected for first slice because it adds another public entry point and makes discovery harder for weaker agents.
- Documentation-only workflow around existing commands: rejected by the user during planning.

## Decision: Treat local dependency setup as best-effort local project-environment convergence

**Rationale**: The user clarified that the command should install missing dependencies in the local Premura folder, akin to `pip install`. The current project uses local setup guidance in `README.md` and `CONTRIBUTING.md`; `ops/bootstrap.sh` already runs local dependency sync commands and has comments about keeping console scripts materialized. The new command should express the same intent as a stable setup action: prepare the local project environment when possible, then verify.

**Alternatives considered**:

- Install global/system dependencies automatically: rejected by spec constraint C-002 and charter local-first safety. System-level prerequisites should be reported unless an existing project-approved local path handles them safely.
- Only print commands: rejected by the user's clarification that it should install missing local dependencies.
- Require health-data setup before declaring success: rejected because bootstrap is setup-only and must not ingest or inspect private health artifacts.

## Decision: Reuse skill installation behavior and add explicit reload guidance

**Rationale**: `hpipe install-skills` already materializes bundled skills under `.claude/skills/` using sha256 idempotency. Tests already cover command registration, subprocess invocation, and second-run idempotency. The bootstrap command should call or reuse this behavior rather than create another skill installer. What is missing for a fresh-clone agent is the handoff sentence: whether the current agent session can see newly installed skills or needs reload.

**Alternatives considered**:

- Build OpenCode-specific and Claude-specific installers in this mission: rejected as scope creep. Existing project skill home is already used by the repo, and the mission should only report visibility/reload guidance.
- Skip skill setup in bootstrap: rejected because the spec requires skill install/verification and reload guidance.

## Decision: Separate install readiness from optional operational readiness

**Rationale**: Current `hpipe doctor` checks `age`, `rclone`, warehouse file, age key, recipients, remote reachability, and disk. Some of those are required for full monthly operation or upload, but not necessarily for a fresh clone to be locally installed and agent-ready. Bootstrap needs a clearer readiness report: local project environment, command availability, skill state, and required setup blockers. Optional upload capability should not make the install path look failed.

**Alternatives considered**:

- Run existing `doctor` verb unchanged as the final gate: rejected because optional upload state and private warehouse existence can be irrelevant or absent in a fresh clone.
- Remove `doctor` checks from the project: rejected as unrelated. Bootstrap can coexist with the operator health check and may reuse parts of it.

## Decision: Test through public command behavior

**Rationale**: The charter requires tests through public interfaces. Existing CLI tests use `CliRunner` for Typer commands and subprocess checks for installed console scripts. Bootstrap should follow the same style: assertions on exit code, concise output, idempotency, local action reporting, and no health-data operation.

**Alternatives considered**:

- Unit-test only private helper functions: rejected because the core value is agent-operable CLI behavior.
- Full fresh-clone sandbox now: rejected because issue #10 is a larger final acceptance gate, explicitly out of scope for this mission.
