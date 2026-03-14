#!/bin/bash
# run_review.sh — Batch driver for Gemini CLI autonomous linguistic review (DB-direct).
#
# Usage:
#   ./run_review.sh awn4-02592253-n                # single synset
#   ./run_review.sh --all                           # all prepared synsets
#   MODEL=gemini-3-flash-preview MAX_TURNS=80 ./run_review.sh --all
#
# Prerequisites:
#   1. Run extract_synset_info.py first to generate prepared/{synset_id}/ directories
#   2. Gemini CLI must be installed (npm i -g @google/gemini-cli)
#   3. GEMINI_API_KEY must be set
#   4. Arabic dictionary DB must be accessible

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GUIDE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"  # linguistic_review_guide/
PREPARED_DIR="${PREPARED_DIR:-$SCRIPT_DIR/prepared}"
OUTPUT_DIR="${OUTPUT_DIR:-$GUIDE_DIR/output/reviews_gemini_db}"
INSTRUCTIONS="$SCRIPT_DIR/review_instructions.md"
DB_REFERENCE="$SCRIPT_DIR/db_reference.md"
SPEC_DIR="${SPEC_DIR:-$GUIDE_DIR/spec}"

# Database path
ARABIC_DICT_DB="${ARABIC_DICT_DB:-/Users/salahmac/Desktop/MLProjects/wn-project/arabic-dictionaries/db/arabic_dict.db}"

# Gemini CLI settings
MODEL="${MODEL:-gemini-3-flash-preview}"
MAX_TURNS="${MAX_TURNS:-80}"

mkdir -p "$OUTPUT_DIR"

# ── Validate prerequisites ──
if [ ! -f "$INSTRUCTIONS" ]; then
    echo "Error: review_instructions.md not found at $INSTRUCTIONS"
    exit 1
fi

if [ ! -f "$DB_REFERENCE" ]; then
    echo "Error: db_reference.md not found at $DB_REFERENCE"
    exit 1
fi

if [ ! -d "$SPEC_DIR" ]; then
    echo "Error: spec/ directory not found at $SPEC_DIR"
    exit 1
fi

if [ ! -f "$ARABIC_DICT_DB" ]; then
    echo "Error: Arabic dictionary DB not found at $ARABIC_DICT_DB"
    echo "Set ARABIC_DICT_DB environment variable to the correct path."
    exit 1
fi

# Quick DB sanity check
DB_ENTRIES=$(sqlite3 "$ARABIC_DICT_DB" "SELECT COUNT(*) FROM entries;" 2>/dev/null || echo "0")
if [ "$DB_ENTRIES" = "0" ]; then
    echo "Error: DB at $ARABIC_DICT_DB appears empty or inaccessible."
    exit 1
fi

# ── Determine which synsets to process ──
if [ "${1:-}" = "--all" ]; then
    if [ ! -d "$PREPARED_DIR" ]; then
        echo "Error: prepared/ directory not found. Run extract_synset_info.py first."
        exit 1
    fi
    SYNSETS=$(ls "$PREPARED_DIR" | sort)
elif [ -n "${1:-}" ]; then
    SYNSETS="$1"
    if [ ! -d "$PREPARED_DIR/$1" ]; then
        echo "Error: prepared/$1/ not found. Run extract_synset_info.py first."
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
    echo "  MODEL            Gemini model (default: gemini-3-flash-preview)"
    echo "  MAX_TURNS        Max agent turns (default: 80)"
    echo "  ARABIC_DICT_DB   Path to arabic_dict.db"
    echo "  PREPARED_DIR     Input directory (default: ./prepared)"
    echo "  OUTPUT_DIR       Output directory (default: ./output/reviews_gemini_db)"
    exit 1
fi

# ── System prompt via GEMINI_SYSTEM_MD (file-based) ──
export GEMINI_SYSTEM_MD="$INSTRUCTIONS"

# ── Process synsets ──
TOTAL=0
DONE=0
SKIP=0
FAIL=0
TOTAL_COST=0

echo "=== AWN4 Gemini CLI Autonomous Review (DB-Direct) ==="
echo "Model:     $MODEL"
echo "Max turns: $MAX_TURNS"
echo "Database:  $ARABIC_DICT_DB ($DB_ENTRIES entries)"
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

    # Verify synset_info exists
    if [ ! -f "$SYNSET_DIR/synset_info.yaml" ]; then
        echo "[$TOTAL] FAIL (no synset_info): $SYNSET_ID"
        FAIL=$((FAIL + 1))
        continue
    fi

    SYNSET_INFO=$(cat "$SYNSET_DIR/synset_info.yaml")
    MASKED_PATH="$SYNSET_DIR/synset_info_masked.yaml"

    echo "[$TOTAL] Reviewing $SYNSET_ID (DB-direct)..."

    # ── Create per-run isolated GEMINI_CLI_HOME ──
    # This provides: session isolation (no persistence), per-run settings.json,
    # and prevents disk bloat from accumulated session files.
    # We copy auth files from the real ~/.gemini/ so OAuth credentials are available.
    GEMINI_HOME=$(mktemp -d)
    REAL_GEMINI_DIR="${HOME}/.gemini"
    # GEMINI_CLI_HOME replaces $HOME; Gemini looks for files under $GEMINI_CLI_HOME/.gemini/
    mkdir -p "$GEMINI_HOME/.gemini"
    # Copy auth/identity files so Gemini CLI can authenticate via OAuth
    for f in oauth_creds.json google_accounts.json installation_id state.json; do
        [ -f "$REAL_GEMINI_DIR/$f" ] && cp "$REAL_GEMINI_DIR/$f" "$GEMINI_HOME/.gemini/$f"
    done
    # Build settings: auth from real config + our turn limit, no tool discovery
    cat > "$GEMINI_HOME/.gemini/settings.json" <<SETTINGS
{
  "security": { "auth": { "selectedType": "oauth-personal" } },
  "model": { "maxSessionTurns": $MAX_TURNS }
}
SETTINGS
    export GEMINI_CLI_HOME="$GEMINI_HOME"

    # Build user prompt
    USER_PROMPT="Review synset ${SYNSET_ID}.

## بيانات المجموعة الترادفية (synset_info)
${SYNSET_INFO}

## مسارات الملفات — File Paths
- Pre-fetched evidence (READ FIRST if exists): ${SYNSET_DIR}/evidence.json
- DB reference: ${DB_REFERENCE}
- Database path (for sqlite3 queries): ${ARABIC_DICT_DB}
- Masked synset info (for Step 0.5 ONLY): ${MASKED_PATH}
- Algorithm: ${SPEC_DIR}/draft_api.md
- Output schema: ${SPEC_DIR}/output_step0.yaml

## مسار المخرجات — Output Path
Write the complete review YAML to: ${REVIEW_PATH}"

    TRAJECTORY_PATH="$OUTPUT_DIR/${SYNSET_ID}.trajectory.jsonl"

    # ── Build Gemini CLI args ──
    # Note: Gemini's -p/--prompt takes the prompt as its string value (not stdin).
    #       --yolo is the CLI shorthand for --approval-mode yolo.
    GEMINI_ARGS=(
        gemini
        --output-format stream-json
        -m "$MODEL"
        --yolo
    )

    # Run Gemini CLI — stream-json to trajectory file
    if "${GEMINI_ARGS[@]}" -p "$USER_PROMPT" > "$TRAJECTORY_PATH" 2>"$OUTPUT_DIR/${SYNSET_ID}.stderr.log"; then
        # Check if the review file was created by Gemini
        if [ -f "$REVIEW_PATH" ]; then
            REVIEW_LINES=$(wc -l < "$REVIEW_PATH" | tr -d ' ')
            TRAJ_LINES=$(wc -l < "$TRAJECTORY_PATH" | tr -d ' ')
            # Extract cost estimate from token counts in the last result event
            RESULT_LINE=$(grep '"type":"result"' "$TRAJECTORY_PATH" | tail -1)
            if [ -n "$RESULT_LINE" ]; then
                INPUT_T=$(echo "$RESULT_LINE" | jq -r '.stats.input_tokens // 0')
                OUTPUT_T=$(echo "$RESULT_LINE" | jq -r '.stats.output_tokens // 0')
                # Gemini 2.5 Pro pricing as conservative baseline: $1.25/M input, $10.00/M output
                COST=$(echo "scale=4; $INPUT_T * 0.00000125 + $OUTPUT_T * 0.00001" | bc 2>/dev/null || echo "?")
            else
                COST="?"
            fi
            echo "  OK: $REVIEW_LINES lines, ~\$$COST (trajectory: $TRAJ_LINES events)"
            DONE=$((DONE + 1))
            # Accumulate cost (best effort)
            if [ "$COST" != "?" ]; then
                TOTAL_COST=$(echo "$TOTAL_COST + $COST" | bc 2>/dev/null || echo "$TOTAL_COST")
            fi
        else
            echo "  WARN: Gemini completed but no review file written"
            FAIL=$((FAIL + 1))
        fi
    else
        echo "  FAIL: gemini -p returned error (see ${SYNSET_ID}.stderr.log)"
        FAIL=$((FAIL + 1))
    fi

    # ── Cleanup per-run GEMINI_CLI_HOME (sessions + settings) ──
    rm -rf "$GEMINI_HOME"
done

# ── Single-synset mode: return meaningful exit code for batch_runner.py ──
if [ "$TOTAL" = "1" ]; then
    if [ "$DONE" = "1" ]; then exit 0; fi
    if [ "$SKIP" = "1" ]; then exit 0; fi
    exit 1  # failure — no review produced
fi

echo ""
echo "=== Summary ==="
echo "Total: $TOTAL | Done: $DONE | Skipped: $SKIP | Failed: $FAIL"
echo "Total estimated cost: ~\$$TOTAL_COST"
echo "Output: $OUTPUT_DIR/"
