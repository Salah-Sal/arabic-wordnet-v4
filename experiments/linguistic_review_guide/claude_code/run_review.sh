#!/bin/bash
# run_review.sh — Batch driver for Claude Code autonomous linguistic review.
#
# Usage:
#   ./run_review.sh awn4-02592253-n                # single synset
#   ./run_review.sh --all                           # all prepared synsets
#   MODEL=haiku MAX_TURNS=30 ./run_review.sh --all  # custom settings
#
# Prerequisites:
#   1. Run prepare.py first to generate prepared/{synset_id}/ directories
#   2. Claude Code CLI must be installed and authenticated

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GUIDE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"  # linguistic_review_guide/
PREPARED_DIR="${PREPARED_DIR:-$SCRIPT_DIR/prepared}"
OUTPUT_DIR="${OUTPUT_DIR:-$GUIDE_DIR/output/reviews_claude}"
INSTRUCTIONS="$SCRIPT_DIR/review_instructions.md"
SPEC_DIR="${SPEC_DIR:-$GUIDE_DIR/spec}"

# Claude Code settings
MODEL="${MODEL:-sonnet}"
MAX_TURNS="${MAX_TURNS:-50}"
MAX_BUDGET="${MAX_BUDGET:-2.00}"
SKIP_PERMISSIONS="${SKIP_PERMISSIONS:-}"  # set to "1" for Docker

mkdir -p "$OUTPUT_DIR"

# ── Validate prerequisites ──
if [ ! -f "$INSTRUCTIONS" ]; then
    echo "Error: review_instructions.md not found at $INSTRUCTIONS"
    exit 1
fi

if [ ! -d "$SPEC_DIR" ]; then
    echo "Error: spec/ directory not found at $SPEC_DIR"
    exit 1
fi

# ── Determine which synsets to process ──
if [ "${1:-}" = "--all" ]; then
    if [ ! -d "$PREPARED_DIR" ]; then
        echo "Error: prepared/ directory not found. Run prepare.py first."
        exit 1
    fi
    SYNSETS=$(ls "$PREPARED_DIR" | sort)
elif [ -n "${1:-}" ]; then
    SYNSETS="$1"
    if [ ! -d "$PREPARED_DIR/$1" ]; then
        echo "Error: prepared/$1/ not found. Run prepare.py first."
        exit 1
    fi
else
    echo "Usage: $0 <synset-id|--all>"
    echo ""
    echo "Examples:"
    echo "  $0 awn4-02592253-n          # single synset"
    echo "  $0 --all                     # all prepared synsets"
    echo ""
    echo "Environment variables:"
    echo "  MODEL         Claude model (default: sonnet)"
    echo "  MAX_TURNS     Max agent turns (default: 50)"
    echo "  MAX_BUDGET    Max USD per synset (default: 2.00)"
    echo "  PREPARED_DIR  Input directory (default: ./prepared)"
    echo "  OUTPUT_DIR    Output directory (default: ./output/reviews_claude)"
    echo "  SKIP_PERMISSIONS  Set to 1 for Docker (default: off)"
    exit 1
fi

# ── Load system prompt ──
SYSTEM_PROMPT=$(cat "$INSTRUCTIONS")

# ── Prevent nested-session detection ──
unset CLAUDECODE 2>/dev/null || true

# ── Build claude CLI base args ──
CLAUDE_ARGS=(
    claude -p
    --output-format json
    --model "$MODEL"
    --max-turns "$MAX_TURNS"
    --no-session-persistence
    --verbose
)

if [ -n "$MAX_BUDGET" ]; then
    CLAUDE_ARGS+=(--max-budget-usd "$MAX_BUDGET")
fi

if [ -n "$SKIP_PERMISSIONS" ]; then
    CLAUDE_ARGS+=(--dangerously-skip-permissions)
fi

CLAUDE_ARGS+=(
    --allowedTools "Read,Write,Grep"
    --system-prompt "$SYSTEM_PROMPT"
)

# ── Process synsets ──
TOTAL=0
DONE=0
SKIP=0
FAIL=0
TOTAL_COST=0

echo "=== AWN4 Claude Code Autonomous Review ==="
echo "Model:     $MODEL"
echo "Max turns: $MAX_TURNS"
echo "Max budget per synset: \$$MAX_BUDGET"
echo "Prepared:  $PREPARED_DIR"
echo "Output:    $OUTPUT_DIR"
echo ""

for SYNSET_ID in $SYNSETS; do
    TOTAL=$((TOTAL + 1))
    REVIEW_PATH="$OUTPUT_DIR/${SYNSET_ID}.review.yaml"

    # Resume: skip if output exists
    if [ -f "$REVIEW_PATH" ]; then
        SKIP=$((SKIP + 1))
        echo "[$TOTAL] SKIP (exists): $SYNSET_ID"
        continue
    fi

    SYNSET_DIR="$PREPARED_DIR/$SYNSET_ID"

    # Verify prepared files exist
    if [ ! -f "$SYNSET_DIR/evidence.yaml" ]; then
        echo "[$TOTAL] FAIL (no evidence): $SYNSET_ID"
        FAIL=$((FAIL + 1))
        continue
    fi

    SYNSET_INFO=$(cat "$SYNSET_DIR/synset_info.yaml")
    EVIDENCE_PATH="$SYNSET_DIR/evidence.yaml"
    MASKED_PATH="$SYNSET_DIR/synset_info_masked.yaml"
    EVIDENCE_LINES=$(wc -l < "$EVIDENCE_PATH" | tr -d ' ')

    echo "[$TOTAL] Reviewing $SYNSET_ID ($EVIDENCE_LINES evidence lines)..."

    # Build user prompt
    USER_PROMPT="Review synset ${SYNSET_ID}.

## بيانات المجموعة الترادفية (synset_info)
${SYNSET_INFO}

## مسارات الملفات — File Paths
- Evidence file: ${EVIDENCE_PATH}
- Masked synset info (for Step 0.5 ONLY): ${MASKED_PATH}
- Algorithm: ${SPEC_DIR}/draft_api.md
- Output schema: ${SPEC_DIR}/output_step0.yaml

## مسار المخرجات — Output Path
Write the complete review YAML to: ${REVIEW_PATH}"

    META_PATH="$OUTPUT_DIR/${SYNSET_ID}.meta.json"

    # Run Claude Code
    if "${CLAUDE_ARGS[@]}" <<< "$USER_PROMPT" > "$META_PATH" 2>"$OUTPUT_DIR/${SYNSET_ID}.stderr.log"; then
        # Check if the review file was created by Claude
        if [ -f "$REVIEW_PATH" ]; then
            REVIEW_LINES=$(wc -l < "$REVIEW_PATH" | tr -d ' ')
            COST=$(jq -r '.total_cost_usd // 0' "$META_PATH" 2>/dev/null || echo "?")
            echo "  OK: $REVIEW_LINES lines, \$$COST"
            DONE=$((DONE + 1))
            # Accumulate cost (best effort)
            if [ "$COST" != "?" ]; then
                TOTAL_COST=$(echo "$TOTAL_COST + $COST" | bc 2>/dev/null || echo "$TOTAL_COST")
            fi
        else
            echo "  WARN: Claude completed but no review file written"
            FAIL=$((FAIL + 1))
        fi
    else
        echo "  FAIL: claude -p returned error (see ${SYNSET_ID}.stderr.log)"
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "=== Summary ==="
echo "Total: $TOTAL | Done: $DONE | Skipped: $SKIP | Failed: $FAIL"
echo "Total cost: \$$TOTAL_COST"
echo "Output: $OUTPUT_DIR/"
