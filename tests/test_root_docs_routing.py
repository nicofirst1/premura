"""Audience-routing guards for the repo-root documentation surface (issue #8).

The public interface under test is the set of root docs a reader lands on and
the route each audience is sent down:

  ``README.md``           — human deciding whether to use/try Premura
  ``AGENTS.md``           — coding agent dropped into this clone to change code
  ``CONTRIBUTING.md``     — contributor (human or agent) opening a PR
  ``docs/operating/RUNTIME_AGENT.md`` — agent operating a developed Premura
                            for a human, without editing the repo
  ``docs/README.md``      — index that must keep those audiences distinct

These tests assert stable routing claims — command names, file paths, and
boundary words — not exact prose or heading structure, so the docs can be
reworded freely without breaking the guard. Each test encodes one audience
route from the issue's TDD slices.
"""

from __future__ import annotations

from pathlib import Path

# tests/ lives at the repo root, so the repo root is one directory up.
REPO_ROOT = Path(__file__).resolve().parent.parent

README = REPO_ROOT / "README.md"
AGENTS = REPO_ROOT / "AGENTS.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
DOCS_INDEX = REPO_ROOT / "docs" / "README.md"
RUNTIME_AGENT_GUIDE = REPO_ROOT / "docs" / "operating" / "RUNTIME_AGENT.md"

# The path the rest of the docs surface uses to route to the runtime-agent guide.
RUNTIME_GUIDE_REL = "docs/operating/RUNTIME_AGENT.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- Slice 1: human / operator route ---------------------------------------


def test_readme_routes_the_human_operator() -> None:
    """README answers what Premura is, how to run it, and where to go next.

    A human landing in the root must get a plain-English statement of what the
    project is, a runnable fresh-clone command, and onward routing to the docs
    guide and the runtime-agent operating guide — without being told to read
    planning or history docs first.
    """
    text = _read(README)
    low = text.lower()
    # What it is, in plain domain language (not internal jargon).
    assert "health" in low
    # How to run it locally on a fresh clone — a runnable command, not a bare
    # console script.
    assert "uv run premura bootstrap" in low
    # Where to go next: the docs guide and the contributor path.
    assert "docs/README.md" in text
    assert "CONTRIBUTING.md" in text
    # A human who wants an agent to operate Premura for them is routed to the
    # runtime-agent guide, not into contributor/planning docs.
    assert RUNTIME_GUIDE_REL in text


# --- Slice 2: coding-agent route -------------------------------------------


def test_agents_md_routes_the_coding_agent() -> None:
    """AGENTS.md is an operational router for an agent editing this clone.

    It must point to doctrine, the maintainer vocabulary context, the
    contributor guide, the fresh-clone bootstrap command, where the checks
    live, and a PR/change workflow — and it must hand runtime operation off to
    the runtime-agent guide rather than absorbing that audience.
    """
    text = _read(AGENTS)
    low = text.lower()
    # Authoritative read order for a code agent.
    assert "DOCTRINE.md" in text
    assert "CONTEXT.md" in text
    assert "CONTRIBUTING.md" in text
    # Explicit first step on a fresh clone.
    assert "uv run premura bootstrap" in low
    # How to make a change safely / prepare a PR — routed, not restated.
    assert "pull request" in low or "pr" in low.split()
    # Runtime operation is a different audience: route it onward, do not absorb it.
    assert RUNTIME_GUIDE_REL in text


# --- Slice 3: contributor route --------------------------------------------


def test_contributing_owns_dev_and_pr_handoff() -> None:
    """CONTRIBUTING owns development setup, checks, conventions, and PR handoff."""
    text = _read(CONTRIBUTING)
    low = text.lower()
    # Development setup that actually runs on a fresh clone.
    assert "uv run premura bootstrap" in low
    # The changed-scope check set must survive here.
    for check in ("pytest", "ruff", "mypy"):
        assert check in low, f"CONTRIBUTING dropped the {check} dev check"
    # An explicit pull-request / review-handoff path, not just a vague mention.
    assert "pull request" in low
    assert "review" in low


# --- Slice 4: runtime-agent route ------------------------------------------


def test_runtime_agent_guide_exists_and_covers_operation() -> None:
    """A runtime-agent operating guide exists and covers the operating contract.

    This audience operates a developed Premura for a human through tools, not by
    editing the repo. The guide must cover MCP-first operation, human approval,
    honest handling of refusals / missing / stale data, trace disclosure, the
    PubMed citation rule, privacy / share-packet boundaries, and the operator
    fallback surface.
    """
    assert RUNTIME_AGENT_GUIDE.exists(), (
        "runtime-agent operating guide is missing at docs/operating/RUNTIME_AGENT.md"
    )
    text = _read(RUNTIME_AGENT_GUIDE)
    low = text.lower()

    # MCP/tool-first is the default operating path, not raw SQL.
    assert "premura-mcp" in low

    # The human stays on the loop: approval before sensitive actions.
    assert "approval" in low or "approve" in low

    # Honest handling of refusals, missing data, and stale data.
    assert "missing_input" in low
    assert "stale_input" in low
    assert "refus" in low  # refuse / refusal

    # Trace disclosure: how the agent shows its search effort.
    assert "research_trace_disclosure" in low

    # PubMed citation rule: only fetched records are citeable, candidates are not.
    assert "pubmed_fetch" in low
    assert "candidate" in low

    # Privacy / share-packet boundary before any public GitHub write.
    assert "share packet" in low or "share-packet" in low

    # Operator fallback surface for the explicit lower-guarantee path.
    assert "premura-mcp-operator" in low


# --- Slice 5: docs-index route ---------------------------------------------


def test_docs_index_routes_four_audiences_separately() -> None:
    """docs/README.md routes the four audiences distinctly.

    The index must send each audience to its own door and must not collapse the
    runtime agent into the coding agent: the runtime-agent guide is referenced
    as its own route alongside README, AGENTS.md, and CONTRIBUTING.md.
    """
    text = _read(DOCS_INDEX)
    # Human/operator, contributor, and coding-agent doors.
    assert "README.md" in text
    assert "CONTRIBUTING.md" in text
    assert "AGENTS.md" in text
    # The runtime agent gets its own door, not folded into AGENTS.md/CONTRIBUTING.
    # docs/README.md links relative to its own location, so match the path
    # suffix (a substring of both the repo-root and docs-relative link forms).
    assert "operating/RUNTIME_AGENT.md" in text
