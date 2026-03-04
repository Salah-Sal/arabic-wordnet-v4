FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    curl git python3 python3-pip jq ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code@latest

# Create non-root user (required for --dangerously-skip-permissions)
RUN useradd -m -s /bin/bash claude
RUN mkdir -p /workspace /data/input /data/output /data/ref \
    && chown -R claude:claude /workspace /data

WORKDIR /workspace

COPY entrypoint.sh /entrypoint.sh
COPY validate_batch.py /validate_batch.py
COPY prompt_template.txt /workspace/prompt.txt
RUN chmod +x /entrypoint.sh && chown claude:claude /workspace/prompt.txt

USER claude
ENTRYPOINT ["/entrypoint.sh"]
