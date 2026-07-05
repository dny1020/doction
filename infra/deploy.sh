#!/usr/bin/env bash
# doction pull-deploy — lo ejecuta el systemd timer en la Pi.
# Pull de ghcr.io; si el digest cambió, recrea el contenedor y verifica /health.
# Si la imagen nueva no pasa el health check, vuelve a la anterior (rollback) y
# avisa por NOTIFY_URL (ntfy/healthchecks; opcional, en /opt/doction/.env).

set -euo pipefail
cd /opt/doction

IMAGE=ghcr.io/dny1020/doction:latest
FAIL_MARKER=/opt/doction/.deploy-failed

# NOTIFY_URL se lee del .env sin hacer `source` (los secretos pueden llevar
# caracteres que romperían el shell).
NOTIFY_URL=$(grep -E '^NOTIFY_URL=' .env 2>/dev/null | cut -d= -f2- || true)

notify() {
  [ -n "$NOTIFY_URL" ] || return 0
  curl -fsS -m 10 -d "doction deploy: $1" "$NOTIFY_URL" > /dev/null 2>&1 || true
}

wait_healthy() {
  for _ in $(seq 1 20); do
    if docker exec doction python3 -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" \
      2>/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

before=$(docker inspect -f '{{.Image}}' doction 2>/dev/null || echo none)
docker compose pull -q
docker compose up -d
after=$(docker inspect -f '{{.Image}}' doction 2>/dev/null || echo none)

[ "$before" = "$after" ] && exit 0

echo "doction image updated: ${before#sha256:} -> ${after#sha256:}"
if wait_healthy; then
  echo "health OK"
  rm -f "$FAIL_MARKER"
  docker image prune -f > /dev/null
  exit 0
fi

echo "health check FAILED after update" >&2

# Rollback: re-etiqueta la imagen anterior como :latest y recrea. El próximo tick
# del timer volverá a intentar la nueva; el marcador evita re-notificar el mismo
# digest roto cada 5 minutos.
if [ "$before" != "none" ]; then
  docker tag "$before" "$IMAGE"
  docker compose up -d
  if wait_healthy; then
    echo "rolled back to previous image ${before#sha256:}"
  else
    echo "rollback did NOT become healthy — manual intervention needed" >&2
    notify "FAILED and rollback unhealthy on $(hostname) — needs manual intervention"
    exit 1
  fi
fi

if ! grep -qs "$after" "$FAIL_MARKER" 2>/dev/null; then
  echo "$after" > "$FAIL_MARKER"
  notify "new image ${after#sha256:} failed health check on $(hostname); rolled back to previous"
fi
exit 1
