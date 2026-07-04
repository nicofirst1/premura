"""Pin the settled build-and-use-now parser rule across the doctrine docs.

SC-007 (mission session-log-substrate-01KT45S1, FR-130): after this mission,
``OPERATING_ROLES.md``, ADR 0010, and ``DOCTRINE.md`` state the
build-and-use-now rule consistently, and **no remaining sentence requires
review before a parser is used on the operator's own data**. The only thing
that changed is the *review-before-use* clause; the narrow "operating role =
a job the orchestrator dispatches through Premura's MCP tools" definition stays
intact (parser-building is file-editing, not an MCP operating role).

These tests assert on file *bytes* via repo-relative paths (DIRECTIVE_036), so
they fail if any of the three docs reverts the settled rule.
"""

from __future__ import annotations

import re
from pathlib import Path

# tests/ lives at the repo root; the docs are siblings under docs/.
_REPO_ROOT = Path(__file__).resolve().parent.parent

# The planning draft was superseded by the promoted architecture spec
# (ADR 0013); the settled rule now lives there.
_OPERATING_ROLES = _REPO_ROOT / "docs" / "building" / "architecture" / "OPERATING_ROLES.md"
_ADR_0010 = (
    _REPO_ROOT / "docs" / "building" / "adr" / "0010-runtime-orchestrator-and-operating-roles.md"
)
_DOCTRINE = _REPO_ROOT / "docs" / "shared" / "DOCTRINE.md"

# The exact review-before-use sentence the mission removes from
# OPERATING_ROLES.md. If it ever comes back, SC-007 has regressed.
_OLD_REVIEW_BEFORE_USE_SENTENCE = (
    "The actual code change remains outside the runtime orchestrator and goes "
    "through the existing development/review process."
)

# The canonical build-and-use phrase that must appear in the runtime docs.
_BUILD_AND_USE_PHRASE = "use it immediately for the operator's own data"

# The narrow operating-role definition that must survive unchanged: parser
# building is file-editing, not an MCP-dispatched operating role.
_OPERATING_ROLE_DEFINITION = "Parser extension is not an operating role"


def _read(path: Path) -> str:
    assert path.exists(), f"expected doctrine doc is missing: {path}"
    return path.read_bytes().decode("utf-8")


def _normalize_ws(text: str) -> str:
    """Collapse runs of whitespace so a line-wrapped sentence matches a one-line probe."""
    return re.sub(r"\s+", " ", text)


def test_no_review_before_use_sentence() -> None:
    """The review-before-use sentence must be absent from OPERATING_ROLES.md.

    The doc wraps sentences across lines, so compare against whitespace-normalized
    bytes — otherwise a wrapped copy of the sentence would slip past a raw probe.
    """
    text = _normalize_ws(_read(_OPERATING_ROLES))
    assert _OLD_REVIEW_BEFORE_USE_SENTENCE not in text, (
        "OPERATING_ROLES.md still asserts the local parser code change is "
        "reviewed before use; SC-007 forbids any remaining review-before-use "
        "sentence on the operator's own data."
    )


def test_adr_no_blanket_codebase_extension_separation() -> None:
    """ADR 0010 must no longer frame runtime as flatly separate from codebase extension.

    The pre-edit ADR said runtime "keeps runtime operation separate from
    bootstrap/setup and from codebase extension" — a blanket separation that
    forbids build-and-use of the operator's own parser. SC-007 requires that
    blanket framing be carved so local build-and-use is allowed.
    """
    text = _normalize_ws(_read(_ADR_0010))
    assert "separate from bootstrap/setup and from codebase extension" not in text, (
        "ADR 0010 still frames runtime operation as flatly separate from codebase "
        "extension without carving out build-and-use for the operator's own data."
    )


def test_build_and_use_rule_present() -> None:
    """The build-and-use phrase must appear in OPERATING_ROLES.md AND DOCTRINE.md.

    Normalize whitespace so the probe matches even when the phrase line-wraps.
    """
    roles_text = _normalize_ws(_read(_OPERATING_ROLES))
    doctrine_text = _normalize_ws(_read(_DOCTRINE))
    assert _BUILD_AND_USE_PHRASE in roles_text, (
        "OPERATING_ROLES.md must state that at runtime an agent may build a "
        f"parser and {_BUILD_AND_USE_PHRASE!r} with no reviewer."
    )
    assert _BUILD_AND_USE_PHRASE in doctrine_text, (
        "DOCTRINE.md must carry a clarifying line making build-and-use-now explicit "
        f"({_BUILD_AND_USE_PHRASE!r})."
    )


def test_adr_states_build_and_use_for_operator_data() -> None:
    """ADR 0010 must distinguish runtime build-and-use from the gated contribute-back path."""
    text = _normalize_ws(_read(_ADR_0010))
    assert _BUILD_AND_USE_PHRASE in text, (
        "ADR 0010 must allow building and using a parser immediately for the "
        "operator's own data; contribution back is the gated path."
    )


def test_operating_role_definition_unchanged() -> None:
    """The narrow operating-role definition must survive in OPERATING_ROLES.md."""
    text = _normalize_ws(_read(_OPERATING_ROLES))
    assert _OPERATING_ROLE_DEFINITION in text, (
        "OPERATING_ROLES.md must keep 'Parser extension is not an operating "
        "role' — parser-building is file-editing, not an MCP-dispatched operating "
        "role; only the review-before-use clause changes."
    )
