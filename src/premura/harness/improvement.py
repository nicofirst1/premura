"""The deterministic improvement scan (improvement-hook m4 WP2, FR-3/FR-4/FR-5).

The judge (m3) writes a structured verdict into ``log_judgment``; nothing consumes
it. This module closes that loop one step: a PURE, rule-based scan that reads a
session's judgments (through the read-only FR-2 surface), looks up each judged
criterion's category in the judge rubric (reusing the m3 rubric parser — NOT a
second one), maps weak/failed evidence to an improvement **area** via a versioned
playbook (``IMPROVEMENT_PLAYBOOK.md``), and persists one durable, agent-readable
proposal per piece of evidence through the harness's sole-writer
``store.record_improvement`` surface.

It **proposes; it never acts**: no issue/PR creation, no prompt/harness/rubric/skill
edit, and it never changes ``contract_pass``, the judgment, the scoreboard, or the
trial verdict. It is fully deterministic — no model calls, no network, no randomness,
and no clock reads beyond the row timestamps the store already wrote (NFR-4/NFR-5).

Altitude (NFR-4): area semantics live in the playbook doc and criterion→category in
the rubric doc; this code keys only on the closed store vocabularies
(``CRITERION_BANDS``, ``JUDGMENT_STATUSES``) and the parsed doc structure. There is
no ``if criterion_id == ...`` ladder and no hardcoded area meaning here.

No code path here syncs or exports any row or PHI (NFR-002): it is a local,
in-process read + sole-writer write of the local session-log file.
"""

from __future__ import annotations

import importlib.resources as resources
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from premura.harness.judge import load_rubric
from premura.session_log import improvement_read, store

if TYPE_CHECKING:
    from pathlib import Path

    from premura.harness.judge import Rubric
    from premura.session_log.improvement_read import JudgmentRow

_PACKAGE = "premura.harness"
_PLAYBOOK_FILE = "IMPROVEMENT_PLAYBOOK.md"

# The two HOOK-OWNED area ids (FR-3): conditions the rubric categories cannot
# express — a judgment that did not complete, and a criterion the current rubric
# no longer defines. They are required-present in the playbook (loud failure if
# absent) but, being hook-owned conditions rather than rubric categories, their
# ids are pinned here as part of the closed scan vocabulary, not enumerated area
# semantics — the playbook still owns each area's suggested_focus + grounding.
_HARNESS_RELIABILITY_AREA = "harness_reliability"
_RUBRIC_DRIFT_AREA = "rubric_drift"


@dataclass(frozen=True, slots=True)
class Playbook:
    """The loaded improvement playbook (FR-3): its version + its area ids.

    ``areas`` is the full set of area ids parsed from the playbook headings.
    ``category_areas`` maps a rubric category to the area that maps from it (parsed
    from each area's ``maps from category:`` line) — the playbook owns this mapping
    so adding a rubric criterion never needs a playbook edit as long as its
    category already has an area. The hook-owned area ids are exposed separately.
    """

    version: str
    areas: tuple[str, ...]
    category_areas: dict[str, str]

    def area_for_category(self, category: str) -> str | None:
        """The area that maps from ``category``, or None if the playbook omits it."""
        return self.category_areas.get(category)

    @property
    def harness_reliability_area(self) -> str:
        return _HARNESS_RELIABILITY_AREA

    @property
    def rubric_drift_area(self) -> str:
        return _RUBRIC_DRIFT_AREA


@dataclass(frozen=True, slots=True)
class ProposalResult:
    """One proposal the scan derived (the persisted row's shape + idempotency flag).

    ``improvement_id`` is the id of the ``log_improvement`` row (the existing row's
    id when ``pre_existing`` is True). ``pre_existing`` is True when the
    (judgment_id, criterion_id, area) combination already had a row, so a re-scan
    reports it as already present and writes nothing new (FR-5).
    """

    improvement_id: str
    judgment_id: str
    criterion_id: str | None
    area: str
    summary: str
    evidence: str
    pre_existing: bool


def _read_playbook_text() -> str:
    """Read the bundled playbook doc (a seam tests monkeypatch to inject mangling)."""
    return resources.files(_PACKAGE).joinpath(_PLAYBOOK_FILE).read_text(encoding="utf-8")


def load_playbook() -> Playbook:
    """Load the packaged improvement playbook, failing loudly if malformed (FR-3).

    Parses ``playbook_version`` and the ``### `<area>``` area headings + their
    ``maps from category:`` lines out of ``IMPROVEMENT_PLAYBOOK.md``. A missing
    version header, no areas, or any missing REQUIRED area (the four rubric-category
    areas plus the two hook-owned ones) raises :class:`ValueError` — code never
    silently proceeds with a malformed or incomplete playbook.
    """
    text = _read_playbook_text()
    version_match = re.search(r"playbook_version:\s*([^\s`]+)", text)
    if version_match is None:
        raise ValueError(f"{_PLAYBOOK_FILE} is missing a `playbook_version:` declaration")
    version = version_match.group(1)

    areas = tuple(re.findall(r"^###\s+`([a-z0-9_]+)`", text, re.MULTILINE))
    if not areas:
        raise ValueError(f"{_PLAYBOOK_FILE} defines no areas")

    # Each area heading binds to its "maps from category: `<category>`" line, if any.
    category_areas: dict[str, str] = {}
    for match in re.finditer(
        r"^###\s+`([a-z0-9_]+)`(.*?)(?=^###\s+`|\Z)", text, re.MULTILINE | re.DOTALL
    ):
        area_id, body = match.group(1), match.group(2)
        cat_match = re.search(r"\*\*maps from category:\*\*\s*`([a-z0-9_]+)`", body)
        if cat_match:
            category_areas[cat_match.group(1)] = area_id

    # The required areas: every closed rubric category must map to an area, and the
    # two hook-owned condition areas must be present (loud failure otherwise).
    rubric = load_rubric()
    required_categories = set(rubric.criterion_categories.values())
    missing_category_areas = sorted(c for c in required_categories if c not in category_areas)
    if missing_category_areas:
        raise ValueError(
            f"{_PLAYBOOK_FILE} is missing an area for rubric categories: {missing_category_areas!r}"
        )
    for required_area in (_HARNESS_RELIABILITY_AREA, _RUBRIC_DRIFT_AREA):
        if required_area not in areas:
            raise ValueError(
                f"{_PLAYBOOK_FILE} is missing the required hook-owned area {required_area!r}"
            )

    return Playbook(version=version, areas=areas, category_areas=category_areas)


@dataclass(frozen=True, slots=True)
class _DerivedProposal:
    """A proposal the rules derived, before persistence (the dedup key + payload)."""

    criterion_id: str | None
    area: str
    summary: str
    evidence: str


def _derive_for_judgment(
    judgment: JudgmentRow, rubric: Rubric, playbook: Playbook
) -> list[_DerivedProposal]:
    """Apply the FR-4 derivation rules to one judgment (pure; no I/O)."""
    derived: list[_DerivedProposal] = []

    # Rule 1: a non-complete judgment status → one harness_reliability proposal.
    if judgment.status != "complete":
        derived.append(
            _DerivedProposal(
                criterion_id=None,
                area=playbook.harness_reliability_area,
                summary=f"judgment did not complete (status={judgment.status})",
                evidence=f"status={judgment.status}; raw_output={judgment.raw_output!r}",
            )
        )
        # A non-complete judgment carries empty criteria; nothing more to derive.
        return derived

    # Rules 2 & 3: walk the criteria. Each entry is {band, rationale}.
    for criterion_id, entry in judgment.criteria.items():
        band = entry.get("band")
        category = rubric.category_of(criterion_id)
        if category is None:
            # Rule 3: a judged criterion the current rubric does not define → drift.
            # (Drift takes precedence over the band: the category cannot be mapped.)
            derived.append(
                _DerivedProposal(
                    criterion_id=criterion_id,
                    area=playbook.rubric_drift_area,
                    summary=f"judged criterion {criterion_id!r} is not in the current rubric",
                    evidence=(
                        f"rubric_version={judgment.rubric_version}; criterion={criterion_id!r}"
                    ),
                )
            )
            continue
        if band != "weak":
            # Rule: strong / adequate / not_applicable produce nothing.
            continue
        area = playbook.area_for_category(category)
        if area is None:
            # load_playbook already enforces every category has an area, so this is
            # unreachable in a well-formed playbook; guard rather than emit a bad row.
            continue
        rationale = str(entry.get("rationale", ""))
        derived.append(
            _DerivedProposal(
                criterion_id=criterion_id,
                area=area,
                summary=f"criterion {criterion_id!r} was judged weak",
                evidence=rationale or f"criterion {criterion_id!r} banded weak (no rationale)",
            )
        )
    return derived


def scan_session(log_path: Path, *, session_id: str) -> list[ProposalResult]:
    """Scan one session's judgments and persist improvement proposals (FR-4/FR-5).

    Reads the session's judgments through the read-only FR-2 surface, derives
    proposals by the FR-4 rules (weak criterion → its category's area; non-complete
    status → ``harness_reliability``; off-rubric criterion → ``rubric_drift``), and
    persists each through ``store.record_improvement`` with status ``"open"``,
    skipping any (judgment_id, criterion_id, area) combination that already has a
    row. Re-running over the same judgments writes nothing new and returns the same
    proposals marked ``pre_existing`` (FR-5).

    The scan is PURE and deterministic: no model calls, no network, no randomness,
    no clock reads beyond the row timestamps the store already wrote. The harness
    stays the sole writer — the read is strictly read-only and the write goes
    through the existing sole-writer surface.
    """
    judgments = improvement_read.read_judgments(log_path, session_id=session_id)
    if not judgments:
        return []

    rubric = load_rubric()
    playbook = load_playbook()

    # Existing (judgment_id, criterion_id, area) keys for this session → their ids,
    # so a re-scan is idempotent and reports pre-existing proposals.
    existing: dict[tuple[str, str | None, str], str] = {
        (p.judgment_id, p.criterion_id, p.area): p.improvement_id
        for p in improvement_read.read_improvements(log_path, session_id=session_id)
    }

    conn = store.connect(log_path)
    try:
        results: list[ProposalResult] = []
        for judgment in judgments:
            for proposal in _derive_for_judgment(judgment, rubric, playbook):
                key = (judgment.judgment_id, proposal.criterion_id, proposal.area)
                if key in existing:
                    results.append(
                        ProposalResult(
                            improvement_id=existing[key],
                            judgment_id=judgment.judgment_id,
                            criterion_id=proposal.criterion_id,
                            area=proposal.area,
                            summary=proposal.summary,
                            evidence=proposal.evidence,
                            pre_existing=True,
                        )
                    )
                    continue
                improvement_id = store.record_improvement(
                    conn,
                    session_id=session_id,
                    judgment_id=judgment.judgment_id,
                    criterion_id=proposal.criterion_id,
                    area=proposal.area,
                    summary=proposal.summary,
                    evidence=proposal.evidence,
                    playbook_version=playbook.version,
                    status="open",
                )
                existing[key] = improvement_id  # guard against intra-scan duplicates
                results.append(
                    ProposalResult(
                        improvement_id=improvement_id,
                        judgment_id=judgment.judgment_id,
                        criterion_id=proposal.criterion_id,
                        area=proposal.area,
                        summary=proposal.summary,
                        evidence=proposal.evidence,
                        pre_existing=False,
                    )
                )
    finally:
        conn.close()
    return results


__all__ = [
    "Playbook",
    "ProposalResult",
    "load_playbook",
    "scan_session",
]
