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
GEMINI_DIR="/home/node/.gemini"
mkdir -p "$GEMINI_DIR"

MAX_TURNS="${MAX_TURNS:-80}"

if [ -n "${GEMINI_API_KEY:-}" ]; then
    # API key mode — Gemini CLI reads GEMINI_API_KEY from env directly.
    cat > "$GEMINI_DIR/settings.json" <<SETTINGS
{
  "model": { "maxSessionTurns": $MAX_TURNS },
  "auth": { "type": "api-key" }
}
SETTINGS
    echo "Auth: API key"
else
    # OAuth mode — credentials mounted from host ~/.gemini/
    cat > "$GEMINI_DIR/settings.json" <<SETTINGS
{
  "model": { "maxSessionTurns": $MAX_TURNS },
  "security": { "auth": { "selectedType": "oauth-personal" } }
}
SETTINGS
    echo "Auth: OAuth (mounted credentials)"
fi

# 3. Run the batch command
exec "$@"
