#!/usr/bin/env bash
# Guard: no data-like file may ever be tracked by git (issue #19).
#
# Real health data lives under data/ and in warehouse/export artifacts
# (.duckdb, .db, .sqlite*, .age). Synthetic test fixtures are text formats
# (CSV/JSON/YAML) and never match these patterns. If a future synthetic
# binary fixture legitimately needs one of these extensions, add a narrow
# `grep -v` allowlist line below with a comment justifying it — never widen
# by deleting a pattern.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

pattern='\.(duckdb|duckdb\.wal|db|sqlite|sqlite3|age)$|^data/'
matches=$(git ls-files --cached --others --exclude-standard | grep -iE "$pattern" || true)

if [[ -n "${matches}" ]]; then
  echo "ERROR: data-like files are tracked or staged:" >&2
  echo "${matches}" >&2
  echo "Real health data must never enter git. See AGENTS.md and issue #19." >&2
  exit 1
fi
echo "OK: no data-like files tracked."
