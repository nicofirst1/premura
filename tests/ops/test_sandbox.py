"""WP03 — sandbox + in-sandbox ingest runner (FR-020, FR-021).

Black-box tests over the throwaway sandbox and the subprocess ingest runner. The
runner emits a JSON outcome envelope on stdout that MUST validate against
``contracts/ingest-outcome-envelope.schema.json`` (R4); the runner must NEVER
write the session log (single-writer rule, FR-021).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from premura.config import REPO_ROOT
from premura.harness import build_sandbox
from tests import CONTRACTS_DIR, FIXTURES_DIR

FIXTURE_DIR = FIXTURES_DIR / "session_log"
GOOD_PARSER = FIXTURE_DIR / "parsers" / "good_fitbit_hr.py"
SYNTHETIC_CSV = FIXTURE_DIR / "fitbit_heart_rate_synthetic.csv"
ENVELOPE_SCHEMA = CONTRACTS_DIR / "ingest-outcome-envelope.schema.json"

# These reference fixtures are committed with the mission (WP04); their absence is
# a HARD failure, never a skip — a vanished committed fixture must block the gate,
# not pass green.
_missing = [p.name for p in (GOOD_PARSER, SYNTHETIC_CSV) if not p.exists()]
if _missing:
    raise FileNotFoundError(
        f"Committed session-log fixtures missing: {_missing}. "
        "They ship with the mission; their absence must fail the suite, not skip it."
    )


def _load_envelope_schema() -> dict:
    return json.loads(ENVELOPE_SCHEMA.read_text(encoding="utf-8"))


def _run_runner(sandbox, *, source: Path, parser: str) -> subprocess.CompletedProcess[str]:
    """Invoke the ingest runner as a subprocess rooted in the sandbox.

    The sandbox's own ``src`` is placed on PYTHONPATH so the subprocess imports
    the sandbox copy of ``premura`` (and any installed parser), not the parent's
    already-loaded package — giving it its own DuckDB handles.
    """
    env = {
        "PYTHONPATH": str(sandbox.root / "src"),
        "PATH": __import__("os").environ.get("PATH", ""),
        "HOME": __import__("os").environ.get("HOME", ""),
    }
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "premura.harness.ingest_runner",
            "--source",
            str(source),
            "--parser",
            parser,
            "--warehouse",
            str(sandbox.warehouse_path),
        ],
        cwd=sandbox.root,
        env=env,
        capture_output=True,
        text=True,
    )


# --------------------------------------------------------------------------- #
# Sandbox build / teardown (T010, T011)
# --------------------------------------------------------------------------- #


def test_sandbox_contains_only_tracked_tree() -> None:
    """The sandbox is built from ``git ls-files`` and excludes junk/huge dirs."""
    with build_sandbox(REPO_ROOT) as sandbox:
        # tracked source present
        assert (sandbox.root / "src" / "premura" / "__init__.py").exists()
        assert (sandbox.root / "src" / "premura" / "parsers" / "base.py").exists()
        # excluded trees absent
        assert not (sandbox.root / ".git").exists()
        assert not (sandbox.root / ".venv").exists()
        assert not (sandbox.root / "kitty-specs").exists()
        assert not (sandbox.root / ".worktrees").exists()
        # the redirect target dir exists but holds NO copied real data — the real
        # data/ tree (PHI, huge warehouse) was never copied (R2 / NFR-004).
        assert list((sandbox.root / "data").iterdir()) == []


def test_sandbox_excludes_untracked_not_ignored_files() -> None:
    """An untracked-not-ignored file at the repo root is NOT copied (R2 / NFR-002).

    The build is ``git ls-files``-only. A freshly-created untracked sentinel at
    the repo root (matching no ``.gitignore`` rule, so ``git ls-files --others
    --exclude-standard`` would list it) must never enter the sandbox — otherwise
    a dirty parent tree would leak transient scratch (e.g. orchestration locks)
    into the isolation boundary and break clean-checkout reproducibility.
    """
    sentinel = REPO_ROOT / "_sandbox_untracked_sentinel.txt"
    sentinel.write_text("transient untracked scratch\n", encoding="utf-8")
    # Guard: the sentinel really is untracked-not-ignored in this checkout, so
    # the test would have FAILED under the old `--others --exclude-standard` copy.
    others = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    try:
        assert sentinel.name in others, "precondition: sentinel must be untracked-not-ignored"
        with build_sandbox(REPO_ROOT) as sandbox:
            assert not (sandbox.root / sentinel.name).exists()
            # Stronger: the copied set is exactly git ls-files minus EXCLUDED_TOP_LEVEL.
            from premura.harness.sandbox import EXCLUDED_TOP_LEVEL

            tracked = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "ls-files"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.split()
            expected = {rel for rel in tracked if rel.split("/", 1)[0] not in EXCLUDED_TOP_LEVEL}
            copied = {
                str(p.relative_to(sandbox.root).as_posix())
                for p in sandbox.root.rglob("*")
                if p.is_file() and p.relative_to(sandbox.root).parts[0] != "data"
            }
            # Every copied file is a tracked, non-excluded path (no untracked leak).
            assert copied <= expected
    finally:
        sentinel.unlink(missing_ok=True)


def test_sandbox_redirects_warehouse_and_session_log_paths() -> None:
    """Warehouse + session-log paths live inside the sandbox temp tree."""
    with build_sandbox(REPO_ROOT) as sandbox:
        assert sandbox.warehouse_path.is_relative_to(sandbox.root)
        assert sandbox.session_log_path.is_relative_to(sandbox.root)
        # distinct files (never share a writer)
        assert sandbox.warehouse_path != sandbox.session_log_path
        assert sandbox.isolation_tag
        assert sandbox.premura_version


def test_teardown_removes_everything() -> None:
    """After teardown nothing under the sandbox root persists (NFR-004)."""
    sandbox = build_sandbox(REPO_ROOT)
    root = sandbox.root
    assert root.exists()
    sandbox.teardown()
    assert not root.exists()


def test_context_manager_guarantees_cleanup() -> None:
    """Even on an exception inside the ``with`` block, the tree is removed."""
    captured_root: Path | None = None
    with pytest.raises(RuntimeError):
        with build_sandbox(REPO_ROOT) as sandbox:
            captured_root = sandbox.root
            assert captured_root.exists()
            raise RuntimeError("boom")
    assert captured_root is not None
    assert not captured_root.exists()


def test_install_parser_puts_module_in_sandbox_tree() -> None:
    """``install_parser`` copies a reference parser into the sandbox src tree."""
    from premura.harness import install_parser

    with build_sandbox(REPO_ROOT) as sandbox:
        dest = install_parser(
            sandbox,
            GOOD_PARSER,
            "src/premura/parsers/_sandbox_good_fitbit_hr.py",
        )
        assert dest.exists()
        assert dest.is_relative_to(sandbox.root)
        # importable within a subprocess rooted at the sandbox
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import premura.parsers._sandbox_good_fitbit_hr as m; "
                "print(m.GoodFitbitHrParser().source_kind)",
            ],
            cwd=sandbox.root,
            env={
                "PYTHONPATH": str(sandbox.root / "src"),
                "PATH": __import__("os").environ.get("PATH", ""),
                "HOME": __import__("os").environ.get("HOME", ""),
            },
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert "fitbit_heart_rate" in proc.stdout


# --------------------------------------------------------------------------- #
# Ingest runner → envelope (T012, T013)
# --------------------------------------------------------------------------- #


def test_runner_emits_valid_envelope_good() -> None:
    """Good parser over the synthetic CSV → schema-valid status=ok envelope."""
    schema = _load_envelope_schema()
    with build_sandbox(REPO_ROOT) as sandbox:
        install_parser_dest = "src/premura/parsers/_sandbox_good_fitbit_hr.py"
        from premura.harness import install_parser

        install_parser(sandbox, GOOD_PARSER, install_parser_dest)
        proc = _run_runner(
            sandbox,
            source=SYNTHETIC_CSV,
            parser="premura.parsers._sandbox_good_fitbit_hr:GoodFitbitHrParser",
        )
        assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"

        envelope = json.loads(proc.stdout)
        # R4: validate against the cross-WP contract schema.
        jsonschema.validate(instance=envelope, schema=schema)

        assert envelope["status"] == "ok"
        assert envelope["error"] is None
        assert envelope["parser_kind"] == "GoodFitbitHrParser"
        assert envelope["declared_metrics"] == ["heart_rate"]
        assert envelope["emitted_metric_ids"] == ["heart_rate"]
        assert set(envelope["unmapped_metrics"]) == {
            "timestamp",
            "confidence",
            "altitude_m",
        }
        assert envelope["skipped_rows"] == []
        assert envelope["load_stats"]["rows_inserted"] == 5
        assert envelope["load_stats"]["rows_skipped_dup"] == 0
        assert envelope["load_stats"]["rows_skipped_priority"] == 0
        assert envelope["batch_id"]


def test_runner_envelope_has_no_extra_keys() -> None:
    """additionalProperties:false — the runner emits no extra top-level keys."""
    schema = _load_envelope_schema()
    allowed = set(schema["properties"])
    with build_sandbox(REPO_ROOT) as sandbox:
        from premura.harness import install_parser

        install_parser(sandbox, GOOD_PARSER, "src/premura/parsers/_sandbox_good_fitbit_hr.py")
        proc = _run_runner(
            sandbox,
            source=SYNTHETIC_CSV,
            parser="premura.parsers._sandbox_good_fitbit_hr:GoodFitbitHrParser",
        )
        envelope = json.loads(proc.stdout)
    assert set(envelope) <= allowed
    # required keys are always present, even on the ok path
    for key in schema["required"]:
        assert key in envelope


def test_runner_envelope_on_error() -> None:
    """A parser that raises → status=error, non-zero exit, schema-valid envelope."""
    schema = _load_envelope_schema()
    raising_parser = FIXTURE_DIR / "parsers" / "_raising_parser_src.py"
    raising_parser.write_text(
        '''"""Throwaway raising parser used only by the error-path test."""

from __future__ import annotations

from pathlib import Path


class RaisingParser:
    source_kind = "fitbit_heart_rate"
    language_hint = None

    def declares_metrics(self):
        return ["heart_rate"]

    def parse(self, path: Path):
        raise ValueError("deliberate parser failure")
''',
        encoding="utf-8",
    )
    try:
        with build_sandbox(REPO_ROOT) as sandbox:
            from premura.harness import install_parser

            install_parser(
                sandbox,
                raising_parser,
                "src/premura/parsers/_sandbox_raising.py",
            )
            proc = _run_runner(
                sandbox,
                source=SYNTHETIC_CSV,
                parser="premura.parsers._sandbox_raising:RaisingParser",
            )
            assert proc.returncode != 0
            envelope = json.loads(proc.stdout)
            jsonschema.validate(instance=envelope, schema=schema)

            assert envelope["status"] == "error"
            assert envelope["error"] is not None
            assert envelope["error"]["kind"]
            assert "deliberate parser failure" in envelope["error"]["message"]
            # required metric/array fields still present on the error path
            assert envelope["declared_metrics"] == []
            assert envelope["emitted_metric_ids"] == []
            assert envelope["unmapped_metrics"] == []
            assert envelope["skipped_rows"] == []
    finally:
        raising_parser.unlink(missing_ok=True)


def test_runner_does_not_write_session_log() -> None:
    """The runner never creates a session-log file (FR-021 single-writer)."""
    with build_sandbox(REPO_ROOT) as sandbox:
        from premura.harness import install_parser

        install_parser(sandbox, GOOD_PARSER, "src/premura/parsers/_sandbox_good_fitbit_hr.py")
        assert not sandbox.session_log_path.exists()
        proc = _run_runner(
            sandbox,
            source=SYNTHETIC_CSV,
            parser="premura.parsers._sandbox_good_fitbit_hr:GoodFitbitHrParser",
        )
        assert proc.returncode == 0, proc.stderr
        # the subprocess wrote the warehouse, but NOT the session log
        assert sandbox.warehouse_path.exists()
        assert not sandbox.session_log_path.exists()


def test_runner_source_has_no_session_log_import() -> None:
    """Static guard: the runner module imports nothing from the session-log store."""
    runner_src = REPO_ROOT / "src" / "premura" / "harness" / "ingest_runner.py"
    text = runner_src.read_text(encoding="utf-8")
    assert "session_log" not in text
