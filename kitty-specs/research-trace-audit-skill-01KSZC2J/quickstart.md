# Quickstart — Verifying the Research Trace Audit Skill

How a reviewer (agent or human) confirms the shipped skill satisfies the spec. No network
access is required for any step here (NFR-005).

## 1. The skill is discoverable and conformant

```bash
ls src/premura/skills/research-trace-audit/
# SKILL.md  AUDIT_RUBRIC.md  fixtures/
```

- `SKILL.md` has `name` + `description` frontmatter (open Agent Skills standard, matching
  `parser-generator`). A first-time reader can name the two required inputs — the Session
  Disclosure object and the final-answer text — in under 2 minutes (NFR-001), without reading
  source.
- `AUDIT_RUBRIC.md` defines the four closed criterion categories **and** the rule for adding a
  criterion (check against `contracts/rubric-criterion-contract.md`). Confirm it is **not** a
  flat banned-phrase list (Design Altitude gate).

## 2. The skill installs to the Claude-style home (always)

```bash
uv run hpipe install-skills
ls .claude/skills/research-trace-audit/SKILL.md   # present after install
```

`install_skills()` auto-discovers any child of `premura.skills` containing a `SKILL.md`, so the
new skill installs with no code change. Re-running is idempotent (sha256 skip).

## 3. Additional homes install only if WP0 recommended *adopt* (contingent)

If WP0's Skill Packaging Recommendation = `adopt`, verify the extra target documented in WP0
(e.g. an OpenCode-style skill home) using the locally-verifiable check WP0 specifies (NFR-006).
If WP0 = `defer`/`reject`, this step is intentionally absent and the recommendation explains why.

## 4. The rubric is reproducible against the fixtures (SC-002, NFR-002)

For each fixture in `fixtures/` (`pass`, `omitted-search-effort`, `hidden-refusal`,
`surfaced-unavailable`, `overclaim`):

1. Read its `disclosure` + `final_answer`.
2. Apply the rubric per `SKILL.md`.
3. Confirm the emitted Audit Result `verdict` matches `expected_verdict`, and that every
   non-`pass` result carries ≥ 1 reason with a concrete `evidence_ref` (NFR-003, SC-003).

Reproducibility check: two independent reviewer agents agree on the top-level `verdict` for
≥ 4 of the 5 fixtures (NFR-002).

## 5. The trace is untouched (C-001)

```bash
git diff --stat master -- src/premura/trace.py src/premura/store/migrations/
# empty — the skill reads the audit-consumer contract; it changes no trace count or schema
```

Confirm no fixture, rubric line, or instruction redefines `unique_hypothesis_count`, the
surfaced count, or introduces a forbidden semantic (SC-004).

## 6. Fixtures are PHI-clean

Every fixture `disclosure` is synthetic — call/result references, hashes, and bounded validity
metadata only, no real `hp.*` health rows (risk boundary 5).
