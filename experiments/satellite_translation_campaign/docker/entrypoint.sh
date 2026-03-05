#!/bin/bash
set -euo pipefail

BATCH_NUM="${BATCH_NUM:?BATCH_NUM env var required}"
PADDED=$(printf "%04d" "$BATCH_NUM")

CLAUDE_HOME="/home/claude"

# --- Credential setup (from blog post pattern) ---
# Priority: CLAUDE_CREDS_JSON (Keychain extract) > ANTHROPIC_API_KEY
CREDS_DIR="$CLAUDE_HOME/.claude"
mkdir -p "$CREDS_DIR"

if [ -n "${CLAUDE_CREDS_JSON:-}" ]; then
    printf '%s' "$CLAUDE_CREDS_JSON" > "$CREDS_DIR/.credentials.json"
    chmod 600 "$CREDS_DIR/.credentials.json"
    echo "Auth: credentials injected from Keychain"
elif [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo "Auth: using ANTHROPIC_API_KEY"
else
    echo "ERROR: No auth provided."
    echo "Set CLAUDE_CREDS_JSON (from macOS Keychain) or ANTHROPIC_API_KEY."
    exit 1
fi

# Clear secrets from environment before running Claude
unset CLAUDE_CREDS_JSON

# --- Prepare workspace ---
INPUT="/data/input/satellites_${PADDED}.json"
if [ ! -f "$INPUT" ]; then
    echo "ERROR: Input file not found: $INPUT"
    exit 1
fi

cp "$INPUT" /workspace/input.json

ENTRIES=$(python3 -c "import json; print(len(json.load(open('/workspace/input.json'))['satellites']))")
echo "=== Batch ${PADDED}: ${ENTRIES} entries ==="

# --- Run Claude Code ---
set +e
claude -p "$(cat /workspace/prompt.txt)" \
    --dangerously-skip-permissions \
    --output-format text \
    --max-turns 25 \
    > /workspace/claude.log 2>&1
CLAUDE_RC=$?
set -e

if [ "$CLAUDE_RC" -ne 0 ]; then
    echo "WARNING: Claude Code exited with code $CLAUDE_RC"
    echo "--- Last 30 lines of log ---"
    tail -30 /workspace/claude.log
fi

# --- Check output exists ---
if [ ! -f /workspace/output.json ]; then
    echo "ERROR: Claude Code did not produce /workspace/output.json"
    echo "--- Last 50 lines of log ---"
    tail -50 /workspace/claude.log
    exit 1
fi

# --- Validate ---
python3 /validate_batch.py "$INPUT" /workspace/output.json
if [ $? -ne 0 ]; then
    echo "ERROR: Validation failed for batch ${PADDED}"
    exit 1
fi

# --- Copy validated output to mounted output directory ---
cp /workspace/output.json "/data/output/batch_${PADDED}.json"
echo "=== Batch ${PADDED} completed successfully ==="
