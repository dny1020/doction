# Atajos del flujo de este repositorio. Cada objetivo es el comando que ya está
# documentado en CLAUDE.md; el Makefile no inventa ninguno.
.PHONY: setup dev frontend build-web test test-clean lint format format-check \
        typecheck spec license changelog check eval image image-test up down logs restart \
        graph clean

# ── Puesta a punto ───────────────────────────────────────────────────────────
setup:
	uv sync --dev
	cd frontend && npm ci
	$(MAKE) build-web

# ── Desarrollo ───────────────────────────────────────────────────────────────
dev:
	uv run uvicorn app.main:app --reload

frontend:
	cd frontend && npm run dev

# El bundle se construye dentro de app/static/app/, que está en .gitignore. Sin
# esto, un cambio bajo frontend/ NO se ve en la aplicación servida por uvicorn:
# la hoja de estilos se enlaza con un hash de contenido que solo cambia al
# construir, así que el navegador sigue con la anterior.
build-web:
	cd frontend && npm run build

# ── Puerta de calidad ────────────────────────────────────────────────────────
# El mismo orden que AGENTS.md y que la CI, para que no diverjan.
lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

typecheck:
	uv run pyright app tests

test:
	uv run pytest

# Los tests levantan su propio Postgres efímero; esto lo retira si queda vivo.
test-clean:
	-docker rm -f doction-test-pg

spec:
	openspec validate --all --strict
	openspec list

# La licencia se declara en siete sitios y uno vive fuera del árbol. Esto los compara
# contra pyproject.toml, que es la única fuente escrita a mano.
license:
	uv run python -m scripts.check_license

# Las notas de una release salen del CHANGELOG, así que una versión sin entrada es una
# release que nadie puede leer. Se comprueba aquí, contra la versión declarada, y no al
# crear el tag: entonces ya sería tarde, el tag existiría y borrarlo está prohibido.
changelog:
	uv run python -m scripts.changelog --check

check:
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) typecheck
	$(MAKE) test
	cd frontend && npm run check
	$(MAKE) license
	$(MAKE) changelog
	$(MAKE) spec

# ── Recuperación ─────────────────────────────────────────────────────────────
# Fuera de pytest a propósito: un número de calidad que puede tumbar una
# construcción es una construcción que se acaba ignorando. SWEEP=1 para barrer.
eval:
	@test -n "$(EVAL_CORPUS)" || (echo "EVAL_CORPUS es obligatorio"; exit 1)
	EVAL_CORPUS="$(EVAL_CORPUS)" uv run python -m evals.retrieval $(if $(SWEEP),--sweep,)

# ── Imagen y compose ─────────────────────────────────────────────────────────
# La versión sale de pyproject.toml, que es donde se sube en cada publicación.
VERSION := $(shell grep -m1 '^version' pyproject.toml | cut -d'"' -f2)

image:
	docker build -t ghcr.io/dny1020/doction:$(VERSION) -t ghcr.io/dny1020/doction:latest .

# Lo mismo que corre la CI: esta etapa levanta su Postgres y pasa la puerta.
image-test:
	docker build --target test .

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f doction

restart:
	docker compose restart doction

# ── Utilidades ───────────────────────────────────────────────────────────────
graph:
	graphify update .

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) \
		-prune -exec rm -rf {} +
	rm -rf app/static/app
