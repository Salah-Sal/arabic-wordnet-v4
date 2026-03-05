#!/usr/bin/env bash
#
# AWN4 Satellite Translation Pipeline — Host-side orchestrator
#
# Usage: ./docker/translate_all.sh [START_BATCH] [END_BATCH] [PAUSE_SECS]
#   Default: ./docker/translate_all.sh 1 53 30
#
# Prerequisites:
#   - Docker installed and running
#   - Auth: ANTHROPIC_API_KEY env var OR Claude Code authenticated (OAuth in macOS Keychain)
#   - data/satellite_input/ populated with satellites_NNNN.json files
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

START_BATCH="${1:-1}"
END_BATCH="${2:-53}"
PAUSE_SECS="${3:-30}"

IMAGE_NAME="awn4-translator"

# --- Determine auth method ---
# Priority: ANTHROPIC_API_KEY > macOS Keychain (OAuth)
AUTH_FLAGS=()
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo "Auth: ANTHROPIC_API_KEY"
    AUTH_FLAGS+=(-e "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY")
else
    # Extract OAuth credentials from macOS Keychain
    CREDS_JSON=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null || true)
    if [ -z "$CREDS_JSON" ]; then
        echo "ERROR: No auth available."
        echo "Either set ANTHROPIC_API_KEY or authenticate Claude Code on host first (run 'claude')."
        exit 1
    fi
    echo "Auth: OAuth credentials from macOS Keychain"
    AUTH_FLAGS+=(-e "CLAUDE_CREDS_JSON=$CREDS_JSON")
fi

# --- Build Docker image if needed ---
if ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
    echo "Building Docker image '$IMAGE_NAME'..."
    docker build -t "$IMAGE_NAME" "$SCRIPT_DIR"
else
    echo "Docker image '$IMAGE_NAME' already built."
fi

# --- Ensure output directory exists ---
mkdir -p "$PROJECT_DIR/data/satellite_translations"

# --- Batch processing ---
CONSECUTIVE_FAILS=0
DONE=0
FAIL=0
SKIPPED=0
TOTAL=$((END_BATCH - START_BATCH + 1))

echo ""
echo "==========================================="
echo "  AWN4 Satellite Translation Pipeline"
echo "==========================================="
echo "Batches:    ${START_BATCH}..${END_BATCH} (${TOTAL} to process)"
echo "Pause:      ${PAUSE_SECS}s between batches"
echo "Input dir:  data/satellite_input/"
echo "Output dir: data/satellite_translations/"
echo "==========================================="
echo ""

for BATCH_NUM in $(seq "$START_BATCH" "$END_BATCH"); do
    PADDED=$(printf "%04d" "$BATCH_NUM")
    OUT="$PROJECT_DIR/data/satellite_translations/batch_${PADDED}.json"

    # Resume support: skip already-completed batches
    if [ -f "$OUT" ]; then
        echo "[SKIP] batch_${PADDED} already exists"
        SKIPPED=$((SKIPPED + 1))
        CONSECUTIVE_FAILS=0
        continue
    fi

    # Check input exists
    INPUT="$PROJECT_DIR/data/satellite_input/satellites_${PADDED}.json"
    if [ ! -f "$INPUT" ]; then
        echo "[SKIP] satellites_${PADDED}.json not found in input"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    echo ""
    echo "--- Batch ${PADDED} | $(date '+%Y-%m-%d %H:%M:%S') ---"

    if docker run --rm \
        --cap-drop=ALL \
        --security-opt=no-new-privileges \
        -e "BATCH_NUM=$BATCH_NUM" \
        "${AUTH_FLAGS[@]}" \
        -v "$PROJECT_DIR/data/satellite_input:/data/input:ro" \
        -v "$PROJECT_DIR/data/satellite_translations:/data/output" \
        "$IMAGE_NAME" 2>&1; then

        DONE=$((DONE + 1))
        CONSECUTIVE_FAILS=0
        echo "[OK] batch_${PADDED} | Completed: $DONE, Failed: $FAIL"
    else
        FAIL=$((FAIL + 1))
        CONSECUTIVE_FAILS=$((CONSECUTIVE_FAILS + 1))
        echo "[FAIL] batch_${PADDED} | Consecutive failures: $CONSECUTIVE_FAILS"

        if [ "$CONSECUTIVE_FAILS" -ge 3 ]; then
            echo ""
            echo "ABORT: 3 consecutive failures — likely rate limit or quota exhaustion."
            echo "Resume later with: $0 $BATCH_NUM $END_BATCH $PAUSE_SECS"
            echo ""
            echo "Completed: $DONE | Failed: $FAIL | Skipped: $SKIPPED"
            exit 2
        fi
    fi

    # Pause between batches (skip after last batch)
    if [ "$BATCH_NUM" -lt "$END_BATCH" ]; then
        echo "Waiting ${PAUSE_SECS}s..."
        sleep "$PAUSE_SECS"
    fi
done

echo ""
echo "==========================================="
echo "  PIPELINE COMPLETE"
echo "==========================================="
echo "Completed: $DONE | Failed: $FAIL | Skipped: $SKIPPED"
echo ""
echo "Next steps:"
echo "  1. Check: ls data/satellite_translations/batch_*.json | wc -l"
echo "  2. Total: python3 -c \"import json,glob; print(sum(len(json.load(open(f))['translations']) for f in glob.glob('data/satellite_translations/batch_*.json')))\""
echo "  3. Proceed to Phase 5: python scripts/convert_to_lmf.py"
