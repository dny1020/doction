# Shortcuts for this repository's workflow. Every target is a command already documented
# elsewhere; the Makefile invents none.
.PHONY: setup dev frontend build-web test test-clean lint format format-check \
        typecheck spec license changelog docs-reachable docs docs-serve check eval image image-test \
        up down logs restart \
        graph clean

# ── Setup ────────────────────────────────────────────────────────────────────
setup:
	uv sync --dev
	cd frontend && npm ci
	$(MAKE) build-web

# ── Development ──────────────────────────────────────────────────────────────
dev:
	uv run uvicorn app.main:app --reload

frontend:
	cd frontend && npm run dev

# The bundle is built into app/static/app/, which is gitignored. Without this, a change
# under frontend/ does not reach the app uvicorn serves: the stylesheet is linked with a
# content hash that only changes on build.
build-web:
	cd frontend && npm run build

# ── Quality gate ─────────────────────────────────────────────────────────────
# The same order as CI, so they cannot diverge.
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

# The tests start their own ephemeral Postgres; this removes it if one is left behind.
test-clean:
	-docker rm -f doction-test-pg

# openspec/ is maintainer-local and not versioned, so a clone skips this step.
spec:
	@if [ -d openspec ]; then openspec validate --all --strict && openspec list; \
	else echo "spec: SKIPPED — openspec/ is not in this checkout"; fi

# The licence is declared in seven places, one of them outside the tree. This compares
# them against pyproject.toml, the only hand-written source.
license:
	uv run python -m scripts.check_license

# Release notes come from the CHANGELOG, so a version without an entry is a release nobody
# can read. Checked here rather than at tag time, when it would already be too late.
changelog:
	uv run python -m scripts.changelog --check

# Orientation that does not travel in the clone orients nobody: CLAUDE.md and .claude/ are
# gitignored, so a tracked document citing them dead-ends for everyone but the maintainer.
docs-reachable:
	uv run python -m scripts.check_docs_reachable

# The published site builds strictly: an internal link that does not resolve is a failure,
# not a log warning. Covers what docs-reachable cannot see, the navigation once the
# documentation is a site.
docs:
	uv run --group docs python -m scripts.build_docs

docs-serve:
	uv run --group docs python -m scripts.build_docs --serve

check:
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) typecheck
	$(MAKE) test
	cd frontend && npm run check
	$(MAKE) license
	$(MAKE) changelog
	$(MAKE) docs-reachable
	$(MAKE) docs
	$(MAKE) spec

# ── Retrieval ────────────────────────────────────────────────────────────────
# Outside pytest on purpose: a quality number that can fail a build is a build that gets
# ignored. SWEEP=1 to sweep.
eval:
	@test -n "$(EVAL_CORPUS)" || (echo "EVAL_CORPUS is required"; exit 1)
	EVAL_CORPUS="$(EVAL_CORPUS)" uv run python -m evals.retrieval $(if $(SWEEP),--sweep,)

# ── Image and compose ────────────────────────────────────────────────────────
# The version comes from pyproject.toml, where it is bumped on every release.
VERSION := $(shell grep -m1 '^version' pyproject.toml | cut -d'"' -f2)

image:
	docker build -t ghcr.io/dny1020/doction:$(VERSION) -t ghcr.io/dny1020/doction:latest .

# What CI runs: this stage starts its own Postgres and passes the gate.
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

# ── Utilities ────────────────────────────────────────────────────────────────
graph:
	graphify update .

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) \
		-prune -exec rm -rf {} +
	rm -rf app/static/app
