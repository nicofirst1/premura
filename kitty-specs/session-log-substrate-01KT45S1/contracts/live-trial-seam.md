# Contract: live-trial seam (`premura.harness.live_trial`)

Built **now** as a seam; the real model invocation is **deferred** (D4). Tests
drive it with a fake `Operator` (an outside-boundary substitute, permitted by
DIRECTIVE_036).

```python
class Operator(Protocol):
    model_id: str
    def operate(self, sandbox: "Sandbox", goal: str) -> None:
        """Edit the sandbox tree to make the dropped data ingestable
        (write a parser, append dim_metric rows). For tests, a fake operator
        installs a reference parser; the deferred real operator drives a cheap
        model + the parser-generator skill."""

class Driver(Protocol):
    model_id: str
    def goal(self) -> str: ...
    def respond(self, question: str) -> str: ...   # reserved for the real-model follow-up

@dataclass
class LiveTrialConfig:
    source_dir: Path          # ~/Downloads/MyFitbitData (live trial only, never committed)
    category: str = "heart_rate"
    run_kind: str = "live_trial"

def run_live_trial(
    config: LiveTrialConfig,
    *,
    driver: Driver,
    operator: Operator,
    repo_root: Path,
    parser_attr: str,
    source: Path | None = None,
) -> Verdict:
    """Build sandbox → operator edits it → run ingest_runner → harness writes log
    → grade. Identical machinery to the repeatable check; only the agent differs.
    NEVER wired into a CI gate (NFR-005)."""
```

## Shipped signature — reconciled with slice-one reality

The shipped `run_live_trial` takes the sandbox-plumbing parameters the seam needs
to run end-to-end from a clean clone: `repo_root` (the clone to sandbox),
`parser_attr` (the attribute the operator's installed module exposes, which the
in-sandbox runner resolves as `<module>:<attr>`), and an optional `source` (the
dropped data to ingest). This is a faithful reconciliation of the contract to the
code, not a new claim that the real path is wired:

- **The slice-one fake-operator proof passes an explicit `source`** — the
  committed SYNTHETIC fixture (`fitbit_heart_rate_synthetic.csv`). When `source`
  is omitted it defaults to that same synthetic fixture; the committed seam test
  never reads the real dump.
- **`config.source_dir`** (the real `~/Downloads/MyFitbitData` dump) is consumed
  by the **real-model live-trial FOLLOW-UP (D4 / R5)**, run locally, NOT by the
  slice-one fake-operator path. No committed test reads it (C-003).
- **`Driver.respond()`** is part of the protocol but is **reserved for that
  real-model follow-up** — the scripted fake driver returns a canned value and the
  slice-one flow never calls it. It is intentionally unused now, named here so the
  deferral is explicit (DIRECTIVE_010), not a silent gap.

## Slice-one boundary

- `operator_model` / `driver_model` are captured on the session for the later
  capability-tier sweep (FR-031).
- A concrete cheap-model `Operator` and `Driver` are a **named follow-up**, not in
  this slice (recorded in plan.md Risks; refines SC-005 per DIRECTIVE_010).
- Real Fitbit data stays local; nothing under `source_dir` is ever copied into the
  repo or a commit (C-003, NFR-004).
