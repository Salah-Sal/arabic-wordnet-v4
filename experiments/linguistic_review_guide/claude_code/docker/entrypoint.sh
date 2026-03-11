#!/bin/bash
# Credential handling: env var → file → clear env → exec
# Pattern from the Masader dataset assessment project.

CREDS_DIR="/home/reviewer/.claude"
mkdir -p "$CREDS_DIR"

if [ -n "$CLAUDE_CREDS_JSON" ]; then
    printf '%s' "$CLAUDE_CREDS_JSON" > "$CREDS_DIR/.credentials.json"
    chmod 600 "$CREDS_DIR/.credentials.json"
fi

# Clear secrets before exec — prevents leaking to child processes
unset CLAUDE_CREDS_JSON
unset ANTHROPIC_API_KEY

exec "$@"
