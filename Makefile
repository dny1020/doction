.PHONY: test test-image lint deploy

VERSION := $(shell python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo local)

IMAGE := doction-test-$(GIT_SHA)

test:
	uv run python -m pytest tests/test.py tests/test_git.py -q

lint:
	uv run ruff check .

deploy:
	DOCKER_HOST=ssh://rpi docker build \
		--label "git.sha=$(GIT_SHA)" \
		-t doction:latest .
	ssh rpi 'cd /opt/doction && docker compose up -d --force-recreate'
	@ssh rpi 'for i in $$(seq 1 30); do docker exec doction python3 -c "import urllib.request; urllib.request.urlopen(\"http://localhost:8000/health\")" >/dev/null 2>&1 && echo "doction is up" && exit 0; sleep 1; done; exit 1'

test-image:
	docker build -t $(IMAGE) .
	@name=$(IMAGE)-smoke-$$$$; \
	docker run -d --name $$name \
	  -e DATABASE_PATH=/tmp/doction-test.db \
	  -e SECRET_KEY=test-secret \
	  -e HF_HUB_OFFLINE=1 \
	  -p 18000:8000 \
	  $(IMAGE); \
	echo "Waiting for app..."; \
	ok=0; for i in $$(seq 1 30); do \
	  if curl -sf http://localhost:18000/health > /dev/null 2>&1; then ok=1; break; fi; \
	  sleep 1; \
	done; \
	docker stop $$name > /dev/null; \
	docker rm $$name > /dev/null; \
	if [ $$ok -eq 1 ]; then \
	  docker rmi $(IMAGE) > /dev/null; \
	  echo "smoke test passed — image removed"; \
	else \
	  echo "smoke test FAILED — image $(IMAGE) kept for inspection"; \
	  exit 1; \
	fi
