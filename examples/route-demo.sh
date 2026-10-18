#!/bin/bash
# Build a router index over the example notes and ask it two questions. No model calls.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
KIT="$(cd "$HERE/.." && pwd)"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
python3 "$KIT/router/build_index.py" --src "$HERE/notes" --out "$OUT"
echo "--- who approves blog posts for the bakery?"
python3 "$KIT/router/route.py" --indexdir "$OUT" --show --allow-root "$HERE/notes" "who approves blog posts for the bakery"
echo "--- style guide email tone"
python3 "$KIT/router/route.py" --indexdir "$OUT" "style guide email tone"
