# OpenCode Arena - Main Application Dockerfile
# Builds the API server and agent framework

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY opencode/ ./opencode/
COPY tasks/ ./tasks/
COPY scripts/ ./scripts/
COPY config/ ./config/

# Create data directory
RUN mkdir -p /data/workspace /data/results /data/logs

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the API server
CMD ["python", "-m", "opencode.api.server"]
