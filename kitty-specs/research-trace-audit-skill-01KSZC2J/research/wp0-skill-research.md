# WP0 Skill Research

This is the research gate for the research-trace audit skill (FR-001…FR-005). It
was re-run with live network access, so every finding below is confirmed against
the current primary docs rather than memory. **Plain-English note on jargon:** a
"skill" is just a folder with a `SKILL.md` instruction file an agent reads; a
"client" is the agent program that loads it (Claude Code, OpenCode, …);
"discovery" means how that program finds the folder on disk without being told.

## Sources

1. **Agent Skills standard — Specification.** <https://agentskills.io/specification.md>
   (folder shape, frontmatter fields, progressive disclosure, validation tool).
2. **Agent Skills standard — Best Practices.** <https://agentskills.io/skill-creation/best-practices.md>
   (description quality, what belongs in `SKILL.md` vs reference files,
   procedures-over-declarations, defaults-not-menus).
3. **Claude Code skills docs.** <https://code.claude.com/docs/en/skills>
   (local install homes, the `.claude/skills/` project path, live discovery,
   `/skills` verification, project-skill trust).
4. **OpenCode skills docs.** <https://opencode.ai/docs/skills/>
   (scan paths — confirmed it reads `.claude/skills/` directly, project and
   global; no CLI verify command exposed).
5. **Agent Skills doc index.** <https://agentskills.io/llms.txt> (page map used
   to locate the primary pages above).

All five are primary vendor/standard docs (FR-002 ≥ 3 satisfied).

## Skill Authoring Findings

**Folder + `SKILL.md` is confirmed, not assumed (Source 1).** A skill is a
directory whose only required file is `SKILL.md`: YAML frontmatter then Markdown.
Optional sibling dirs are exactly `scripts/`, `references/`, `assets/`, plus "any
additional files." *Consequence:* Premura's planned
`research-trace-audit/{SKILL.md, AUDIT_RUBRIC.md, fixtures/}` is conformant —
`AUDIT_RUBRIC.md` and `fixtures/` are just bundled resources. The stop-condition
"sources contradict the folder+`SKILL.md` assumption" did **not** fire.

**Frontmatter (Source 1).** Required: `name` (≤64 chars, lowercase
alphanumeric + hyphens, no leading/trailing/double hyphen, **must match the
parent directory name**) and `description` (≤1024 chars). Optional: `license`,
`compatibility` (≤500 chars; can state network/runtime needs), `metadata`
(arbitrary string map), `allowed-tools` (experimental). *Consequence for WP03:*
the directory must be `research-trace-audit/` with `name: research-trace-audit`,
or discovery/validation breaks. *What would break if assumed wrong:* a mismatched
name or uppercase fails `skills-ref validate` and some clients silently skip the
skill.

**Progressive disclosure (Source 1).** Three load tiers: (1) `name`+`description`
(~100 tokens) loaded for *all* skills at startup; (2) full `SKILL.md` body
(<5000 tokens / <500 lines recommended) loaded only on activation; (3)
resource files loaded only when the body tells the agent to read them.
*Consequence for WP03:* the `description` is the only thing the agent sees when
deciding whether to invoke — it must carry the trigger ("audit a final answer
against a Premura session research trace") and the inputs, satisfying NFR-001
(inputs findable in <2 min) at the discovery tier. *Consequence for WP02:* the
rubric and fixtures belong in sibling files, **not** inlined, so they cost no
context until the audit actually runs.

**What belongs where (Source 2).** Best practices say: put in `SKILL.md` only what
the agent *wouldn't already know* (project conventions, gotchas, the exact trace
fields); omit generic knowledge. Favor *procedures over declarations* ("how to
audit a class of answers") and *defaults, not menus*. Tell the agent **when** to
load each reference file ("read `AUDIT_RUBRIC.md` before issuing a verdict"),
never a bare "see references/." *Consequence:* this is the same guide-don't-
enumerate altitude Premura's DOCTRINE demands — the external best-practice and the
project charter agree, which de-risks WP02's rubric design.

## Installation Findings

Two install homes were in scope (FR-003): Claude-style and OpenCode-style.

**Claude Code (Source 3).** Three locations: Personal `~/.claude/skills/<name>/`,
Project `.claude/skills/<name>/` (repo-local, commit to VCS), and Plugin
`<plugin>/skills/<name>/`. Premura's existing `install_skills()` writes to
`target_root/.claude/skills/<name>/` — the **Project** location, repo-local,
already supported, no code change needed (it auto-walks every child dir with a
`SKILL.md`). *Repo-local supported:* yes. *Global supported:* yes (personal).
*Reviewer verification (NFR-006):* in a Claude Code session run the `/skills`
menu or ask "What skills are available?" — the skill must appear by name;
out-of-session, inspect that `<target>/.claude/skills/research-trace-audit/SKILL.md`
exists on disk after `install_skills()`. Project skills require accepting the
workspace-trust dialog before `allowed-tools` activate — relevant only if WP03
sets `allowed-tools` (it should not need to; the audit is pure reading).

**OpenCode (Source 4) — the decisive finding.** OpenCode scans, project-local
(walking up to the git worktree root) **and** global:

- Project: `.opencode/skills/`, **`.claude/skills/`**, `.agents/skills/`
- Global: `~/.config/opencode/skills/`, **`~/.claude/skills/`**, `~/.agents/skills/`

So OpenCode reads the **same `.claude/skills/` path Premura already installs to** —
both the repo-local and the global one. *Repo-local supported:* yes. *Global
supported:* yes. *Naming/metadata vs the standard:* none extra — same
`SKILL.md` + `name`/`description`. *Reviewer verification (NFR-006):* OpenCode
exposes **no** CLI "list skills" command in its docs; verify by (a) confirming
the file is at `.claude/skills/research-trace-audit/SKILL.md` (the path OpenCode
documents it scans) and (b) starting OpenCode in the repo and confirming the
`skill` tool lists `research-trace-audit` with its description. The stop-condition
"no authoritative source confirms an OpenCode-style local skill home" did **not**
fire — but note the home is `.claude/skills/`, not a separate OpenCode-only dir.

**Offline boundary (NFR-005, hard requirement).** Ordinary audit execution MUST
remain **OFFLINE**: no client downloads, no registry, no network at runtime. The
internet was used only at authoring time (this WP0). Both clients discover skills
purely from local files on disk — nothing here introduces a runtime network
dependency, and nothing should. The stop-condition "a target requires
network-backed installation or a package registry" did **not** fire.

## Packaging Recommendation

**Content: ADOPT write-once-by-conformance. Installer: REJECT a separate
OpenCode target for this mission.**

*One-line rationale:* the standard makes one `SKILL.md` folder portable across
clients, and OpenCode already scans the very `.claude/skills/` path Premura
installs to — so a new installer target would create dead, redundant files.

This **validates the content half** of the leading hypothesis (write-once content
by conforming to the standard) and **rejects the installer half** (the hypothesis
expected the installer to need *additional* target paths; live OpenCode docs show
it does not — it reuses `.claude/skills/`).

Tradeoffs:
- **Blast radius:** rejecting the installer extension keeps the mission purely
  additive (one new skill dir, zero changes to `install_skills()`), the smallest
  possible footprint (DIRECTIVE_024).
- **Local-first:** both clients read local files only; offline runtime preserved.
- **Maintenance:** a second writer (e.g. an `.opencode/skills/` copy) would mean
  two on-disk copies to keep in sha-sync — pure liability for zero discovery gain.
- **Reviewer verification:** one path to check serves both clients; simpler and
  less error-prone than verifying two homes.

*Conservative posture:* the only residual is that OpenCode publishes no
list-skills CLI, so its verification is file-inspection + in-session `skill`-tool
listing rather than a one-liner. That is a verification-ergonomics gap, not a
discovery gap, and does not justify writing installer code.

**Exact decision for WP04:** Do **not** extend `install_skills()`. Keep the single
`target_root/.claude/skills/` writer. WP04's scope is to *verify* (not extend)
that the existing installer materializes `research-trace-audit/` and that the path
is the documented OpenCode scan path — no new Python target, no
`test_install_skills_opencode_home.py`.

## Premura-Specific Rules

**`SKILL.md` frontmatter (WP03):** `name: research-trace-audit` (must equal the
dir name); `description` leads with the trigger and inputs — e.g. "Audit a final
analytical answer against a Premura session research trace disclosure (the
audit-consumer contract). Use when an agent or reviewer must judge whether the
answer disclosed search effort, refusals, surfaced-unavailable marks, and avoided
causal/diagnostic/significance overclaims." Optionally `compatibility` may note
"offline; reads local trace disclosure only." Do **not** rely on `allowed-tools`
(audit is read-only; avoids the trust-dialog dependency).

**`SKILL.md` vs `AUDIT_RUBRIC.md` (C-006):** `SKILL.md` holds when-to-invoke, the
required inputs (structured Session Disclosure object + final answer text), the
review *procedure*, the output shape (`pass`/`needs revision`/`blocked` +
evidence refs), and an explicit "read `AUDIT_RUBRIC.md` before issuing a verdict."
`AUDIT_RUBRIC.md` holds the bounded criteria *categories* and the rule for adding
a criterion — never a frozen banned-phrase list (DOCTRINE guide-don't-enumerate).
Packaging/install guidance stays out of both (C-006).

**Fixtures (WP02):** package under `research-trace-audit/fixtures/` as a bundled
resource (standard allows arbitrary subdirs). Synthetic Session Disclosure +
answer + expected verdict only — **no real `hp.*` rows, no PHI** in fixtures or
commits. Reference them from `SKILL.md` only with a load-when trigger.

**Install targets in scope:** exactly one — `.claude/skills/` via the existing
`install_skills()`, which simultaneously serves Claude Code (Project) and OpenCode
(its `.claude/skills/` scan path). No second target this mission.

**Checks later WPs run:** WP04 verifies, for the one supported target, that
`install_skills(target)` writes `target/.claude/skills/research-trace-audit/SKILL.md`
(+ `AUDIT_RUBRIC.md`, `fixtures/*`) with matching sha256, and that this path is the
documented Claude *and* OpenCode scan location. No semantic change to any trace
count (C-001…C-005); no runtime network (NFR-005).

## Follow-On Scope for WP04

1. **No installer code change.** Keep `install_skills()` writing only
   `.claude/skills/`. Recommendation is reject-the-second-target; do not add
   `test_install_skills_opencode_home.py`.
2. **Verification deliverable (NFR-006), per target:**
   - *Claude Code (Project `.claude/skills/`):* file-inspect
     `<target>/.claude/skills/research-trace-audit/SKILL.md` after
     `install_skills()`; in-session confirm via `/skills` / "What skills are
     available?" that `research-trace-audit` is listed.
   - *OpenCode (reuses `.claude/skills/`):* same file inspection at the same path
     (OpenCode's documented project scan path); in an OpenCode session confirm the
     `skill` tool lists `research-trace-audit`. Note in docs that OpenCode has no
     list-skills CLI, so file-inspection is the primary check.
3. **Record the dual-purpose path explicitly** so reviewers know one check covers
   both clients and there is no missing OpenCode home.
4. **Restate the offline boundary** in the install docs: discovery is local-file
   only; authoring-time internet (this WP0) is the sole network use.
