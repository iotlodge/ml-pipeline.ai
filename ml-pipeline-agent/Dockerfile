# Production Dockerfile — Python 3.12 + uv
FROM python:3.12-slim AS base

# System deps for numpy/sklearn/xgboost + Node.js for mermaid-cli
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libopenblas-dev libgomp1 \
    nodejs npm \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Install mermaid-cli for graph PNG rendering
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
RUN npm install -g @mermaid-js/mermaid-cli 2>/dev/null || true

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# ── Dependencies (cached layer) ──────────────────────────────────────────────
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-editable 2>/dev/null || uv sync --no-dev --no-editable

# ── Application ──────────────────────────────────────────────────────────────
COPY src ./src

# ── Runtime ──────────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create dirs for artifacts and checkpoints
RUN mkdir -p /tmp/ml-pipeline/artifacts /tmp/ml-pipeline/checkpoints /tmp/ml-pipeline/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
