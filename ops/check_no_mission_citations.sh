#!/usr/bin/env bash
# Guard: no spec-kitty mission-internal citation may leak into tracked code or docs.
#
# WHY: FR-/NFR-/SC-/WP##/T###/C-/D- tokens and kitty-specs/ paths point at a
# mission's requirements, work packages, tasks and constitution rules. Those
# artifacts live in the mission workspace and go stale the moment the mission is
# archived, so in shipped code and docs they are pure noise that misleads the
# next reader. Durable references (ADR NNNN, CONTEXT.md, contract names, issue
# #NN) are fine and are NOT matched — cite those instead of the mission token.
#
# Policy: mission citations do not belong in ANY tracked file — code, comments,
# docstrings, config or prose alike — so this scans every relevant file type,
# not only Python. Two homes legitimately carry these tokens and are excluded:
#   - docs/shared/CHANGELOG.md  (append-only mission narratives, per DOCTRINE.md)
#   - kitty-specs/              (the mission workspace itself)
#
# If a durable artifact must name a mission token (rare), quote it in prose that
# does not match a token shape, or add a narrow `--exclude`/`grep -v` line below
# with a comment justifying it — never widen by deleting an alternative.
#
# Usage: ops/check_no_mission_citations.sh [root ...]   (default: src tests docs)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

ROOTS=("$@")
if [[ ${#ROOTS[@]} -eq 0 ]]; then
  ROOTS=(src tests docs)
fi

# Case-sensitive, word-bounded so ordinary prose ("performance", "we cite") and
# clinical codes are not flagged. Each alternative is a distinctive citation shape.
PATTERN='(\b(FR|NFR|SC)-[0-9]|\bWP[0-9]{2}|\bT[0-9]{3}\b|\b[CD]-[0-9]|kitty-specs/)'

hits=$(grep -rnE "$PATTERN" "${ROOTS[@]}" \
         --include='*.py' --include='*.pyi' --include='*.md' \
         --include='*.yaml' --include='*.yml' --include='*.toml' --include='*.sh' \
         --exclude-dir='__pycache__' --exclude-dir='kitty-specs' \
         --exclude='CHANGELOG.md' \
         --exclude='check_no_mission_citations.sh' || true)

if [[ -n "$hits" ]]; then
  echo "ERROR: spec-kitty mission citations found in: ${ROOTS[*]}" >&2
  echo "These reference mission artifacts that go stale; remove them and keep only" >&2
  echo "durable refs (ADR NNNN, CONTEXT.md, contract names, issue #NN):" >&2
  echo "$hits" >&2
  exit 1
fi
echo "OK: no mission citations in: ${ROOTS[*]}"
