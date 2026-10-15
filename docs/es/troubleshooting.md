---
source_sha256: 53478d99046748acbf4e478f7470f2e9603c45f9eeb964ad9f22035a8d339083
---
# Resolución de problemas

Primero el síntoma. Cada entrada dice qué revisar y por qué el fallo se ve como se ve.

## El servidor no arranca

### `RuntimeError: SECRET_KEY must be set to a real secret when SECURE_COOKIES is enabled`

Funciona según lo previsto. Con `SECURE_COOKIES=1` (la señal de que estás en producción detrás de
TLS) doction se niega a arrancar con una clave sin definir o con uno de los valores de ejemplo de
`.env.example` (`change-me`, `changeme`, `dev-secret-key`).

```bash
openssl rand -hex 32
```

Pon eso en `SECRET_KEY` y reinicia. Cambiar la clave invalida todas las cookies de sesión y JWT
existentes; los tokens de acceso personal no se ven afectados, porque no se firman con ella.

### `/health` devuelve `"db": "error"`, o el arranque se queda esperando a la base de datos

La aplicación está arriba y Postgres no es accesible. Por orden:

```bash
docker compose ps                      # ¿el contenedor de postgres está en marcha y sano?
docker compose logs postgres | tail -30
```

La causa más común es que `DATABASE_URL` apunte a un nombre de host que no se resuelve desde
dentro del contenedor de la aplicación. El valor por defecto es
`postgresql://doction:doction@postgres:5432/doction`, donde `postgres` es un *nombre de servicio*
de Compose: se resuelve dentro de la red de Compose y en ningún otro sitio. Ejecutar la aplicación
fuera de Compose significa que ese host no existe.

### Errores de permisos en `/data` o `/logs`

El contenedor se ejecuta sin root, como uid 1000. Un bind mount creado por el propio `docker`
pertenece a root, y la aplicación no puede escribir en él.

```bash
mkdir -p data/logs
sudo chown -R 1000:1000 data
```

Crea los directorios antes del primer `up`; por eso lo dice la cabecera del archivo de Compose.

## Problemas de búsqueda

### Una palabra con acento no coincide con su forma sin acento

Si `renovacion` no encuentra una página titulada «Renovación TLS», el plegado de acentos no está
activo. Depende de la extensión `unaccent`, y si el rol de la base de datos no puede hacer
`CREATE EXTENSION unaccent`, doction lo registra en el log y recurre solo al stemmer en lugar de
negarse a arrancar.

```bash
docker compose logs doction | grep -i unaccent
docker exec -it doction-postgres psql -U doction -d doction -c 'CREATE EXTENSION IF NOT EXISTS unaccent;'
```

Reinicia la aplicación después de crearla. En el siguiente arranque las columnas `search_vector`
convergen a la expresión con plegado de acentos, que es una reescritura de la tabla más la
reconstrucción de un índice GIN, y ocurre sola.

### La búsqueda semántica no devuelve nada, o recurre a palabra clave

Tienen que cumplirse tres cosas, en este orden:

```bash
curl -s -H "Authorization: Bearer $TOKEN" $DOCTION/api/system | jq .semantic_search
```

1. `SEMANTIC_SEARCH=1` está definida **y el proceso la recogió**. El campo de `/api/system` es la
   respuesta que vale, no el entorno que crees haber definido.
2. El modelo se cargó. Se carga bajo demanda en la primera consulta, así que revisa los logs
   *después* de hacer una búsqueda, no después de un reinicio.
3. Las páginas tienen embeddings. El proceso es asíncrono: una página escrita hace un segundo se
   puede buscar por texto completo de inmediato y semánticamente un poco después.

Cada respuesta de inteligencia lleva un campo `mode`. Si indica un modo por palabra clave, doction
te está diciendo que se degradó en lugar de fallar, que es lo previsto.

### Los resultados de búsqueda contienen markdown en bruto

Los fragmentos se extraen del markdown guardado, así que en el extracto pueden aparecer barras de
tabla, `##` y `[[…]]`. Es cosmético; la ordenación no se ve afectada.

## La interfaz web

### Un cambio bajo `frontend/` no aparece

El bundle se construye, no se sirve desde el código fuente. `app/static/app/` está en el
gitignore y lo produce el build de Docker.

```bash
make build-web      # o: cd frontend && npm run build
```

**Esto incluye `app/static/style.css`.** Se enlaza con un hash de contenido que solo cambia al
hacer build, así que un cambio de CSS medido contra un servidor de desarrollo en marcha describe la
hoja de estilos *anterior*. Esto hace perder más tiempo que cualquier otra cosa de esta página.

### `/app` no sirve nada en un clon nuevo

La misma causa. Ejecuta el build del frontend una vez después de clonar, o usa la imagen
publicada, que ya contiene el bundle.

### Las subidas fallan con un 413

Es el proxy inverso, no doction. nginx tiene por defecto un límite de 1 MB para el cuerpo.

```nginx
client_max_body_size 25m;
```

### Una captura de pantalla pegada no se puede buscar

El OCR es opcional. Define `OCR_UPLOADS=1` y comprueba que `OCR_LANGS` nombra paquetes presentes
en la imagen (por defecto `eng+spa`). El OCR se ejecuta como tarea en segundo plano y un fallo
nunca rompe la subida, así que la única prueba está en los logs.

## Agentes y MCP

### `tools/call` devuelve un error de autenticación, `initialize` funciona

Es el comportamiento correcto: `initialize` y `tools/list` son abiertos para que un cliente pueda
descubrir el servidor, y `tools/call` necesita un token Bearer.

```bash
curl -s -X POST $DOCTION/api/mcp \
  -H "Authorization: Bearer doction_..." \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq '.result.tools | length'
# 27
```

### Un token dejó de funcionar

O se revocó, o era un JWT y caducó: los JWT duran 7 días y los tokens de acceso personal duran
hasta que se revocan. `GET /api/tokens` lista los tokens de acceso personal vigentes. Un texto en
claro perdido no se puede recuperar, solo sustituir: doction guarda un hash SHA-256.

### Un agente no ve un workspace

El acceso es la pertenencia al workspace, no la autoría. Un token lleva las pertenencias de su
usuario, y `pages.user_id` (quien la creó) y `pages.updated_by` (quien la editó por última vez)
son autoría, nunca permisos. Añade el usuario como miembro con
`POST /api/workspaces/{slug}/members`.

## Despliegue

### La versión desplegada no es la que esperaba

Los despliegues son manuales. Nada en el host reacciona a un push, así que una imagen publicada
por la CI no se ejecuta hasta que alguien la descarga.

```bash
curl -s $DOCTION/health | jq .version
```

Si va por detrás: `docker compose pull && docker compose down && docker compose up -d`.

### `docker compose pull` no encuentra la imagen

El paquete de GHCR tiene que seguir siendo público para que un host lo descargue sin iniciar
sesión. Revisa la visibilidad del paquete en los ajustes de Packages del repositorio.

### Las páginas existen pero la búsqueda no encuentra nada, después de una restauración

Restauraste una mitad. La base de datos es el índice; `DATA_DIR` es el contenido. Restaurar el
volumen sin el volcado deja en disco páginas que ninguna fila describe. Consulta el procedimiento
de restauración en [Operación](operations.md), y fíjate en el orden: el volcado antes del tar.

## Pedir ayuda

Abre un issue con la versión de `/health`, las variables opcionales que tienes activadas y una
reproducción: una llamada con `curl` distingue un fallo del servidor de uno del navegador. Sube
antes `LOG_LEVEL=DEBUG` e incluye las líneas relevantes, con los tokens ocultos.

Los problemas de seguridad van al
[canal privado de avisos](https://github.com/dny1020/doction/security/advisories/new), nunca a un
issue público.
