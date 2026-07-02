.PHONY: test lint test-image backup

IMAGE := doction-test-$(shell git rev-parse --short HEAD 2>/dev/null || echo local)

test:
	uv run python -m pytest tests -q

lint:
	uv run ruff check .

# Snapshot local de los datos (dump de Postgres + pages/ + uploads/) en ./backups.
# Requiere `docker compose up` corriendo (dump vía `docker exec` al contenedor postgres).
# En la Pi lo corre el systemd timer doction-backup.timer apuntando a /mnt/ssd/doction.
backup:
	DOCTION_DATA=$(PWD)/data DOCTION_BACKUP_DIR=$(PWD)/backups bash infra/backup.sh

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
