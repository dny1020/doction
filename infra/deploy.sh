#!/usr/bin/env bash
# doction pull-deploy — lo ejecuta el systemd timer en la Pi.
# Pull de ghcr.io; si el digest cambió, recrea el contenedor y verifica /health.

set -euo pipefail
cd /opt/doction

before=$(docker inspect -f '{{.Image}}' doction 2>/dev/null || echo none)
docker compose pull -q
docker compose up -d
after=$(docker inspect -f '{{.Image}}' doction 2>/dev/null || echo none)

[ "$before" = "$after" ] && exit 0

echo "doction image updated: ${before#sha256:} -> ${after#sha256:}"
for _ in $(seq 1 20); do
  if docker exec doction python3 -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" \
    2>/dev/null; then
    echo "health OK"
    docker image prune -f > /dev/null
    exit 0
  fi
  sleep 2
done
echo "health check FAILED after update" >&2
exit 1
