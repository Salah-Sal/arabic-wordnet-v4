#!/bin/bash
# Container entrypoint: firewall → settings → exec
# Runs as 'node' user (firewall via sudo).

# 1. Initialize egress firewall (default-deny whitelist)
echo "Initializing firewall..."
if sudo /usr/local/bin/init-firewall.sh; then
    echo "Firewall active."
else
    echo "WARNING: Firewall setup failed. Continuing without network restrictions."
fi
echo ""

# 2. Settings handling: write settings.json with turn limit and auth config
# Gemini CLI reads GEMINI_API_KEY from env directly — no credential file needed.
GEMINI_DIR="/home/node/.gemini"
mkdir -p "$GEMINI_DIR"

MAX_TURNS="${MAX_TURNS:-80}"

cat > "$GEMINI_DIR/settings.json" <<SETTINGS
{
  "model": { "maxSessionTurns": $MAX_TURNS },
  "auth": { "type": "api-key" }
}
SETTINGS

# GEMINI_API_KEY stays in env — Gemini CLI reads it at runtime.
# No need to write credential files.

# 3. Run the batch command
exec "$@"
