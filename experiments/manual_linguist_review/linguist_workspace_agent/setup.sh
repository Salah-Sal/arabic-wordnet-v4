#!/usr/bin/env bash
# setup.sh — RLM Agent Workspace Setup
# Links the dictionary database and verifies dependencies.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"

echo "═══════════════════════════════════════════════════════"
echo "  RLM Agent — Evidence Collection Setup"
echo "═══════════════════════════════════════════════════════"
echo ""

# ── 1. Database ──
DB_NAME="arabic_dict.db"
TARGET="$DATA_DIR/$DB_NAME"

if [ -e "$TARGET" ]; then
    echo "[OK] Database already linked: $TARGET"
else
    DB_PATH="${1:-}"
    if [ -z "$DB_PATH" ]; then
        # Auto-detect
        for candidate in \
            "$SCRIPT_DIR/../../arabic-dictionaries/extraction/db/$DB_NAME" \
            "$SCRIPT_DIR/../linguist_workspace/data/$DB_NAME" \
            "$SCRIPT_DIR/../../arabic-dictionaries/$DB_NAME"; do
            if [ -e "$candidate" ]; then
                DB_PATH="$(cd "$(dirname "$candidate")" && pwd)/$(basename "$candidate")"
                break
            fi
        done
    fi
    if [ -z "$DB_PATH" ] || [ ! -e "$DB_PATH" ]; then
        echo "[ERROR] Database not found. Run: ./setup.sh /path/to/$DB_NAME"
        exit 1
    fi
    mkdir -p "$DATA_DIR"
    ln -s "$DB_PATH" "$TARGET"
    echo "[OK] Database linked: $TARGET -> $DB_PATH"
fi

# Verify DB
ENTRY_COUNT=$(sqlite3 "file:$TARGET?mode=ro" "SELECT COUNT(*) FROM entries;" 2>/dev/null || echo "0")
echo "     Entries: $ENTRY_COUNT"

# ── 2. Dependencies ──
echo ""
MISSING=0

for cmd in python3 sqlite3 deno; do
    if command -v "$cmd" &>/dev/null; then
        echo "[OK] $cmd found"
    else
        echo "[MISSING] $cmd"
        MISSING=1
    fi
done

# Python packages
for pkg in wn dspy yaml; do
    if python3 -c "import $pkg" 2>/dev/null; then
        echo "[OK] Python package: $pkg"
    else
        echo "[MISSING] Python package: $pkg"
        MISSING=1
    fi
done

# ── 3. wn data ──
echo ""
WN_STATUS=$(python3 -c "
import wn
lexicons = [l.specifier() for l in wn.lexicons()]
ar = [s for s in lexicons if 'awn' in s.lower()]
en = [s for s in lexicons if 'oewn' in s.lower()]
print(f'AWN4: {ar[0] if ar else \"NOT LOADED\"}')
print(f'OEWN: {en[0] if en else \"NOT LOADED\"}')
" 2>/dev/null || echo "wn library check failed")
echo "$WN_STATUS"

if [ "$MISSING" -eq 1 ]; then
    echo ""
    echo "[WARNING] Some dependencies missing. Install them before running the agent."
    exit 1
fi

echo ""
echo "Setup complete. Run the agent with:"
echo "  python run_agent.py awn4-05162506-n --verbose"
echo ""
