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
    def respond(self, question: str) -> str: ...

@dataclass
class LiveTrialConfig:
    source_dir: Path          # ~/Downloads/MyFitbitData (live trial only, never committed)
    category: str = "heart_rate"
    run_kind: str = "live_trial"

def run_live_trial(config: LiveTrialConfig, *, driver: Driver, operator: Operator) -> Verdict:
    """Build sandbox → operator edits it → run ingest_runner → harness writes log
    → grade. Identical machinery to the repeatable check; only the agent differs.
    NEVER wired into a CI gate (NFR-005)."""
```

## Slice-one boundary

- `operator_model` / `driver_model` are captured on the session for the later
  capability-tier sweep (FR-031).
- A concrete cheap-model `Operator` and `Driver` are a **named follow-up**, not in
  this slice (recorded in plan.md Risks; refines SC-005 per DIRECTIVE_010).
- Real Fitbit data stays local; nothing under `source_dir` is ever copied into the
  repo or a commit (C-003, NFR-004).
