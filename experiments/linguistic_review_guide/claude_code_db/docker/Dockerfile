FROM node:20

ARG CLAUDE_CODE_VERSION=latest

# System deps for firewall + batch processing + DB queries (no dev tools — headless runner)
RUN apt-get update && apt-get install -y --no-install-recommends \
    jq bc procps sudo \
    iptables ipset iproute2 dnsutils \
    sqlite3 python3 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Claude Code (pinnable version for reproducible batch runs)
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin
RUN mkdir -p /usr/local/share/npm-global && chown -R node:node /usr/local/share/npm-global
USER node
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# OOM protection — default Node.js heap (~1.5 GB) can crash on large sessions
ENV NODE_OPTIONS=--max-old-space-size=4096

# Workspace layout
USER root
RUN mkdir -p /workspace/prepared /workspace/spec /data /output /home/node/.claude \
    && chown -R node:node /workspace /data /output /home/node/.claude

# Firewall script (runs as root via sudo in entrypoint)
COPY init-firewall.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/init-firewall.sh \
    && echo "node ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" \
       > /etc/sudoers.d/node-firewall \
    && chmod 0440 /etc/sudoers.d/node-firewall

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER node
WORKDIR /workspace

ENTRYPOINT ["entrypoint.sh"]
CMD ["python3", "/workspace/batch_runner.py", "--all"]
