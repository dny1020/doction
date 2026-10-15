---
source_sha256: c6956cd141b22cc280b8de3a34d77f3d34e40893d90bda061805d6eb2433eec6
---
# Instalación

doction son dos contenedores: la aplicación y un Postgres con el que habla. No hay un tercer
servicio, ni broker, ni API externa. La imagen publicada es multiarquitectura, así que la misma
etiqueta funciona en hardware amd64 y arm64, desde una VM en la nube hasta una placa pequeña
autoalojada.

## Requisitos

| | Mínimo | Holgado |
| --- | --- | --- |
| Arquitectura | amd64 o arm64 | — |
| RAM para el contenedor de la aplicación | 256 MB | 768 MB |
| RAM adicional, con `SEMANTIC_SEARCH=1` | +150 MB | — |
| RAM adicional, con `RERANK=1` | +100 MB | — |
| Disco | el repositorio git de tus páginas, más los archivos subidos, más el volumen de Postgres | — |
| Postgres | 16 | 16 |

doction funciona con holgura en hardware autoalojado modesto: por ejemplo, una Raspberry Pi 4 con
2 GB lo ejecuta con la búsqueda semántica activada. El despliegue de referencia limita el
contenedor de la aplicación a 768 MB.

## Opción 1: Docker Compose

El `compose.yaml` de la raíz del repositorio conecta los dos contenedores y es el camino más
rápido a una instancia que funcione.

```bash
git clone https://github.com/dny1020/doction.git
cd doction

cp .env.example .env
# Edita .env: POSTGRES_PASSWORD y SECRET_KEY son las dos que importan.
# openssl rand -hex 24   → POSTGRES_PASSWORD
# openssl rand -hex 32   → SECRET_KEY

mkdir -p data/logs   # para que los bind mounts tengan tu uid; el contenedor corre como uid 1000
docker compose up -d
```

Abre <http://localhost:8000> y regístrate. **La primera cuenta es la que importa**: el registro
está abierto por defecto, así que crea la tuya de inmediato, luego define
`DISABLE_REGISTRATION=1` y reinicia.

Postgres solo se publica en `127.0.0.1:5432`, así que `psql` funciona en local sin exponer la base
de datos a la red.

## Opción 2: `docker run` simple, detrás de un proxy

Para un host en el que gestionas tú mismo el proxy inverso. Esta es la forma que usa el
despliegue de referencia.

```bash
docker network create doction-net

docker run -d --name doction-postgres --restart unless-stopped --network doction-net \
  -e POSTGRES_USER=doction \
  -e POSTGRES_PASSWORD=$(openssl rand -hex 24) \
  -e POSTGRES_DB=doction \
  -v /srv/doction/postgres:/var/lib/postgresql/data \
  postgres:16-alpine

docker run -d --name doction --restart unless-stopped --network doction-net \
  -p 127.0.0.1:8000:8000 \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  -e DATABASE_URL=postgresql://doction:<la-contraseña-de-arriba>@doction-postgres:5432/doction \
  -e SECURE_COOKIES=1 \
  -e DISABLE_REGISTRATION=1 \
  -e SEMANTIC_SEARCH=1 \
  -v /srv/doction:/data \
  -v /srv/doction/logs:/logs \
  ghcr.io/dny1020/doction:latest
```

Dos detalles en los que es fácil equivocarse:

- **Publica en loopback**, `-p 127.0.0.1:8000:8000`, no `-p 8000:8000`. Si no, la aplicación es
  accesible directamente, saltándose el proxy y su TLS.
- **Pon Postgres solo en una red interna.** No necesita ningún puerto publicado. El despliegue de
  referencia le da una red `db_net` aparte para que la base de datos siga siendo inaccesible
  aunque el proxy esté mal configurado.

Después termina el TLS en nginx, Caddy o Traefik apuntando a `http://127.0.0.1:8000`.

### nginx, mínimo

```nginx
server {
    listen 443 ssl http2;
    server_name wiki.example.com;

    ssl_certificate     /etc/letsencrypt/live/wiki.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/wiki.example.com/privkey.pem;

    # Imágenes y PDF subidos. Súbelo si pegas capturas de pantalla grandes.
    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

`client_max_body_size` es el que la gente olvida. nginx usa 1 MB por defecto, así que un archivo
subido más grande falla en el proxy con un 413 antes de que doction llegue a verlo.

## Opción 3: desde el código fuente

Para desarrollo, o para ejecutarlo sin Docker. Sigues necesitando un Postgres en algún sitio.

```bash
uv sync --dev
cd frontend && npm install && npm run build && cd ..

export DATABASE_URL=postgresql://doction:doction@localhost:5432/doction
export SECRET_KEY=$(openssl rand -hex 32)
export DATA_DIR=./data LOG_DIR=./data/logs

uv run uvicorn app.main:app --reload
```

El paso de build del frontend no es opcional. `app/static/app/` está en el gitignore (lo genera
el build de Docker), así que en un clon nuevo la ruta `/app` no sirve nada hasta que ejecutas
`npm run build` (o `make build-web`).

## Verificar la instalación

```bash
curl -s http://localhost:8000/health | jq
# {"status":"ok","db":"ok","version":"0.31.3"}
```

`db: "ok"` significa que el esquema se creó y es accesible. El esquema se construye con
`CREATE TABLE IF NOT EXISTS` en cada arranque, así que el primer arranque y todos los siguientes
ejecutan el mismo código: no hay paso de migración que recordar ni una escalera de migraciones que
mantener en orden.

Para comprobar la superficie para agentes sin autenticarte:

```bash
curl -s -X POST http://localhost:8000/api/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}' | jq .result.serverInfo
# {"name":"doction","version":"0.31.3"}
```

Esa es también la forma de confirmar qué versión ejecuta de verdad un despliegue remoto, lo que
importa porque los despliegues son manuales.

## Qué hacer después

1. Registra el primer usuario y luego define `DISABLE_REGISTRATION=1`.
2. Crea un token de acceso personal para tu agente: consulta [Agentes y MCP](mcp.md).
3. Configura las copias de seguridad antes de depender de él: consulta
   [Operación](operations.md). El volumen y la base de datos, o la restauración no funciona.
