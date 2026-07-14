"""Install-from-docs fresh-clone tier (issue #55).

The deterministic first rung of the install tier (#10): hand a fresh agent
nothing but a cold clone and assert the documented onboarding path
(AGENTS.md / README.md — ``uv sync`` → ``uv run hpipe bootstrap`` → a smoke
ingest of the bundled synthetic scenario fixture) actually works from a cold
environment. This is a regression guard on the closed #8 docs-by-audience work.

``regression``-marked (slow, network for package download) and therefore
**excluded from the default pytest suite** — a real ``git clone`` + a real
``uv sync`` is never in the fast feedback path. Run it explicitly with
``uv run python -m pytest -q -m regression``.

A model-driven variant (a model reading the docs and improvising) is a
deliberate follow-up, out of scope for this slice.
"""

from __future__ import annotations

import shutil

import pytest

from premura.config import REPO_ROOT
from premura.harness import scoreboard
from premura.harness.sandbox import INSTALL_TIER, run_install_tier

pytestmark = pytest.mark.regression


def test_documented_onboarding_works_from_cold_clone(tmp_path):
    """Cold clone → uv sync → hpipe bootstrap → synthetic smoke ingest, all green.

    Records the outcome under the ``install`` tier in a scratch scoreboard so the
    capability floor (#10) can watch it, without ever touching the real one.
    """
    if shutil.which("git") is None or shutil.which("uv") is None:
        pytest.skip("install tier needs `git` and `uv` on PATH")

    result = run_install_tier(REPO_ROOT)

    # Record the run under the `install` tier via the existing scoreboard path.
    # Scripted, not model-driven, so operator/driver are the sentinel "scripted".
    scoreboard.append_scoreboard(
        scoreboard.ScoreboardEntry(
            ts="install-tier",
            operator_model="scripted",
            driver_model="scripted",
            attempts_used=1,
            first_attempt_pass=result.passed,
            final_pass=result.passed,
            tier=INSTALL_TIER,
        ),
        path=tmp_path / "scoreboard.jsonl",
    )

    # Assert the whole documented path worked; a failure names the first broken step.
    failure = result.first_failure
    assert result.passed, (
        f"documented onboarding broke at step {failure.name!r}:\n{failure.detail}"
        if failure
        else "install tier failed with no recorded step"
    )
    assert result.rows_inserted > 0

    # The tier landed on the scoreboard under the right axis so #10 can read it.
    entries = scoreboard.read_scoreboard(path=tmp_path / "scoreboard.jsonl")
    assert [e.tier for e in entries] == [INSTALL_TIER]
