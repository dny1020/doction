FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DATABASE_URL=postgresql://doction:doction@postgres:5432/doction \
    DATA_DIR=/data \
    LOG_DIR=/logs \
    LOG_LEVEL=INFO \
    GIT_AUTHOR_NAME="doction" \
    GIT_AUTHOR_EMAIL="doction@localhost" \
    GIT_COMMITTER_NAME="doction" \
    GIT_COMMITTER_EMAIL="doction@localhost"

WORKDIR /app

RUN pip install --no-cache-dir uv

RUN apt-get update -qq && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

# CI gate: `docker build --target test` runs lint and the suite against an embedded
# Postgres, so the gate is one self-contained build. Never shipped.
FROM base AS test

# nodejs is for pyright, which runs on node; without it one is downloaded mid-build.
RUN apt-get update -qq && apt-get install -y --no-install-recommends postgresql nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN uv sync --frozen

COPY app ./app
COPY tests ./tests
COPY scripts ./scripts

ENV DATABASE_URL=postgresql://doction:doction@localhost:5432/doction \
    TEST_DATABASE_URL=postgresql://doction:doction@localhost:5432/postgres

RUN service postgresql start \
    # --superuser, as in tests/conftest.py: DROP DATABASE ... WITH (FORCE) needs it.
    && su postgres -c "createuser --createdb --superuser doction" \
    && su postgres -c "psql -c \"ALTER USER doction PASSWORD 'doction';\"" \
    && su postgres -c "createdb -O doction doction" \
    && uv run ruff check . \
    && uv run ruff format --check . \
    && uv run pyright app tests \
    && uv run pytest \
    && service postgresql stop

# Builds the SPA once on the build host (it is the same on every arch; under QEMU it took
# minutes). Node 22: jsdom and undici require node >=22.19.
FROM --platform=$BUILDPLATFORM node:22-slim AS web

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# The local-asset check reads the backend's stylesheet, where the @font-face rules live.
COPY app/static/style.css /build/app/static/style.css
# Hashed into index.html's URLs by vite.config.js, so a changed icon reaches the browser.
COPY app/static/favicon.svg app/static/manifest.webmanifest app/static/apple-touch-icon.png \
     /build/app/static/
# The same gate as locally: no bundle unless lint, format, tests and the asset check pass.
RUN npm run check

FROM base AS runtime

# The app starts .venv/bin/uvicorn, so uv and pip go; that also drops pip's vendored
# packages from Trivy's findings.
RUN uv sync --frozen --no-dev && uv cache clean \
    && pip uninstall -y uv pip 2>/dev/null || true

# CI passes the ISO week, so the apt upgrade below reruns weekly despite the build cache.
ARG APT_REFRESH=

# Opt-in OCR (OCR_UPLOADS=1) plus Debian security updates. Here, not in `base`, so the
# `test` stage does not pay for it.
RUN apt-get update -qq \
    && apt-get -y --no-install-recommends upgrade \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

# The embedding model, baked in so semantic search works offline; pinned by revision and
# sha256. --retry for transient 429s, but not --retry-all-errors: a 404 must fail now.
ARG MODEL_REPO=Xenova/all-MiniLM-L6-v2
ARG MODEL_REV=751bff37182d3f1213fa05d7196b954e230abad9
ARG MODEL_SHA256=afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1
ARG TOKENIZER_SHA256=da0e79933b9ed51798a3ae27893d3c5fa4a201126cef75586296df9b4d2c62a0
RUN mkdir -p /app/models \
    && curl -fsSL --retry 5 --retry-delay 5 -o /app/models/model_quantized.onnx \
        "https://huggingface.co/${MODEL_REPO}/resolve/${MODEL_REV}/onnx/model_quantized.onnx" \
    && curl -fsSL --retry 5 --retry-delay 5 -o /app/models/tokenizer.json \
        "https://huggingface.co/${MODEL_REPO}/resolve/${MODEL_REV}/tokenizer.json" \
    && echo "${MODEL_SHA256}  /app/models/model_quantized.onnx" | sha256sum -c - \
    && echo "${TOKENIZER_SHA256}  /app/models/tokenizer.json" | sha256sum -c -

# The cross-encoder reranker, opt-in with RERANK=1 (needs SEMANTIC_SEARCH=1).
ARG RERANK_REPO=Xenova/ms-marco-MiniLM-L-6-v2
ARG RERANK_REV=a09144355adeed5f58c8ed011d209bf8ee5a1fec
ARG RERANK_SHA256=e9d8ebf845c413e981c175bfe49a3bfa9b3dcce2a3ba54875ee5df5a58639fbe
ARG RERANK_TOKENIZER_SHA256=d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66
RUN mkdir -p /app/models/reranker \
    && curl -fsSL --retry 5 --retry-delay 5 -o /app/models/reranker/model_quantized.onnx \
        "https://huggingface.co/${RERANK_REPO}/resolve/${RERANK_REV}/onnx/model_quantized.onnx" \
    && curl -fsSL --retry 5 --retry-delay 5 -o /app/models/reranker/tokenizer.json \
        "https://huggingface.co/${RERANK_REPO}/resolve/${RERANK_REV}/tokenizer.json" \
    && echo "${RERANK_SHA256}  /app/models/reranker/model_quantized.onnx" | sha256sum -c - \
    && echo "${RERANK_TOKENIZER_SHA256}  /app/models/reranker/tokenizer.json" | sha256sum -c -

COPY app ./app
COPY scripts ./scripts
# The SPA bundle from the `web` stage, served by FastAPI at /app.
COPY --from=web /build/app/static/app ./app/static/app

# Non-root, uid 1000 (the Pi's first user), so bind mounts need no chown. For root-owned data:
#   sudo chown -R 1000:1000 /mnt/ssd/doction/{pages,uploads,logs}   (not postgres/!)
RUN useradd --uid 1000 --create-home doction \
    && mkdir -p /data /logs \
    && chown -R doction:doction /data /logs
USER doction

EXPOSE 8000

CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
