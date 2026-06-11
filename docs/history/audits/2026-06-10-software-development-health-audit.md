# Software-development health audit — 2026-06-10

> Status: point-in-time audit (history doc, frozen after writing).
> Auditor: Claude (Fable 5), full-repo review at commit `a6ee259` on `master`.
> Scope: roadmap alignment, bugs, quality gates, future risks, docs structure,
> and a recommended development process.

## How this audit was done (the "process" question)

There is a standard practice for assessing a codebase's health, and this audit
followed it. Four passes, each answering a different question:

1. **Quality gates** — run the project's own automated checks (tests, linter,
   formatter, type checker) and see if they actually pass. This is the ground
   truth; docs can lie, a test run can't.
2. **Code review** — read the source looking for logic errors, edge cases, and
   privacy leaks (this repo handles real health data, so that matters extra).
3. **Docs-vs-code drift check** — take every concrete claim the live docs make
   (tool counts, signal lists, file names) and verify it against the code.
4. **Process and risk review** — the things that don't show up in any single
   file: backups, CI, git hygiene, single points of failure.

Every finding below was either produced directly by me or produced by a
research agent and then **independently re-verified** before inclusion. Two
agent findings failed verification and were discarded (noted at the end, so
you can see the filter working).

## Verdict in one paragraph

**You are on the right track.** The test suite is green (1,041 tests pass),
lint and formatting are clean, the documentation matches the code with
unusually high fidelity (every shipped-state claim I checked — tool counts,
signal registries, migrations, confound vocabulary, pinned doctrine tests —
verified against the source), and the roadmap is sequenced sensibly with an
explicit anti-roadmap keeping scope honest. The codebase shows no high-severity
bugs and no PHI/privacy leaks. The real risks are **process risks**, not code
risks: there is no CI, 60 commits exist only on this one laptop, and the
documentation structure — while sound today — has a growth pattern that will
not survive another 20 missions. None of these is hard to fix; all of them get
more expensive the longer they wait.

## 1. Quality gates — what the machines say

| Gate | Result | Meaning |
|---|---|---|
| `pytest` (default suite) | ✅ 1,041 passed, 10 deselected, ~4 min | The deselected ten are the real-data/`live_trial` tests, excluded by design. |
| `ruff check` | ✅ clean | No lint violations anywhere. |
| `ruff format --check` | ✅ 168 files formatted | No formatting drift. |
| `mypy src/` | ⚠️ **13 errors in 6 files** | See finding B1 below. |

The mypy failures are the one dirty gate. Three are environmental (missing
`types-python-dateutil` stubs — `_localtime.py:35`, `sleep_as_android.py:23`,
`bmt.py:27`); ten are real type errors, concentrated in the older parsers
(`health_connect.py:358,367` — `**dict` unpacking that defeats the type
checker, 8 errors; `garmin_gdpr.py:301`; `engine/_query.py:297`).

**Why this matters:** CONTRIBUTING.md prescribes *changed-scope* mypy, so these
legacy errors never block anyone — but they also never get fixed, and they
teach every agent that "mypy has errors" is normal. A type checker that is
allowed to stay red loses most of its value as a regression tripwire.

## 2. Bugs found (code)

The good news first: the areas most likely to harbor subtle bugs were checked
and came back clean — the local-calendar-day conversion (`_localtime.py`,
including the offset-magnitude check, which I traced by hand), the
`OLLAMA_URL` local-only enforcement (correctly restricted to
`localhost`/`127.0.0.1`/`::1`, no DNS-rebinding hole), the dedupe SQL (table
names are internal constants, not user input), the trace append-only
guarantees, NaN/zero-variance handling in the analytical tools, and the
paired-t-test constant-difference refusal.

**B1 — mypy: 10 real type errors tolerated in `src/` (medium).**
Described above. Justification for "medium": none is a live crash today, but
`health_connect.py`'s `**dict[str, object]` unpacking means the type checker
cannot verify the `Measurement` construction at all — a wrong-typed field
introduced there in a future change would sail through.

**B2 — `smoothed_average` and `rolling_mean` disagree on `min_coverage=0.0`
(low).** `rolling_mean.py:239` accepts `0.0 <= min_coverage <= 1.0`;
`analytical_tools.py:444` (smoothed_average) requires `0.0 < min_coverage`.
Two parallel tools, identical parameter meaning, different validation. Each
tool's refusal message states its own range, so this may be deliberate — but
nothing documents *why* they differ, and an agent calling both will get
inconsistent behavior. Justification: either align the bounds or write one
sentence in `engine/CONTRACT.md` saying the difference is intended.

That is the complete bug list. For a ~73-module codebase with this much
statistical edge-case surface, finding no high-severity defects is a genuinely
good result — the refusal-first design (tools refuse rather than guess) shows
up everywhere and is doing its job.

## 3. Things that can bite you later (process risks, ranked)

**R1 — No CI. Severity: the big one.**
There is no `.github/workflows/` (or any CI config). Every check above ran on
this laptop because I ran it. Nothing structurally prevents a commit that
breaks the tests from landing on `master` — the protection is purely the
discipline of the agents doing the work. In an agent-operated repo this is the
single highest-leverage fix: agents are *exactly* the contributors who benefit
from a machine gate, because a reviewer agent reading a diff can be convinced
by plausible-looking code; a CI run cannot.
*Fix:* one GitHub Actions workflow running `uv run pytest -q`, `ruff check`,
`ruff format --check`, `mypy src/`, and `uv lock --check` on every push/PR.
Roughly an afternoon of work.

**R2 — 60 commits exist only on this machine. Severity: high, trivial fix.**
`master` is ahead of `origin/master` by 60 commits (verified:
`## master...origin/master [ahead 60]`) — that is every mission since roughly
the end of May. A disk failure today loses two weeks of shipped work plus the
mission bookkeeping. *Fix:* push now; adopt a push-after-merge habit (or a
post-merge hook).

**R3 — The `age` encryption key is a single point of failure. Severity: high
if both failures coincide.** The whole backup story is: encrypted warehouse
artifact → Drive (opt-in), decryptable only with `~/.config/premura/age.key`.
`ops/bootstrap.sh` *tells* the operator to back the key up, but nothing ever
verifies it happened. Lose the laptop and the key together and ~3.5 years of
health history is gone. *Fix:* make `hpipe doctor` check the key exists and is
readable, and add a periodic reminder/`verify-backup` round-trip check.

**R4 — STATUS.md's growth pattern. Severity: medium, compounding.**
See §5 (docs structure) — this is the "will bite later" entry there.

**R5 — Leftover worktrees and one unmerged branch. Severity: low.**
Two `.worktrees/` from the `research-trace-audit-skill-01KSZC2J` mission
(merged 2026-05-31) are still on disk, one on a detached HEAD, plus the
unmerged `spec-kitty/orchestrator/research-trace-audit-skill-01KSZC2J` branch
(~10 MB and a confusion hazard for future agents; the other local branches are
all merged). *Fix:* confirm nothing unique is on them, then
`git worktree remove` + branch deletion.

**R6 — `v1.0.0` tag vs. v0.x product line. Severity: low.**
Both `v0.3.0` and `v1.0.0` exist as tags; README explains `v1.0.0` is a
historical restore point, but a tag listing sorts it as the latest release.
Any tool or person who looks at tags before reading README gets the wrong
answer. *Fix:* leave it (documented) or retag; just decide once.

**PHI/privacy: clean.** Real health data lives under `data/` and is properly
gitignored; `git ls-files` shows no `.duckdb`/`.db`/`.age` files and only
synthetic fixtures; the live-trial path enforces local-only model calls in
code. The one gap: nothing *automatically* guards against a future accidental
commit of data — a cheap CI/pre-commit check (`git ls-files` must match no
data patterns) would convert the current good behavior into a guarantee.

## 4. Roadmap alignment — are the docs telling the truth?

Yes, to an unusual degree. Spot-checks all verified against code:

- Default MCP surface: **22 tools** exactly as enumerated (operator surface 23
  with `query_warehouse`) — matches `mcp/server.py` and the pinned
  `tests/test_mcp_server.py` list.
- `engine.list_analytical_tools()` → exactly the five documented tools.
- Eight Stage 2 signals + `bmi` registered, matching the STATUS table.
- All four `SEMANTIC_DOMAINS` have concrete resolvers; migrations 001–005
  present and as described; the nine-key `ConfoundKey` vocabulary matches;
  `tests/test_doctrine_build_and_use.py` pins the build-and-use doctrine; the
  research-trace-audit skill ships with all five fixtures.

Two cosmetic doc inconsistencies: STATUS.md line ~99 still says "twenty tools"
(a historical mid-sequence count; line 39's "twenty-two" is current), and the
"eight signals" framing leaves `bmi` as a ninth signal discussed separately —
technically consistent, easy to misread.

The roadmap's *sequencing* is also sound: analytical depth was built
foundation-first (admissibility → tools → trace → grounding), the deferred
list is explicit ("named so future work is not assumed shipped" is a habit
most professional teams lack), and the anti-roadmap actively prevents scope
creep. The one roadmap-level observation: **almost everything recent is
platform/foundation work**. The next phase items (real vendor intake parser,
real SAA ingest, the tool-loop tier) are the points where the platform meets
reality — the live-trial spikes already showed reality pushes back. Prioritize
the "first real export" items; they are the cheapest source of truth about
whether the abstractions hold.

## 5. Docs structure — is it right?

**The structure is fundamentally sound; the maintenance pattern is not.**

What's right (keep it): the audience split (`building/` contributors,
`operating/` runtime agents, `using/` operators, `shared/` everyone,
`history/` archive) is real and honored — 60 markdown files and almost all sit
where their reader would look. The entry-point graph (README → AGENTS →
DOCTRINE → CONTEXT → CONTRIBUTING) is acyclic. ADRs 0001–0011 are numbered
cleanly, short, and cite code. Most projects never get this disciplined.

Three structural problems, all of the same species — **facts with more than
one home**:

1. **STATUS.md is a changelog wearing a snapshot's clothes.** It is ~500 lines
   and every mission appends a 25–105-line narrative section ("shipped
   2026-05-XX…"). Twenty more missions ≈ 1,600 lines that nobody can verify at
   a glance. The industry-standard split: a **CHANGELOG.md** (append-only,
   per-mission entries, never edited — narratives go here) plus a **short
   STATUS.md snapshot** (current counts and tables only, fully rewritable).
2. **Shipped-state numbers are restated in ~4 places.** "Twenty-two tools" /
   the signal list appear in STATUS.md, ROADMAP.md, STAGES.md, and
   FULL_APP_DEVELOPMENT_PLAN.md (the last still says "twenty"). Every new tool
   means a manual 4-file sync, and one of the four is already stale. State
   each count **once** (STATUS.md) and have the others link to it — or
   generate the inventory table from code, which can never drift.
3. **history/ docs are cited as the current rules.** Live docs point at
   `history/research/CORRELATE_METHODOLOGY_RESEARCH.md` and
   `ARCHITECTURE_HISTORY.md` for *normative* content ("the statistical choices
   are settled in…"), and STATUS.md points at a `kitty-specs/` contract file
   for the trace audit surface. If "history is frozen archive" is the rule,
   settled decisions belong in a live contract or ADR; history keeps the
   *rationale*, not the rule. (`kitty-specs/` is mission bookkeeping — a live
   contract should not have its only home there.)

This is also the per-WP-review lesson this repo has already learned applied to
docs: each mission's doc update is locally correct, and the drift lives in the
cross-document gaps no single mission owns. A "live-doc reconciliation" step
exists in the process notes; the structural fixes above shrink the surface it
has to reconcile.

## 6. Recommended process going forward

For a solo-maintainer, agent-operated repo, the right-sized process is small:

1. **CI on every push** (R1) — the machine gate agents can't talk their way
   past. *Do first.*
2. **Push after every mission merge** (R2) — the remote is the backup.
3. **Key + data-leak guarantees in automation** (R3, PHI note) — `hpipe
   doctor` checks the age key; CI checks no data file is ever tracked.
4. **CHANGELOG.md + slim STATUS.md** (docs fix 1) — adopt at the *next*
   mission; don't big-bang rewrite, just stop appending narratives to STATUS.
5. **Single-home rule for counts** (docs fix 2) — fold into the existing
   DOCTRINE self-check: *does this doc restate a fact that already has a
   home?*
6. **Burn down the 13 mypy errors once** (B1), add stubs
   (`types-python-dateutil`), then flip mypy to repo-wide-must-be-clean in CI.
7. Quarterly: re-run this audit shape (gates → bugs → drift → risks). The
   repo's own `docs/history/audits/` convention is already the right home.

## Appendix — discarded findings (verification filter)

Two findings from research agents were checked and **rejected**; recorded so
the filter is visible:

- *"Timezone offset validation bug in `_localtime.py:88` (HIGH)"* — false.
  The magnitude check runs before the sign is applied, which **is** the
  symmetric `abs(delta) > max` check; a `-25:00` offset is correctly rejected
  to UTC-fallback. Traced by hand; the code comment even documents the order.
- *"`skills-lock.json` is gitignored but still tracked"* — false.
  `git ls-files` shows it is not tracked; the `.gitignore` entry is working.
