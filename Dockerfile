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
    # --superuser para igualar al Postgres efimero que usa tests/conftest.py en
    # local (POSTGRES_USER siempre es superusuario en la imagen oficial). Sin
    # esto el mismo rol tiene privilegios distintos aqui y en local, y el
    # DROP DATABASE ... WITH (FORCE) del teardown falla solo en CI.
    && su postgres -c "createuser --createdb --superuser doction" \
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
# Node 22 LTS, no 20: jsdom y undici (que entran por vitest) declaran `engines`
# node >=22.19.0, así que en node:20 el gate falla al cargar el entorno de pruebas
# —y solo ahí, porque en local se corre sobre otra versión. Al subir la imagen base,
# comprobar contra los `engines` del lockfile, no contra lo que haya en la máquina.
FROM node:25-slim AS web

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# El CSS del design system lo sirve el backend, pero el chequeo de assets locales
# —la última parte de `npm run check`— tiene que leerlo: es donde viven las @font-face
# y por tanto donde aparecería una fuente pedida a un CDN. Sin esta copia el chequeo
# no encontraba el fichero y la etapa fallaba solo aquí, no en local.
COPY app/static/style.css /build/app/static/style.css
# `check` = eslint + prettier --check + vitest + build + assets: el mismo gate que se
# corre en local, así que el bundle solo se genera si el front pasa lint, formato,
# pruebas y air-gap.
RUN npm run check

FROM base AS runtime

# uv construye el venv y después no hace falta: la aplicación arranca
# `.venv/bin/uvicorn`, no pip ni uv. Quitarlos de la imagen quita con ellos setuptools y
# msgpack, que no están instalados como paquetes sino vendorizados dentro de pip
# (pip/_vendor/pkg_resources 70.3.0 y pip/_vendor/msgpack) y aportaban tres hallazgos de
# Trivy. Un componente que no se envía no vuelve a aparecer en un escaneo; un descarte hay
# que rejustificarlo cada vez.
RUN uv sync --frozen --no-dev && uv cache clean \
    && pip uninstall -y uv pip 2>/dev/null || true

# OCR local opt-in (OCR_UPLOADS=1): tesseract indexa el texto de las imágenes
# subidas para la búsqueda. Solo en runtime — el stage test no lo necesita.
#
# En la misma capa se aplican las actualizaciones de seguridad de Debian. Trivy reportaba
# 13 hallazgos —libpcre2-8-0, libsqlite3-0, gzip, libc6, libc-bin— y todos tenían ya
# publicado el arreglo dentro de la misma release de Debian, así que no eran descartables:
# existía la versión corregida y esta imagen enviaba la anterior. Va aquí y no en `base`
# para que el stage `test` no pague la descarga en cada build.
RUN apt-get update -qq \
    && apt-get -y --no-install-recommends upgrade \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

# Modelo de embeddings (MiniLM int8, ~22MB) horneado en la imagen → semántica
# offline, sin servicios externos. Opt-in en runtime con SEMANTIC_SEARCH=1; si está
# apagado el modelo ni se carga (0 RAM extra). Revisión + sha256 fijadas (reproducible).
#
# --retry porque el publish de 0.31.4 murió con un 429 de Hugging Face. El contenido va
# pineado por revisión y verificado por sha256, así que aquello era disponibilidad y no
# integridad: una release detenida por un límite momentáneo es una release detenida por
# nada. El build multiarquitectura pide cada modelo una vez por arquitectura, lo que dobla
# las peticiones y hace más probable el límite. Sin --retry-all-errors a propósito: un 404
# o una revisión renombrada tienen que fallar ya, no tras cinco esperas.
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

# Reranker cross-encoder (ms-marco MiniLM int8, ~23MB): repuntúa el top-20 de sgrep.
# Opt-in en runtime con RERANK=1 (requiere SEMANTIC_SEARCH=1); apagado no carga nada.
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
