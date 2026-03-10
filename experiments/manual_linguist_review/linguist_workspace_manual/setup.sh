#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# setup.sh — إعداد مساحة الجمع اليدوي
# Manual Evidence Collection Workspace Setup
# ═══════════════════════════════════════════════════════════════════
#
# Usage:
#   ./setup.sh                              # Auto-detect DB path
#   ./setup.sh /path/to/arabic_dict.db      # Manual DB path
#   ./setup.sh --copy                       # Copy DB instead of symlink
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"

# ── Colors ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { printf "${GREEN}✓${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}⚠${NC} %s\n" "$1"; }
fail() { printf "${RED}✗${NC} %s\n" "$1"; exit 1; }
info() { printf "${BLUE}→${NC} %s\n" "$1"; }

# ── Parse arguments ─────────────────────────────────────────────────
COPY_MODE=false
DB_PATH=""

for arg in "$@"; do
    case "$arg" in
        --copy) COPY_MODE=true ;;
        *.db)   DB_PATH="$arg" ;;
    esac
done

# ── Step 1: Check prerequisites ─────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  إعداد مساحة الجمع اليدوي — Manual Evidence Collection Setup"
echo "═══════════════════════════════════════════════════"
echo ""

info "Checking prerequisites..."

if command -v sqlite3 &>/dev/null; then
    ok "sqlite3 found: $(sqlite3 --version | head -1)"
else
    fail "sqlite3 not found. Please install sqlite3."
fi

if command -v python3 &>/dev/null; then
    ok "python3 found: $(python3 --version)"
else
    fail "python3 not found. Required for extract_synset_wn.py and scaffold_synset.py."
fi

# ── Step 2: Check Python packages ──────────────────────────────────
info "Checking Python packages..."

if python3 -c "import wn" 2>/dev/null; then
    ok "wn package installed"
else
    warn "wn package not found. Installing..."
    pip3 install wn && ok "wn installed" || fail "Failed to install wn"
fi

# ── Step 3: Locate and link database ───────────────────────────────
info "Locating arabic_dict.db..."

if [ -z "$DB_PATH" ]; then
    for p in \
        "$SCRIPT_DIR/../../../../arabic-dictionaries/db/arabic_dict.db" \
        "$SCRIPT_DIR/../../../arabic-dictionaries/db/arabic_dict.db" \
        "$HOME/arabic_dict.db" \
    ; do
        if [ -f "$p" ]; then
            DB_PATH="$(cd "$(dirname "$p")" && pwd)/$(basename "$p")"
            break
        fi
    done
fi

mkdir -p "$DATA_DIR"

if [ -z "$DB_PATH" ]; then
    fail "arabic_dict.db not found. Run: ./setup.sh /path/to/arabic_dict.db"
fi

if [ ! -f "$DB_PATH" ]; then
    fail "File not found: $DB_PATH"
fi

DEST="$DATA_DIR/arabic_dict.db"
[ -e "$DEST" ] && rm -f "$DEST"

if $COPY_MODE; then
    info "Copying database (this may take a moment)..."
    cp "$DB_PATH" "$DEST"
    ok "Database copied → data/arabic_dict.db"
else
    ln -s "$DB_PATH" "$DEST"
    ok "Database linked → data/arabic_dict.db"
fi

# ── Step 4: Verify database ────────────────────────────────────────
echo ""
info "Verifying database..."

ENTRY_COUNT=$(sqlite3 "file:$DEST?mode=ro" "SELECT COUNT(*) FROM entries;" 2>/dev/null || echo "ERROR")
DICT_COUNT=$(sqlite3 "file:$DEST?mode=ro" "SELECT COUNT(*) FROM dictionaries;" 2>/dev/null || echo "ERROR")

if [ "$ENTRY_COUNT" != "ERROR" ]; then
    ok "Database OK: $ENTRY_COUNT entries from $DICT_COUNT dictionaries"
else
    warn "Database file exists but could not be read"
fi

# ── Step 5: Verify wn data ─────────────────────────────────────────
echo ""
info "Checking wn library data..."

WN_STATUS=$(python3 -c "
import wn
lexicons = [l.specifier() for l in wn.lexicons()]
has_awn4 = any('awn4' in s for s in lexicons)
has_oewn = any('oewn' in s for s in lexicons)
if has_awn4 and has_oewn:
    print('OK')
elif has_awn4:
    print('NEED_OEWN')
elif has_oewn:
    print('NEED_AWN4')
else:
    print('NEED_BOTH')
" 2>/dev/null || echo "ERROR")

case "$WN_STATUS" in
    OK)
        ok "wn data loaded: AWN4 + OEWN available"
        ;;
    NEED_OEWN)
        warn "OEWN not loaded. Run: python3 -c \"import wn; wn.download('oewn:2024')\""
        ;;
    NEED_AWN4)
        warn "AWN4 not loaded. Run: python3 -c \"import wn; wn.add('/path/to/awn4.xml')\""
        ;;
    NEED_BOTH)
        warn "Neither AWN4 nor OEWN loaded."
        echo "  Run: python3 -c \"import wn; wn.add('/path/to/awn4.xml')\""
        echo "  Run: python3 -c \"import wn; wn.download('oewn:2024')\""
        ;;
    *)
        warn "Could not check wn data status."
        ;;
esac

# ── Done ─────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  Setup complete!"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Next steps:"
echo "  1. Generate a scaffold for a synset:"
echo "     python3 tools/scaffold_synset.py awn4-05162506-n"
echo ""
echo "  2. Open the database for manual queries:"
echo "     sqlite3 \"file:data/arabic_dict.db?mode=ro\""
echo ""
echo "  3. Browse synsets:"
echo "     python3 tools/extract_synset_wn.py --random 5"
echo ""
echo "  4. Read the step-by-step guide:"
echo "     docs/MANUAL_GUIDE.md"
echo ""
