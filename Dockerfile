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

# nodejs es para pyright: está escrito en TypeScript y corre sobre node. Sin él se
# bajaría uno por su cuenta a mitad del build.
RUN apt-get update -qq && apt-get install -y --no-install-recommends postgresql nodejs \
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
    && uv run ruff format --check . \
    && uv run pyright app tests \
    && uv run pytest \
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

# OCR local opt-in (OCR_UPLOADS=1): tesseract indexa el texto de las imágenes
# subidas para la búsqueda. Solo en runtime — el stage test no lo necesita.
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

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

# Reranker cross-encoder (ms-marco MiniLM int8, ~23MB): repuntúa el top-20 de sgrep.
# Opt-in en runtime con RERANK=1 (requiere SEMANTIC_SEARCH=1); apagado no carga nada.
ARG RERANK_REPO=Xenova/ms-marco-MiniLM-L-6-v2
ARG RERANK_REV=a09144355adeed5f58c8ed011d209bf8ee5a1fec
ARG RERANK_SHA256=e9d8ebf845c413e981c175bfe49a3bfa9b3dcce2a3ba54875ee5df5a58639fbe
ARG RERANK_TOKENIZER_SHA256=d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66
RUN mkdir -p /app/models/reranker \
    && curl -fsSL -o /app/models/reranker/model_quantized.onnx \
        "https://huggingface.co/${RERANK_REPO}/resolve/${RERANK_REV}/onnx/model_quantized.onnx" \
    && curl -fsSL -o /app/models/reranker/tokenizer.json \
        "https://huggingface.co/${RERANK_REPO}/resolve/${RERANK_REV}/tokenizer.json" \
    && echo "${RERANK_SHA256}  /app/models/reranker/model_quantized.onnx" | sha256sum -c - \
    && echo "${RERANK_TOKENIZER_SHA256}  /app/models/reranker/tokenizer.json" | sha256sum -c -

COPY app ./app
COPY scripts ./scripts
# Bundle de la SPA construido en el stage `web` → servido por FastAPI en /app.
COPY --from=web /build/app/static/app ./app/static/app

# Non-root: uvicorn y los subprocesos de git corren como `doction` (uid 1000, el uid
# típico del primer usuario en la Pi/dev, para que los bind mounts de /data y /logs
# funcionen sin chown extra). Si los datos existentes son de root (deploys antiguos):
#   sudo chown -R 1000:1000 /mnt/ssd/doction/{pages,uploads,logs}   (¡postgres/ no!)
RUN useradd --uid 1000 --create-home doction \
    && mkdir -p /data /logs \
    && chown -R doction:doction /data /logs
USER doction

EXPOSE 8000

CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
