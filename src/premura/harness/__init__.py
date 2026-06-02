"""Harness: throwaway sandbox + in-sandbox ingest runner (mission session-log-substrate).

The sandbox (:mod:`premura.harness.sandbox`) is the isolation mechanism that lets
an agent edit parser files and run a real ingest without touching the real repo
or warehouse (FR-020). The ingest runner
(:mod:`premura.harness.ingest_runner`) executes one parser-build ingest as a
subprocess inside a sandbox and emits a JSON outcome envelope on stdout; the
parent harness — never the runner — is the sole session-log writer (FR-021).
"""

from __future__ import annotations

from premura.harness.sandbox import (
    EXCLUDED_TOP_LEVEL,
    Sandbox,
    build_sandbox,
    install_parser,
)

__all__ = [
    "EXCLUDED_TOP_LEVEL",
    "Sandbox",
    "build_sandbox",
    "install_parser",
]
