# The API image. Build from backend/:  docker build -t cms-api .
# Configuration comes from real environment variables (no .env is copied in).

# --- Build stage: install the runtime dependencies and the app into /app/.venv ---
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.9.8 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependencies first, so a code change does not reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# The BM25 model, downloaded now so the container does not need the network to start.
ENV FASTEMBED_CACHE_PATH=/app/models
RUN /app/.venv/bin/python -c "from fastembed import SparseTextEmbedding; SparseTextEmbedding('Qdrant/bm25')"

# --- Runtime stage: only the virtualenv, the model and the seed corpus ---
FROM python:3.13-slim
RUN useradd --create-home cms
WORKDIR /app

COPY --from=build --chown=cms /app/.venv /app/.venv
COPY --from=build --chown=cms /app/models /app/models
COPY --chown=cms data/seed /app/data/seed

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/app/models \
    SEED_DATA_DIR=/app/data/seed \
    # Each worker writes its metric counts here and /metrics adds them up.
    PROMETHEUS_MULTIPROC_DIR=/tmp/cms-metrics \
    # Worker processes; uvicorn reads this itself. Each one loads its own spaCy model.
    WEB_CONCURRENCY=1

USER cms
# The guards ask NLTK for its `punkt` data on every start; fetched now, so a start needs no network.
RUN python -c "import nltk; nltk.download('punkt')"
EXPOSE 8000

# Long start period: the spaCy and BM25 models load before the port opens.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live', timeout=3)"

# The metrics folder is emptied first, or the last run's counts would be added in.
CMD ["sh", "-c", "rm -rf \"$PROMETHEUS_MULTIPROC_DIR\" && mkdir -p \"$PROMETHEUS_MULTIPROC_DIR\" && exec uvicorn cms.main:app --host 0.0.0.0 --port 8000"]
