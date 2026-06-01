# Data Model: Fresh Clone Bootstrap Agent

This mission does not add warehouse tables. The model below describes the setup-state records the CLI should produce internally and surface in its handoff output.

## BootstrapRun

Represents one invocation of the bootstrap command.

| Field | Meaning | Validation |
|---|---|---|
| `started_at` | Time the run began. | Present for every run. |
| `checkout_root` | Project root where bootstrap is running. | Must be the current Premura checkout. |
| `mode` | Whether the run is installing, verifying, or both. | Closed values chosen by implementation; default should include both local install and verification. |
| `checks` | Ordered list of `BootstrapCheck` records. | At least one check required. |
| `actions` | Ordered list of `BootstrapAction` records. | Empty allowed when already prepared. |
| `summary` | Final `BootstrapSummary`. | Required before command exits. |

## BootstrapCheck

Represents one readiness check.

| Field | Meaning | Validation |
|---|---|---|
| `name` | Stable check name shown to the agent. | Required; plain English or snake-case. |
| `category` | Setup area: project environment, command availability, skill setup, optional capability, or external prerequisite. | Must not imply health-data operation. |
| `status` | Result of the check. | Closed values: `pass`, `fixed`, `blocked`, `warning`, `skipped`. |
| `observed` | What bootstrap found. | Required for blocked/warning checks. |
| `next_action` | Concrete action for the agent/human. | Required for blocked checks; optional otherwise. |
| `local_action_allowed` | Whether bootstrap may attempt to fix it locally. | False for system-wide or sensitive actions. |

## BootstrapAction

Represents one local action bootstrap attempted.

| Field | Meaning | Validation |
|---|---|---|
| `name` | Stable action name. | Required. |
| `scope` | Where the action applies. | Must distinguish local checkout/environment from external/system scope. |
| `result` | Outcome. | Closed values: `changed`, `no_change`, `failed`, `not_attempted`. |
| `detail` | Short human-readable detail. | Required for failed actions; recommended for changed actions. |

## SkillSetupState

Represents skill installation/visibility state.

| Field | Meaning | Validation |
|---|---|---|
| `installed_count` | Number of skill files written or updated. | Integer >= 0. |
| `unchanged` | Whether all required skill files already matched package data. | Boolean. |
| `install_path` | Root where skills were materialized. | Path under the project checkout. |
| `reload_required` | Whether a new/reloaded agent session is required or recommended. | Boolean or explicit unknown represented in summary wording. |
| `message` | Plain-language guidance for the agent/human. | Required. |

## BootstrapSummary

The final handoff object.

| Field | Meaning | Validation |
|---|---|---|
| `status` | Overall result. | Closed values: `ready`, `partial`, `blocked`. |
| `ready_for_operation` | Whether the agent can proceed to normal Premura operation. | True only when required checks pass or are fixed. |
| `blockers` | Remaining required blockers. | Empty when `status=ready`. |
| `warnings` | Optional capability gaps. | Optional upload gaps belong here, not in required blockers. |
| `reload_guidance` | Whether to restart/reload agent session before using newly installed skills. | Required on every run. |
| `next_step` | One safe next action. | Required; must not be an ingest or analysis action unless user already supplied that separate goal. |

## State Transitions

```text
not_started
  -> checking_prerequisites
  -> installing_local_dependencies
  -> installing_or_verifying_skills
  -> verifying_readiness
  -> ready | partial | blocked
```

Rules:

- `blocked` means at least one required prerequisite remains unresolved.
- `partial` means local install is usable but optional capability or session visibility needs user/agent follow-up.
- `ready` means the local checkout is prepared for normal Premura operation, not that health data has been ingested.
