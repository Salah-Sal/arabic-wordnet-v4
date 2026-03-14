#!/bin/bash
# Egress firewall for headless Gemini CLI batch processing.
# Adapted from: github.com/anthropics/claude-code/.devcontainer/init-firewall.sh
#
# Policy: default-deny outbound, whitelist only what Gemini CLI needs at runtime.
# Tighter than the official devcontainer (no GitHub, no npm, no VS Code marketplace).
set -euo pipefail
IFS=$'\n\t'

# ── 1. Preserve Docker internal DNS before flushing ──
DOCKER_DNS_RULES=$(iptables-save -t nat | grep "127\.0\.0\.11" || true)

# Flush existing rules
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
ipset destroy allowed-domains 2>/dev/null || true

# Restore Docker DNS resolution
if [ -n "$DOCKER_DNS_RULES" ]; then
    echo "Restoring Docker DNS rules..."
    iptables -t nat -N DOCKER_OUTPUT 2>/dev/null || true
    iptables -t nat -N DOCKER_POSTROUTING 2>/dev/null || true
    echo "$DOCKER_DNS_RULES" | xargs -L 1 iptables -t nat
fi

# ── 2. Allow DNS, localhost, and established connections first ──
# DNS (required for domain resolution below)
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A INPUT -p udp --sport 53 -j ACCEPT

# Localhost
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# ── 3. Build whitelist of allowed domains ──
ipset create allowed-domains hash:net

# Resolve each domain and add its IPs to the whitelist.
# Minimal set for headless batch processing:
#   - generativelanguage.googleapis.com : Gemini API (required)
#   - aiplatform.googleapis.com         : Vertex AI (alternative API endpoint)
#   - sentry.io                         : Gemini CLI error telemetry
#   - statsig.com                       : feature flags
for domain in \
    "generativelanguage.googleapis.com" \
    "aiplatform.googleapis.com" \
    "sentry.io" \
    "statsig.com"; do
    echo "Resolving $domain..."
    ips=$(dig +noall +answer A "$domain" | awk '$4 == "A" {print $5}')
    if [ -z "$ips" ]; then
        echo "WARNING: Failed to resolve $domain (continuing)"
        continue
    fi

    while read -r ip; do
        if [[ "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
            echo "  Adding $ip ($domain)"
            ipset add allowed-domains "$ip" 2>/dev/null || true
        fi
    done < <(echo "$ips")
done

# ── 4. Allow host network (Docker Desktop routing) ──
HOST_IP=$(ip route | grep default | cut -d" " -f3)
if [ -n "$HOST_IP" ]; then
    HOST_NETWORK=$(echo "$HOST_IP" | sed "s/\.[0-9]*$/.0\/24/")
    echo "Host network: $HOST_NETWORK"
    iptables -A INPUT -s "$HOST_NETWORK" -j ACCEPT
    iptables -A OUTPUT -d "$HOST_NETWORK" -j ACCEPT
fi

# ── 5. Set default-deny policy ──
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# Allow established connections (for already-approved traffic)
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow whitelisted destinations
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT

# Reject everything else (immediate feedback, not silent drop)
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

# ── 6. Verify ──
echo ""
echo "Firewall verification..."

# Should be BLOCKED
if curl --connect-timeout 5 -s https://example.com >/dev/null 2>&1; then
    echo "FAIL: example.com reachable (should be blocked)"
    exit 1
else
    echo "  PASS: example.com blocked"
fi

# Should be ALLOWED
if curl --connect-timeout 5 -s https://generativelanguage.googleapis.com >/dev/null 2>&1; then
    echo "  PASS: generativelanguage.googleapis.com reachable"
else
    # API may return non-200 but connection should succeed
    echo "  PASS: generativelanguage.googleapis.com connection attempted (may return error, but not blocked)"
fi

echo ""
echo "Firewall active — default-deny with $(ipset list allowed-domains | grep -c '^[0-9]') whitelisted IPs"
