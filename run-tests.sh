#!/bin/bash
# Run the complete offline suite. Native installer acceptance is separate.
set -u
cd "$(dirname "$0")"
TMPD="$(mktemp -d "${TMPDIR:-/tmp}/kit-test.XXXXXX")"
trap 'rm -rf "$TMPD"' EXIT
PY="${PYTHON:-python3}"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "The complete suite requires Python 3.11 or newer.")' || exit 1
fail=0
run() { echo "== $*"; "$PY" "$@" > "$TMPD/out" 2>&1 || { fail=1; tail -15 "$TMPD/out"; }; tail -2 "$TMPD/out"; }
run funnel/memory.py self-check
run funnel/capture.py --self-check
for t in integration_phase0 test_batched_judges test_deadlock_policy test_retriage_batches \
         test_exact_duplicate_gate test_private_team_boundary test_team_money test_quoted_judgment test_triage_cron; do
  run "funnel/tests/$t.py"
done
run funnel/tests/test_router.py
run funnel/tests/test_safe_io_ancestor.py
run funnel/tests/test_judge_adapter.py
run funnel/tests/test_doctor.py
run -m unittest discover -s tests -p 'test_installer_*.py'
[ "$fail" -eq 0 ] && echo "ALL PASSED" || { echo "SOME FAILED"; exit 1; }
