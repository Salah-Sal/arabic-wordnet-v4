#!/bin/bash
# Launch the full batch review inside a Docker container (DB-direct pipeline).
#
# Architecture: Claude Code is the full autonomous agent.
# The container runs run_review.sh which calls `claude -p` once per synset.
# Claude queries the Arabic dictionary SQLite DB directly via sqlite3 CLI.
#
# Security: egress firewall (default-deny whitelist inside container),
#           read-only input mounts, disposable container.
#           NET_ADMIN/NET_RAW caps required for iptables firewall setup.
#           Note: no-new-privileges is incompatible with sudo (needed for firewall).
#
# Prerequisites:
#   1. Run extract_synset_info.py on the host to generate prepared/ directory
#   2. Docker installed
#   3. Arabic dictionary DB accessible
#
# Usage:
#   ./run_batch.sh                     # Full corpus, Sonnet
#   MODEL=haiku ./run_batch.sh         # Full corpus, Haiku
#   ./run_batch.sh awn4-02592253-n     # Single synset

set -euo pipefail

# ── Paths ──
GUIDE_DIR="${GUIDE_DIR:-$HOME/Desktop/MLProjects/wn-project/arabic-wordnet-v4/experiments/linguistic_review_guide}"
CLAUDE_CODE_DB_DIR="${CLAUDE_CODE_DB_DIR:-$GUIDE_DIR/claude_code_db}"
PREPARED_DIR="${PREPARED_DIR:-$CLAUDE_CODE_DB_DIR/prepared}"
OUTPUT_DIR="${OUTPUT_DIR:-$GUIDE_DIR/output/reviews_claude_db}"
ARABIC_DICT_DB="${ARABIC_DICT_DB:-$HOME/Desktop/MLProjects/wn-project/arabic-dictionaries/db/arabic_dict.db}"

MODEL="${MODEL:-sonnet}"

mkdir -p "$OUTPUT_DIR"

# ── Validate DB exists ──
if [ ! -f "$ARABIC_DICT_DB" ]; then
    echo "Error: Arabic dictionary DB not found at $ARABIC_DICT_DB"
    echo "Set ARABIC_DICT_DB environment variable to the correct path."
    exit 1
fi

# ── Build image if needed ──
IMAGE_NAME="claude-reviewer-db"
DOCKER_DIR="$(dirname "$0")"

if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "Building Docker image: $IMAGE_NAME"
    docker build -t "$IMAGE_NAME" "$DOCKER_DIR"
fi

# ── Retrieve credentials from macOS Keychain ──
CREDS_JSON="$(security find-generic-password -s 'Claude Code-credentials' -w 2>/dev/null || echo '')"
if [ -z "$CREDS_JSON" ]; then
    echo "Warning: Could not retrieve Claude Code credentials from Keychain."
    echo "Set ANTHROPIC_API_KEY env var instead, or log in with 'claude auth login'."
fi

# ── Run ──
echo "Prepared: $PREPARED_DIR"
echo "Output:   $OUTPUT_DIR"
echo "Database: $ARABIC_DICT_DB"
echo "Model:    $MODEL"
echo "Args:     ${*:-'--all'}"
echo

docker run --rm \
    --cap-add=NET_ADMIN \
    --cap-add=NET_RAW \
    -v "$PREPARED_DIR":/workspace/prepared:ro \
    -v "$GUIDE_DIR/spec":/workspace/spec:ro \
    -v "$CLAUDE_CODE_DB_DIR/review_instructions.md":/workspace/review_instructions.md:ro \
    -v "$CLAUDE_CODE_DB_DIR/db_reference.md":/workspace/db_reference.md:ro \
    -v "$CLAUDE_CODE_DB_DIR/run_review.sh":/workspace/run_review.sh:ro \
    -v "$ARABIC_DICT_DB":/data/arabic_dict.db:ro \
    -v "$OUTPUT_DIR":/output \
    -e CLAUDE_CREDS_JSON="$CREDS_JSON" \
    -e MODEL="$MODEL" \
    -e SKIP_PERMISSIONS=1 \
    -e OUTPUT_DIR=/output \
    -e PREPARED_DIR=/workspace/prepared \
    -e SPEC_DIR=/workspace/spec \
    -e ARABIC_DICT_DB=/data/arabic_dict.db \
    "$IMAGE_NAME" \
    bash /workspace/run_review.sh "${@:---all}"
