FROM python:3.13-slim AS base

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

# CI gate: `docker build --target test` runs lint + suite; never shipped. Postgres
# runs embedded in this stage (initdb + start, discarded when the layer finishes)
# so the gate stays a single self-contained `docker build`, no sidecar containers.
FROM base AS test

RUN apt-get update -qq && apt-get install -y --no-install-recommends postgresql \
    && rm -rf /var/lib/apt/lists/*

RUN uv sync --frozen

COPY app ./app
COPY tests ./tests
COPY scripts ./scripts

ENV DATABASE_URL=postgresql://doction:doction@localhost:5432/doction \
    TEST_DATABASE_URL=postgresql://doction:doction@localhost:5432/postgres

RUN service postgresql start \
    && su postgres -c "createuser --createdb doction" \
    && su postgres -c "psql -c \"ALTER USER doction PASSWORD 'doction';\"" \
    && su postgres -c "createdb -O doction doction" \
    && uv run ruff check . \
    && uv run python -m pytest tests -q \
    && service postgresql stop

# Frontend React (Vite): construye la SPA. Node entra SOLO en este stage de build;
# el runtime sigue siendo una imagen de solo Python. El bundle sale en
# /build/app/static/app (por el outDir de vite.config.js: ../app/static/app).
FROM node:20-slim AS web

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM base AS runtime

RUN uv sync --frozen --no-dev && uv cache clean

# Modelo de embeddings (MiniLM int8, ~22MB) horneado en la imagen → semántica
# offline, sin servicios externos. Opt-in en runtime con SEMANTIC_SEARCH=1; si está
# apagado el modelo ni se carga (0 RAM extra). Revisión + sha256 fijadas (reproducible).
ARG MODEL_REPO=Xenova/all-MiniLM-L6-v2
ARG MODEL_REV=751bff37182d3f1213fa05d7196b954e230abad9
ARG MODEL_SHA256=afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1
ARG TOKENIZER_SHA256=da0e79933b9ed51798a3ae27893d3c5fa4a201126cef75586296df9b4d2c62a0
RUN mkdir -p /app/models \
    && curl -fsSL -o /app/models/model_quantized.onnx \
        "https://huggingface.co/${MODEL_REPO}/resolve/${MODEL_REV}/onnx/model_quantized.onnx" \
    && curl -fsSL -o /app/models/tokenizer.json \
        "https://huggingface.co/${MODEL_REPO}/resolve/${MODEL_REV}/tokenizer.json" \
    && echo "${MODEL_SHA256}  /app/models/model_quantized.onnx" | sha256sum -c - \
    && echo "${TOKENIZER_SHA256}  /app/models/tokenizer.json" | sha256sum -c -

COPY app ./app
COPY scripts ./scripts
# Bundle de la SPA construido en el stage `web` → servido por FastAPI en /app.
COPY --from=web /build/app/static/app ./app/static/app
RUN mkdir -p /data /logs

EXPOSE 8000

CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
