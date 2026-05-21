---
affected_files: []
cycle_number: 1
mission_slug: v2-architectural-skeleton-01KS4SHA
reproduction_command:
reviewed_at: '2026-05-21T12:10:48Z'
reviewer_agent: unknown
verdict: rejected
wp_id: WP04
---

# Mission Review Rollback Feedback: WP04

## Verdict

Move `WP04` back to `planned`.

## Blocking findings

1. The mission's one intentional new user-visible behavior is not reachable through the promised CLI path.
   - `pyproject.toml` declares `hpipe = "premura.cli:app"`.
   - `src/premura/cli.py` registers `install-skills`.
   - `ops/bootstrap.sh` invokes `uv run hpipe install-skills`.
   - In this checkout, after `uv sync --extra dev`, `.venv/bin/` still has no `hpipe`, and `uv run hpipe install-skills` fails with `Failed to spawn: hpipe`.
   - `uv run python -m premura.cli install-skills` does work, so the implementation exists, but the promised public entry point does not.

2. The shipped skill document repeats the same contract drift found in WP03.
   - `src/premura/skills/parser-generator/SKILL.md` says `PluginParseResult` is a "frozen dataclass".
   - The code in `src/premura/parsers/base.py` ships it mutable.

## Why this blocks acceptance

`WP04` owns the `install-skills` behavior and bootstrap plumbing. If `uv run hpipe install-skills` cannot be executed as specified, then `FR-013`, `FR-014`, and `SC-004` are not actually satisfied through the documented workflow.

## Required correction

- Fix the advertised `hpipe` invocation path so `uv run hpipe install-skills` works from a synced checkout, and
- Align the bundled skill text with the actual parser contract surface.
