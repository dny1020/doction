---
source_sha256: 9bd6fc23ba049851cc0af9d0461ebe68a4243096bf85023bd5b4cf42036b51b4
---
# Operación

Cómo mantener doction en marcha después de instalarlo. Todo lo de aquí asume la forma de dos
contenedores de [Instalación](install.md).

## Salud y versión

```bash
curl -s $DOCTION/health | jq
# {"status":"ok","db":"ok","version":"0.31.3"}
```

`status` es el proceso, `db` es la conexión a Postgres. Un `200` con `"db":"error"` significa que
la aplicación está arriba y la base de datos no: revisa el contenedor de la base de datos antes que
nada.

`GET /api/system` (con autenticación) añade qué funciones opcionales quedaron activadas de verdad.
Úsalo para confirmar que una variable tuvo efecto en lugar de fiarte del entorno que crees haber
definido:

```bash
curl -s -H "Authorization: Bearer $TOKEN" $DOCTION/api/system | jq
# {"version":"0.31.3","db":"ok","semantic_search":true,"rerank":false,"ocr_uploads":false, ...}
```

Para un despliegue remoto en el que no tienes shell, el endpoint MCP responde sin autenticación:

```bash
curl -s -X POST $DOCTION/api/mcp -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}' \
  | jq .result.serverInfo.version
```

## Verificar una imagen descargada

Cada imagen publicada lleva un SBOM y la procedencia SLSA, así que puedes responder «¿qué hay
dentro?» y «¿de dónde viene?» sin desempaquetar capas ni preguntar al mantenedor.

```bash
# Qué hay dentro: cada paquete y su versión, en SPDX.
docker buildx imagetools inspect ghcr.io/dny1020/doction:0.31.5 \
  --format '{{ json .SBOM }}'

# De dónde viene: la ejecución de CI que la construyó, sus pasos y sus entradas resueltas.
docker buildx imagetools inspect ghcr.io/dny1020/doction:0.31.5 \
  --format '{{ json .Provenance }}'
```

La procedencia nombra la ejecución de GitHub Actions que produjo la imagen, así que puedes
compararla con el commit que declara la versión. Las dos atestaciones van adjuntas al índice de la
imagen como manifiestos adicionales, y por eso `docker manifest inspect` muestra entradas cuya
plataforma es `unknown/unknown`.

Las notas de cada versión están en su GitHub Release, generadas a partir de `CHANGELOG.md`. Las
releases empiezan en la 0.31.5; las etiquetas anteriores son previas a la automatización y no
tienen, porque el changelog describe esa historia por rangos y no por versión.

## Copia de seguridad

**Dos mitades, y una sin la otra no restaura.** La base de datos es un índice de los archivos; los
archivos son el contenido.

| Qué | Dónde | Por qué |
| --- | --- | --- |
| Páginas y archivos subidos | `DATA_DIR` (`/data`): un repositorio git más los archivos subidos | El contenido y su historial completo |
| Base de datos | el volumen de Postgres | Índice de búsqueda, tags, grafo de enlaces, usuarios, tokens, workspaces |
| Logs | `LOG_DIR` (`/logs`) | Solo para diagnóstico. No los incluyas. |

Una copia de seguridad mínima y correcta:

```bash
#!/bin/sh
set -eu
STAMP=$(date +%F)
DEST=/srv/backups/doction/$STAMP
mkdir -p "$DEST"

# Primero la base de datos, luego los archivos. Una página guardada entre los dos pasos aparece
# en los archivos sin fila; reindexar al restaurar lo arregla. El orden inverso pierde la página.
docker exec doction-postgres pg_dump -U doction -Fc doction > "$DEST/doction.dump"
tar -C /srv/doction -czf "$DEST/data.tar.gz" pages uploads

sha256sum "$DEST"/* > "$DEST/SHA256SUMS"
```

El comentario sobre el orden es lo que importa. Vuelca la base de datos *antes* de archivar los
archivos, para que cualquier página escrita entre los dos pasos exista en disco sin fila de índice,
lo que se recupera reindexando. El orden inverso produce una fila de índice para un archivo que no
tienes, y eso no se recupera.

No hay copia de seguridad automática ni vuelta atrás incorporada. Es un cron que escribes tú.

## Restauración

Pruébala antes de necesitarla. Una copia de seguridad sin probar no es una copia de seguridad.

```bash
# 1. Para la aplicación. Deja Postgres en marcha.
docker stop doction

# 2. Verifica el archivo antes de tocar nada.
cd /srv/backups/doction/<fecha> && sha256sum -c SHA256SUMS

# 3. Restaura primero la base de datos en una base de datos auxiliar, nunca sobre la activa.
docker exec -i doction-postgres createdb -U doction doction_restore
docker exec -i doction-postgres pg_restore -U doction -d doction_restore --clean < doction.dump

# 4. Compruébala: número de filas y la página más reciente.
docker exec -i doction-postgres psql -U doction -d doction_restore \
  -c 'select count(*) from pages' -c 'select slug, updated_at from pages order by updated_at desc limit 5'

# 5. Solo ahora haz el cambio. Restaura los archivos, apunta DATABASE_URL a la base de datos
#    restaurada (o renombra las bases de datos) y arranca la aplicación.
tar -C /srv/doction -xzf data.tar.gz
docker start doction
```

Restaurar los archivos pero no la base de datos, o al revés, deja los dos desincronizados. El
esquema converge al arrancar, así que las tablas serán correctas, pero las filas que describen
páginas que no están en disco, o las páginas sin filas, siguen mal hasta que se reindexan.

## Actualizar

Los despliegues son manuales. Nada en el host reacciona por sí solo a un push.

```bash
cd /opt/doction          # donde estén tu compose.yaml y tu .env
docker compose pull
docker compose down
docker compose up -d
curl -s http://127.0.0.1:8000/health | jq .version
```

Antes de hacer pull:

- **Haz una copia de seguridad.** No hay procedimiento de vuelta atrás, y la etiqueta de imagen en
  la que estabas es tu única forma de volver.
- **Lee `CHANGELOG.md`** para las versiones que te saltas.

Qué pasa en el primer arranque de una imagen nueva:

- El esquema converge. `CREATE TABLE IF NOT EXISTS` para todo lo nuevo, y las columnas
  `search_vector` se reconstruyen solo si cambió su expresión de generación. Esa reconstrucción es
  una reescritura de la tabla más un índice GIN, y se ejecuta sola.
- Volver *atrás* a una imagen anterior es seguro por la misma razón: el código anterior compara
  las mismas expresiones y hace converger la columna de vuelta.

### Volver atrás

Fija la etiqueta anterior y reinicia:

```bash
# en compose.yaml: image: ghcr.io/dny1020/doction:0.31.2
docker compose up -d
```

Funciona porque el esquema converge en las dos direcciones. **No** deshace cambios en los datos:
las páginas editadas con la versión nueva siguen editadas.

## Logs

Dos destinos, siempre: stdout y un archivo rotado bajo `LOG_DIR`.

```bash
docker compose logs -f doction          # stdout
tail -f /srv/doction/logs/doction.log   # el archivo rotado
```

Monta `LOG_DIR` como un volumen propio. En Docker, un directorio de logs que no está montado
desaparece con el contenedor, que es justo cuando quieres leerlo.

Para aumentar el detalle, define `LOG_LEVEL=DEBUG` y reinicia. Llega a los logs de la aplicación,
no solo a los de uvicorn: el logger raíz se configura al importar precisamente por eso.

## Capacidad y uso de recursos

El despliegue de referencia funciona en hardware autoalojado modesto (una Raspberry Pi) con el
contenedor de la aplicación limitado a `768m`, con `SEMANTIC_SEARCH=1` activada y el reranker
desactivado. Ese límite tiene margen de sobra.

Los dos modelos opcionales son lo que mueve la cifra. El modelo de embeddings ocupa ~23 MB en
disco; activar además el reranker necesita unos 80–100 MB más de memoria residente, que es la
cifra a reservar frente a un límite de contenedor ajustado.

Los dos modelos se cargan **bajo demanda**, en la primera consulta que los necesita, no al
arrancar. Dimensionar un contenedor según su uso al arrancar es como acabas con un cierre por falta
de memoria una hora después. Mide después de una búsqueda, no después de un reinicio.

Vigila, más o menos en el orden de lo que falla de verdad:

- **El disco del volumen `DATA_DIR`.** Cada guardado es un commit. El repositorio crece y nunca
  encoge por sí solo.
- **El volumen de Postgres**, dominado por `page_chunks` cuando la búsqueda semántica está activa.
- **La memoria**, si activaste el reranker dentro de un límite de contenedor ajustado.

## Webhooks

Los webhooks salientes van firmados con HMAC-SHA256 y se entregan desde un hilo aparte, nunca en
el camino de la petición. `db.emit_event()` encola en `webhook_deliveries` *dentro de la
transacción que hizo la escritura*, así que nunca se emite un evento de una escritura que se
deshizo, y `delivery_worker()` vacía la cola por separado con reintentos espaciados.

Eventos: `page.created`, `page.updated`, `page.deleted`, `page.moved`, `page.renamed`.

Consulta las entregas de cada webhook con `GET /api/webhooks/{id}/deliveries`: ahí es donde
aparece un endpoint que falla, porque una entrega fallida nunca se ve en la petición que la causó.

## Mantenimiento rutinario

Hay muy poco, por diseño.

- **Rota los tokens de acceso personal** que diste a los agentes. `GET /api/tokens` los lista,
  `DELETE /api/tokens/{id}` revoca uno de inmediato.
- **Vacía la papelera.** Las eliminaciones son suaves: `GET /api/trash` las lista,
  `POST /api/trash/{slug}/restore` recupera una, `POST /api/trash/{slug}/purge` la elimina para
  siempre.
- **Revisa `workspace_insights`** de vez en cuando. Las páginas huérfanas y los enlaces rotos son
  la degradación de una wiki, y es lo único que informa de ellos.
- **Confirma la versión desplegada después de cada despliegue.** Los despliegues manuales son como
  un host acaba ejecutando algo que no creías que ejecutaba.
