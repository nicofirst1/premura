#!/usr/bin/env bash
# Plain-language linter for premura prose docs.
# Flags banned buzzwords, weasel words, expletive openers, wordy phrases, likely
# run-on sentences (>30 words), and ungrounded markers. Advisory by design: it is
# a doc-quality aid, not a CI gate — prose judgment beats a wordlist. Run it before
# writing or reviewing a doc.
#
# Usage:
#   ops/lint_docs.sh [PATH ...]     # default: README.md + docs/
#   ops/lint_docs.sh --strict ...   # also fail on weasel words
#   ops/lint_docs.sh --quiet  ...   # summary only, no per-hit lines
#
# Exit 0 = no banned buzzwords (clean); exit 1 = banned buzzwords found
# (or, with --strict, weasel words too). Warnings never fail on their own.
set -u
cd "$(git rev-parse --show-toplevel)" || exit 1
exec 3>&1  # real stdout, so emit()'s diagnostic prints escape its `$(...)` count capture

STRICT=0; QUIET=0; PATHS=()
for a in "$@"; do
  case "$a" in
    --strict) STRICT=1 ;;
    --quiet)  QUIET=1 ;;
    *)        PATHS+=("$a") ;;
  esac
done
[ ${#PATHS[@]} -eq 0 ] && PATHS=(README.md docs)

# Hard-banned buzzwords. These FAIL the lint.
BUZZWORDS='end-to-end|leverage|synergy|seamless|holistic|robust|best-in-class|cutting-edge|world-class|performant|moat|dovetail|game-?changer|frictionless|turnkey|paradigm[ -]shift|state-of-the-art|bleeding-edge'
# Vague quantifiers / weasel words. WARN (or fail with --strict).
WEASEL='\b(various|several|numerous|myriad|plethora|a number of|a variety of|significantly|a lot of)\b'
# Expletive constructions. WARN.
EXPLETIVE='\b(there (is|are|was|were)|it is important to note|it should be noted|it is worth noting)\b'
# Stacked hedges. WARN.
HEDGE='\b(may potentially|could possibly|might possibly|may or may not|possibly might)\b'
# Wordy phrases with shorter equivalents. WARN.
WORDY='\b(in order to|due to the fact that|at this point in time|in the near future|has the ability to|utili[sz]e|going forward)\b'
# Ungrounded markers — intentional placeholders + stray TODOs. INFO (never fails).
UNGROUNDED='\[needs:|\bTBD\b|\bTODO\b|needs review|to be determined'

# Collect markdown files
mapfile -t FILES < <(find "${PATHS[@]}" -name '*.md' 2>/dev/null | sort)
[ ${#FILES[@]} -eq 0 ] && { echo "no markdown files under: ${PATHS[*]}"; exit 0; }

buzz_total=0; weasel_total=0; expl_total=0; hedge_total=0; wordy_total=0; runon_total=0; ung_total=0

# grep helper: case-insensitive, line numbers; skips fenced code blocks crudely
scan() { # $1=file $2=regex  -> prints "lineno: text"
  awk '/^```/{f=!f; next} !f{print NR": "$0}' "$1" | grep -iE "$2" 2>/dev/null
}

report_file() {
  local f="$1" any=0
  emit() { # $1=label $2=regex  -> echo hits, return count
    local label="$1" rx="$2" out n
    out=$(scan "$f" "$rx")
    n=$(printf '%s' "$out" | grep -c . )
    [ "$n" -eq 0 ] && { echo 0; return; }
    if [ "$QUIET" -eq 0 ]; then
      [ "$any" -eq 0 ] && { printf '\n%s\n' "$f" >&3; any=1; }
      printf '  %-9s (%d):\n' "$label" "$n" >&3
      printf '%s\n' "$out" | sed 's/^/      /' >&3
    fi
    echo "$n"
  }
  local b w e h wd u
  b=$(emit BUZZWORD "$BUZZWORDS");   buzz_total=$((buzz_total+b))
  w=$(emit weasel   "$WEASEL");      weasel_total=$((weasel_total+w))
  e=$(emit expletiv "$EXPLETIVE");   expl_total=$((expl_total+e))
  h=$(emit hedge    "$HEDGE");       hedge_total=$((hedge_total+h))
  wd=$(emit wordy   "$WORDY");       wordy_total=$((wordy_total+wd))
  u=$(emit needs    "$UNGROUNDED");  ung_total=$((ung_total+u))

  # Likely run-on prose lines: >30 words, not a table row / heading / code.
  local ro
  ro=$(awk '/^```/{f=!f; next} f{next}
            /^\s*\|/{next} /^\s*#/{next} /^\s*[-*0-9]+[.)]?\s/{ }
            { n=split($0,a,/[ \t]+/); if (n>30) print NR": ["n" words] "substr($0,1,80)"..." }' "$f")
  if [ -n "$ro" ]; then
    local rn; rn=$(printf '%s\n' "$ro" | grep -c .)
    runon_total=$((runon_total+rn))
    if [ "$QUIET" -eq 0 ]; then
      [ "$any" -eq 0 ] && { printf '\n%s\n' "$f"; any=1; }
      printf '  %-9s (%d):\n' "run-on?" "$rn"
      printf '%s\n' "$ro" | sed 's/^/      /'
    fi
  fi
}

echo "== Plain-language lint =="
echo "scanning ${#FILES[@]} files"
for f in "${FILES[@]}"; do report_file "$f"; done

echo
echo "== Summary =="
printf '  %-22s %d   (FAIL)\n'  "banned buzzwords"     "$buzz_total"
printf '  %-22s %d   (%s)\n'    "vague quantifiers"    "$weasel_total" "$([ $STRICT -eq 1 ] && echo FAIL || echo warn)"
printf '  %-22s %d   (warn)\n'  "expletive openers"    "$expl_total"
printf '  %-22s %d   (warn)\n'  "stacked hedges"       "$hedge_total"
printf '  %-22s %d   (warn)\n'  "wordy phrases"        "$wordy_total"
printf '  %-22s %d   (warn)\n'  "likely run-ons >30w"  "$runon_total"
printf '  %-22s %d   (resolve)\n' "ungrounded [needs:]" "$ung_total"

FAIL=0
[ "$buzz_total" -gt 0 ] && FAIL=1
[ "$STRICT" -eq 1 ] && [ "$weasel_total" -gt 0 ] && FAIL=1
echo
if [ "$FAIL" -eq 0 ]; then
  echo "PASS: no banned buzzwords$([ $STRICT -eq 1 ] && echo ' or vague quantifiers')."
else
  echo "FAIL: replace banned buzzwords with plain words. Run again to confirm."
fi
exit $FAIL
