"""Test package.

Depth-independent path anchors. Tests are organized into subsystem
subfolders (engine/, mcp/, intake/, ...); anchoring fixture and repo
lookups here - not off each test's own ``__file__`` - keeps those paths
correct no matter how deep a test file sits.
"""

from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
CONTRACTS_DIR = TESTS_DIR / "contracts"
