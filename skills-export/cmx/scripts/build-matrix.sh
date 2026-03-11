#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$(pwd)}"
TASK_TEXT="${2:-}"

if [[ -z "$TASK_TEXT" ]]; then
  echo "Usage: bash scripts/build-matrix.sh <project-root> \"<task text>\"" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$SKILL_DIR/references/capability-manifest.latest.md"
OUTPUT="$SKILL_DIR/references/capability-matrix.latest.md"

bash "$SCRIPT_DIR/discover-all-capabilities.sh" "$PROJECT_DIR" > "$MANIFEST"
python3 "$SCRIPT_DIR/generate-capability-matrix.py" \
  --manifest "$MANIFEST" \
  --project "$PROJECT_DIR" \
  --task "$TASK_TEXT" \
  --out "$OUTPUT"

echo "Saved capability manifest: $MANIFEST"
echo "Saved capability matrix: $OUTPUT"
