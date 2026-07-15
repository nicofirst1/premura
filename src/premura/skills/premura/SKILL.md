---
name: premura
description: First-run onboarding for Premura, the local personal health-data warehouse. Run this the first time a human wants to use Premura in a coding-agent harness ("help me get started with my health data", "/premura", "set up Premura"). Chains: install-check -> what do you want to know -> what data you have -> how to collect it -> analysis. Not for a session where data is already ingested and the human just wants an answer.
---

# Premura first-run

You are opening a human's first Premura session over a coding-agent surface. Premura is a local-first, agent-operated personal health-data warehouse. Your job here is only the **onboarding chain** below - hand off to normal operation once data is flowing. You never edit Premura's code from this skill.

Two contracts bind everything you do, and this skill does not restate them - read them and stay inside them:

- `docs/operating/RUNTIME_AGENT.md` - how to operate an installed Premura honestly (validity-gated tools, structured verdicts, ask-before-sensitive-actions, never route around a refusal, never send data off-machine). If it disagrees with this skill, it wins.
- `src/premura/ui/HUMAN_FACING.md` Part B - the interview invariants: **interview before metrics**, one question at a time, agent-mediated capture (never a silent profile write, never a human form), presentation-agnostic.

The chain is the _rule_, not a script. You generate each question; the registries behind the tools decide what resolves. Do not enumerate devices or directions from memory - ask the tools.

## The chain

### 1. Install-check

Confirm the default MCP surface is reachable by calling `interview_devices` with no argument. If the interview tools respond, Premura is installed - keep this inventory response; step 3 reuses it rather than calling again.

If they are absent, the human has not registered the server yet. Tell them to run one command for their harness and reload:

```
uv run premura install-client claude   # or: opencode | codex
```

Never register or suggest the operator surface (`premura-mcp-operator --ack`) here - it is the raw-SQL escape hatch and is out of scope for onboarding.

### 2. Direction - what do you want to know

Ask what the human wants to understand about their health, before showing any number (interview-before-metrics is a hard invariant). Turn their goal into a direction and call:

```
interview_route(direction=<their goal>)
```

- `status: "routed"` -> a track with a real analysis behind it. Note `required_slots` / `missing_slots`; those are the baseline profile facts phase-2 grounding will need. Do not capture them silently - propose each as a confirmed one-fact capture when you reach it.
- `status: "refused"` -> there is no analysis behind that direction (a dead end). Say so plainly, relay the reason, and offer a direction that does resolve rather than promising something with nothing behind it.

### 3. Devices - what data you have

Use the step-1 inventory - the full set of sources Premura has a parser for:

```
interview_devices()  ->  {status: "inventory", devices: [{track_id, source_kind, collection_hint}, ...]}
```

Ask which of these they own or use. For a specific one, resolve it:

```
interview_devices(device=<name>)
```

- `status: "routed"` -> relay its `collection_hint` (step 4).
- `status: "refused"` -> Premura has no parser for that source yet. Do not pretend it works. This is an **improvement candidate** (RUNTIME_AGENT "Proposing changes"): note it, and remember a runtime agent may build-and-use a new parser for the human's own data with no review (the `parser-generator` skill) if they want to go that far now.

### 4. Collection guidance

Relay each resolved `collection_hint` and let the human gather or export the data on their own machine - collection is local, never an upload. Once they have the file(s), ingest each one with its source key:

```
uv run premura ingest --source <key> <path>
```

`--source` is required for a path: `uv run premura ingest <path>` alone defaults to `--source all`, which **ignores the path** and autodiscovers the inbox instead. Get the authoritative `<key>` list from `uv run premura ingest --help` and match it to the source you resolved in step 3 (do not guess the key from the `source_kind` string - they differ, e.g. Health Connect is `hc`). Alternatively, drop the file into Premura's inbox and run `uv run premura ingest` with no arguments to parse everything there.

Never ask a human to upload, export off-machine, or post anything to satisfy this step. Follow the RUNTIME_AGENT sensitive-action rule for anything that leaves the machine.

### 5. Analysis

Data is now in the warehouse. The onboarding chain is done - operate normally per `RUNTIME_AGENT.md`: run the chosen track's analysis through the validity-gated tools, carry the structured verdict (`available` / `missing_input` / `stale_input` / `insufficient_data`) through to the human, and narrate findings through `present_answer` under the human-facing boundaries. If grounding facts from step 2 are still missing, capture them one confirmed fact at a time before interpreting.

## Stop conditions

- A direction that will not resolve, a source with no parser, or a metric with no data are all honest answers - relay them, do not fabricate a path around them.
- You never leave the default surface, edit repo code, or move data off the machine from this skill. Any of those is a separate, human-approved step elsewhere.
