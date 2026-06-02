"""The session log's own local DuckDB substrate (mission session-log-substrate).

This package owns the session log's **own** DuckDB file, schema bootstrap, and
sole-writer API — separate from the health warehouse (``hp.*``) and the
analytical research trace (``trace.*``) per FR-070 / ADR 0011. The public surface
lives in :mod:`premura.session_log.store`.
"""

from __future__ import annotations

from premura.session_log import store

__all__ = ["store"]
