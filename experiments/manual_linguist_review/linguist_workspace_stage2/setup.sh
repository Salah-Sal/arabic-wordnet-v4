#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# setup.sh — إعداد مساحة عمل المرحلة الثانية
# Stage 2 Linguistic Analysis Workspace Setup
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
NC="\033[0m"

WORKSPACE="$(cd "$(dirname "$0")" && pwd)"

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }

echo "═══════════════════════════════════════════════════════════════"
echo " Stage 2 — Manual Linguistic Analysis Workspace Setup"
echo "═══════════════════════════════════════════════════════════════"
echo ""

ERRORS=0

# ── 1. Check Python ──────────────────────────────────────────────────────
echo "1. Checking prerequisites..."

if command -v python3 &>/dev/null; then
    ok "python3 $(python3 --version 2>&1 | cut -d' ' -f2)"
else
    fail "python3 not found"
    ERRORS=$((ERRORS + 1))
fi

if python3 -c "import yaml" 2>/dev/null; then
    ok "pyyaml installed"
else
    fail "pyyaml not installed — run: pip install pyyaml"
    ERRORS=$((ERRORS + 1))
fi

# ── 2. Locate evidence directory ─────────────────────────────────────────
echo ""
echo "2. Locating Stage 1 evidence directory..."

EVIDENCE_DIR="${WORKSPACE}/../linguist_workspace/output/evidence"
EVIDENCE_DIR_RESOLVED=""

if [ -d "$EVIDENCE_DIR" ]; then
    EVIDENCE_DIR_RESOLVED="$(cd "$EVIDENCE_DIR" && pwd)"
    COUNT=$(ls "$EVIDENCE_DIR_RESOLVED"/*.evidence.yaml.gz 2>/dev/null | head -5 | wc -l | tr -d ' ')
    if [ "$COUNT" -gt 0 ]; then
        TOTAL=$(ls "$EVIDENCE_DIR_RESOLVED"/ | grep -c '.evidence.yaml.gz$' || echo 0)
        ok "Found evidence directory: ${EVIDENCE_DIR_RESOLVED}"
        ok "${TOTAL} evidence files (.yaml.gz)"
    else
        warn "Evidence directory exists but contains no .yaml.gz files"
        warn "Run Stage 1 pipeline first: cd ../linguist_workspace && python3 tools/run_all.py"
    fi
else
    fail "Evidence directory not found: ${EVIDENCE_DIR}"
    warn "Expected at: ../linguist_workspace/output/evidence/"
    ERRORS=$((ERRORS + 1))
fi

# ── 3. Create data/evidence symlink ──────────────────────────────────────
echo ""
echo "3. Setting up symlinks..."

mkdir -p "${WORKSPACE}/data"
if [ -n "$EVIDENCE_DIR_RESOLVED" ]; then
    if [ -L "${WORKSPACE}/data/evidence" ]; then
        rm "${WORKSPACE}/data/evidence"
    fi
    ln -sf "$EVIDENCE_DIR_RESOLVED" "${WORKSPACE}/data/evidence"
    ok "data/evidence → ${EVIDENCE_DIR_RESOLVED}"
else
    warn "Skipping evidence symlink (directory not found)"
fi

# ── 4. Check wn data (optional) ─────────────────────────────────────────
echo ""
echo "4. Checking WordNet data (optional)..."

if python3 -c "import wn" 2>/dev/null; then
    AWN=$(python3 -c "
import wn
lexicons = [l.specifier() for l in wn.lexicons()]
awn = [l for l in lexicons if 'awn' in l.lower()]
print(awn[0] if awn else 'NOT_FOUND')
" 2>/dev/null)
    if [ "$AWN" != "NOT_FOUND" ]; then
        ok "AWN4 loaded: $AWN"
    else
        warn "AWN4 not loaded (not required for prepare_synset.py)"
    fi
else
    warn "wn package not installed (not required for prepare_synset.py)"
fi

# ── 5. Verify output directory ───────────────────────────────────────────
echo ""
echo "5. Verifying output directory..."
mkdir -p "${WORKSPACE}/output"
ok "output/ directory ready"

# ── Summary ──────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then
    echo -e " ${GREEN}Setup complete!${NC}"
    echo ""
    echo " Quick start:"
    echo "   python3 tools/prepare_synset.py awn4-01572394-v"
    echo ""
    echo " This will create:"
    echo "   output/awn4-01572394-v/summary.md      ← read this"
    echo "   output/awn4-01572394-v/review.yaml      ← fill this"
    echo "   output/awn4-01572394-v/evidence.yaml     ← drill-down"
else
    echo -e " ${RED}Setup incomplete — ${ERRORS} error(s)${NC}"
    echo " Fix the errors above and re-run ./setup.sh"
fi
echo "═══════════════════════════════════════════════════════════════"
