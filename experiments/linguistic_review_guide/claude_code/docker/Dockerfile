FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

# System deps (no Python needed — Claude Code is the only runtime)
RUN apt-get update && apt-get install -y \
    curl git jq bc ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Node.js 20 (Claude Code runtime)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*

# Claude Code
RUN npm install -g @anthropic-ai/claude-code

# Non-root user
RUN useradd -m -s /bin/bash reviewer
RUN mkdir -p /workspace/prepared /workspace/spec /output /home/reviewer/.claude \
    && chown -R reviewer:reviewer /workspace /output /home/reviewer/.claude

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER reviewer
WORKDIR /workspace

ENTRYPOINT ["entrypoint.sh"]
CMD ["bash", "/workspace/run_review.sh", "--all"]
