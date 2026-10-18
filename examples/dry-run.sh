#!/bin/bash
# Dry run of the funnel on the example facts. Uses an offline stub judge: NO model calls.
# Writes only to a temporary directory. Needs python3 with PyYAML (pip install pyyaml).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
KIT="$(cd "$HERE/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/candidates" "$WORK/vault/03-resources/agent-systems"
printf '# captured-client-harbour-bakery\n\n## Sources\n\n- example\n' \
  > "$WORK/vault/03-resources/agent-systems/captured-client-harbour-bakery.md"
TODAY="$(date +%F)"
for f in "$HERE"/candidates/*.yaml; do
  sed "s#__EXAMPLES__#$HERE#; s#__TODAY__#$TODAY#" "$f" > "$WORK/candidates/$(basename "$f")"
done
export MEMORY_ROOT="$WORK" VAULT_ROOT="$WORK/vault"
export MEMORY_JUDGE_A_CMD="python3 $HERE/judge_stub.py"
export MEMORY_JUDGE_B_CMD="python3 $HERE/judge_stub.py"
export MEMORY_TIEBREAK_CMD="python3 $HERE/judge_stub.py"
export MEMORY_TEAM_ROUTING=0
# No --apply flag, so this is a dry run: it prints what would be promoted and writes nothing.
python3 "$KIT/funnel/memory.py" run
