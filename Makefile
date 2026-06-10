.PHONY: test lint test-image

IMAGE := doction-test-$(shell git rev-parse --short HEAD 2>/dev/null || echo local)

test:
	uv run python -m pytest tests/test.py tests/test_git.py -q

lint:
	uv run ruff check .

test-image:
	docker build -t $(IMAGE) .
	@name=$(IMAGE)-smoke-$$$$; \
	docker run -d --name $$name \
	  -e DATABASE_PATH=/tmp/doction-test.db \
	  -e SECRET_KEY=test-secret \
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
