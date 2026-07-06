.PHONY: test lint test-image backup check format bump-patch bump-minor bump-major

IMAGE := doction-test-$(shell git rev-parse --short HEAD 2>/dev/null || echo local)

test:
	uv run python -m pytest tests -q

lint:
	uv run ruff check .
	uv run mypy app

# Snapshot local de los datos (dump de Postgres + pages/ + uploads/) en ./backups.
# Requiere `docker compose up` corriendo (dump vía `docker exec` al contenedor postgres).
# En la Pi lo corre el systemd timer doction-backup.timer apuntando a /mnt/ssd/doction.
backup:
	DOCTION_DATA=$(PWD)/data DOCTION_BACKUP_DIR=$(PWD)/backups bash infra/backup.sh

check:
	uv run ruff check .
	uv run black --check .
	uv run mypy app
	uv run pytest

format:
	uv run ruff check --fix .
	uv run black .


test-image:
	docker build -t $(IMAGE) .
	@net=$(IMAGE)-net-$$$$; pg=$(IMAGE)-pg-smoke-$$$$; name=$(IMAGE)-smoke-$$$$; \
	docker network create $$net > /dev/null; \
	docker run -d --name $$pg --network $$net \
	  -e POSTGRES_USER=doction -e POSTGRES_PASSWORD=test -e POSTGRES_DB=doction \
	  postgres:16-alpine > /dev/null; \
	echo "Waiting for postgres..."; \
	for i in $$(seq 1 30); do \
	  docker exec $$pg pg_isready -U doction > /dev/null 2>&1 && break; \
	  sleep 1; \
	done; \
	docker run -d --name $$name --network $$net \
	  -e DATABASE_URL=postgresql://doction:test@$$pg:5432/doction \
	  -e SECRET_KEY=test-secret \
	  -p 18000:8000 \
	  $(IMAGE); \
	echo "Waiting for app..."; \
	ok=0; for i in $$(seq 1 30); do \
	  if curl -sf http://localhost:18000/health > /dev/null 2>&1; then ok=1; break; fi; \
	  sleep 1; \
	done; \
	docker stop $$name $$pg > /dev/null; \
	docker rm $$name $$pg > /dev/null; \
	docker network rm $$net > /dev/null; \
	if [ $$ok -eq 1 ]; then \
	  docker rmi $(IMAGE) > /dev/null; \
	  echo "smoke test passed — image removed"; \
	else \
	  echo "smoke test FAILED — image $(IMAGE) kept for inspection"; \
	  exit 1; \
	fi

# Sube la versión (única fuente: pyproject.toml — app/version.py y el MCP la leen
# de ahí en runtime), commitea y etiqueta. uv.lock también registra la versión del
# proyecto, así que se re-lockea y entra en el mismo commit.
bump-patch bump-minor bump-major:
	@git diff --quiet && git diff --cached --quiet \
		|| { echo 'working tree not clean — commit or stash first'; exit 1; }
	@part=$(subst bump-,,$@); \
	v=$$(python3 -c "import re,sys;c=open('pyproject.toml').read();ma,mi,pa=map(int,re.search(r'version = \"(\d+)\.(\d+)\.(\d+)\"',c).groups());print({'major':f'{ma+1}.0.0','minor':f'{ma}.{mi+1}.0','patch':f'{ma}.{mi}.{pa+1}'}[sys.argv[1]])" $$part); \
	sed -i "s/^version = \".*\"/version = \"$$v\"/" pyproject.toml; \
	uv lock -q; \
	git add pyproject.toml uv.lock && git commit -m "bump: v$$v" && git tag "v$$v"; \
	echo "v$$v — recuerda: git push && git push --tags"

