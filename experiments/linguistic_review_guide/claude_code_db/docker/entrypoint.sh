#!/bin/bash
# Container entrypoint: firewall → credentials → exec
# Runs as 'node' user (firewall via sudo, creds in user home).

# 1. Initialize egress firewall (default-deny whitelist)
echo "Initializing firewall..."
if sudo /usr/local/bin/init-firewall.sh; then
    echo "Firewall active."
else
    echo "WARNING: Firewall setup failed. Continuing without network restrictions."
fi
echo ""

# 2. Credential handling: env var → file → clear env → exec
CREDS_DIR="/home/node/.claude"
mkdir -p "$CREDS_DIR"

if [ -n "${CLAUDE_CREDS_JSON:-}" ]; then
    printf '%s' "$CLAUDE_CREDS_JSON" > "$CREDS_DIR/.credentials.json"
    chmod 600 "$CREDS_DIR/.credentials.json"
fi

# Clear secrets before exec — prevents leaking to child processes
unset CLAUDE_CREDS_JSON
unset ANTHROPIC_API_KEY

# 3. Run the batch command
exec "$@"
