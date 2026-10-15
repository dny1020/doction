---
source_sha256: 4d4fd189cc8aa0e25ef082360801994a0d3e39a5003e701ae125825db9ba7d3c
---
# API REST

El servidor de doction solo habla JSON. Guarda markdown en bruto, no renderiza nada, y cada
superficie de abajo devuelve JSON salvo que la tabla diga otra cosa.

Esta página enumera todas las operaciones que sirve la aplicación. No se mantiene a mano: un test
compara la lista de abajo con el esquema que produce la aplicación en marcha, y falla si se añade
un endpoint sin su entrada o si una entrada sobrevive a la eliminación de su endpoint. Si estás
leyendo una copia de esta página que venía con una versión, estaba completa para esa versión.

## Autenticación

Tres formas de entrar, para tres tipos de cliente distintos:

| Credencial | Cómo obtenerla | Duración |
| --- | --- | --- |
| Cookie de sesión | `POST /api/auth/login` | 7 días, `httponly` |
| JWT | `POST /api/token` | 7 días |
| Token de acceso personal | `POST /api/tokens` | hasta que se revoque |

```bash
# token de larga duración para un agente o un script; el texto en claro se muestra UNA vez
curl -s -X POST $DOCTION/api/tokens -b cookies.txt \
  -H 'content-type: application/json' -d '{"name": "my-laptop"}'
# → {"id": 1, "name": "my-laptop", "token": "doction_..."}

curl -s $DOCTION/api/pages -H "authorization: Bearer $TOKEN"
```

Un token que empieza por `doction_` se busca como token de acceso personal; cualquier otro se
prueba como JWT. Envíalo en `authorization: Bearer`.

Cuatro operaciones no necesitan credencial: `GET /health`, `GET /api/i18n`,
`POST /api/auth/login` y `POST /api/auth/register`. El registro está **abierto por defecto**, así
que una instancia en una dirección accesible deja que cualquiera cree una cuenta hasta que defines
`DISABLE_REGISTRATION=1`.

## Workspaces

Cada página pertenece a un workspace, y las operaciones sobre páginas actúan sobre el workspace
del contexto de la petición y no sobre uno nombrado en la ruta. Añade `?ws=<slug>` a cualquier
operación sobre páginas para elegir uno explícitamente, o cambia el predeterminado de la sesión
con `POST /api/workspaces/{slug}/switch`.

Los workspaces se comparten por pertenencia, con los roles `owner` y `member`. Los miembros se
añaden por el email de una cuenta existente, porque el servidor no envía correo.

## La documentación interactiva

La aplicación también sirve su propio esquema y dos navegadores para él:

| Ruta | Qué es |
| --- | --- |
| `/openapi.json` | el documento OpenAPI, generado a partir de las rutas en marcha |
| `/docs` | Swagger UI |
| `/redoc` | ReDoc |

**Las tres son públicas y no necesitan autenticación.** Verificado contra una instancia en marcha:
cada una responde 200 sin credencial. Describen la forma de la superficie, que es conocimiento
público en una aplicación de código abierto, pero la enumeran. Si eso no es lo que quieres en una
instancia accesible, bloquea las tres rutas en tu proxy inverso.

Los dos navegadores cargan su JavaScript y su CSS desde un CDN público. En una instancia sin
acceso a la red de salida cargan una página en blanco, mientras que `/openapi.json` sigue
funcionando, porque el documento en sí se sirve en local.

El documento declara la misma versión que informa `/health`, así que puedes saber qué build estás
leyendo.

Cada operación declara lo que devuelve. Los cuerpos JSON son modelos Pydantic de
`app/schemas.py`, validados a la salida, así que el esquema no puede prometer un campo que el
servidor dejó de enviar. El resto indica su tipo de medio: la exportación en zip, el markdown en
bruto, las imágenes subidas y el HTML de la aplicación.

## Todos los endpoints

```
# auth
POST   /api/auth/login
POST   /api/auth/logout
POST   /api/auth/register
POST   /api/token
GET    /api/tokens
POST   /api/tokens
DELETE /api/tokens/{token_id}

# account
POST   /api/lang/{code}
GET    /api/me
POST   /api/settings/password
POST   /api/settings/profile

# workspaces
GET    /api/workspaces
POST   /api/workspaces
DELETE /api/workspaces/{slug}
PUT    /api/workspaces/{slug}
GET    /api/workspaces/{slug}/export
GET    /api/workspaces/{slug}/members
POST   /api/workspaces/{slug}/members
DELETE /api/workspaces/{slug}/members/{member_id}
POST   /api/workspaces/{slug}/switch

# pages
GET    /api/notes
GET    /api/pages
POST   /api/pages
DELETE /api/pages/{slug}
GET    /api/pages/{slug}
PUT    /api/pages/{slug}
GET    /api/pages/{slug}/children
GET    /api/pages/{slug}/history
GET    /api/pages/{slug}/history/{sha}
GET    /api/pages/{slug}/history/{sha}/diff
POST   /api/pages/{slug}/move
GET    /api/pages/{slug}/raw
POST   /api/pages/{slug}/rename
POST   /api/pages/{slug}/restore/{sha}
GET    /api/pages/{slug}/view
GET    /api/trash
POST   /api/trash/{slug}/purge
POST   /api/trash/{slug}/restore

# search
GET    /api/search

# intelligence
GET    /api/graph
GET    /api/insights
GET    /api/pages/{slug}/suggest-links
GET    /api/pages/{slug}/suggest-tags
GET    /api/pages/{slug}/summary

# webhooks
GET    /api/webhooks
POST   /api/webhooks
DELETE /api/webhooks/{webhook_id}
GET    /api/webhooks/{webhook_id}/deliveries

# uploads
POST   /api/uploads
GET    /uploads/{name}

# mcp
POST   /api/mcp

# system
GET    /api/i18n
GET    /api/system
GET    /health

# app
GET    /
GET    /app
GET    /app/{full_path}
GET    /login
GET    /register
```

## Para qué sirve cada grupo

**auth** y **account** cubren la entrada y los ajustes propios del usuario con sesión iniciada. Un
token de acceso personal se muestra una vez al crearlo y solo se guarda como hash, así que un
token perdido se revoca y se sustituye, no se recupera.

**workspaces** cubre crear, compartir y exportar. `export` devuelve un zip de archivos markdown,
uno por página, que es la forma soportada de llevarte tu contenido a otro sitio.

**pages** es el grueso de la superficie: el árbol, el contenido de una página, las operaciones de
mover y renombrar, el historial de git y la papelera. [Escribir páginas](writing-pages.md) la
recorre en el orden en que la usarías de verdad.

**search** es una operación con tres modos. Merece la pena leer qué hace una consulta con lo que
escribiste antes de depender de ella: consulta [buscar](search.md).

**intelligence** es el aprendizaje automático local: sugerencias de enlaces y de tags, un resumen
extractivo, los insights del workspace y el grafo de wikilinks. Cada respuesta lleva un campo
`mode` que dice cómo se produjo, porque un resultado sacado de estadísticas de términos y uno de un
modelo de embeddings son afirmaciones distintas. Nada de esto llama a un tercero, y las partes que
usan embeddings vuelven a métodos más simples cuando `SEMANTIC_SEARCH` está desactivada.

**webhooks** entrega eventos de página a una URL que tú controlas, firmados con HMAC-SHA256. La
lista de entregas es de solo lectura, así que consultarla nunca provoca un reintento.

**uploads** recibe una imagen pegada en el editor y la vuelve a servir por una ruta autenticada,
así que una imagen de un workspace privado no se convierte en una URL pública.

**mcp** es el servidor Model Context Protocol completo, 27 herramientas detrás de un solo endpoint
JSON-RPC. Consulta [agentes y MCP](mcp.md).

**system** es lo que lee un monitor o un operador: `/health` para saber si está vivo y listo, y
`/api/system` para la versión, el estado de la base de datos y qué funciones de recuperación están
activas.

**app** es la superficie para el navegador y no una API: la aplicación de una sola página y las
redirecciones que llevan a ella.

## Errores

| Estado | Cuándo |
| --- | --- |
| 400 | la petición está bien formada pero se rechaza, como un contenido de página por encima del límite de 1 MiB |
| 401 | sin credencial, o con una que no es válida |
| 404 | la cosa no existe, **o existe y no es tuya** |
| 409 | un conflicto, como registrar un email que ya existe |
| 422 | el cuerpo no tiene la forma esperada |
| 429 | demasiados intentos de inicio de sesión fallidos para esa dirección y ese par de direcciones |

Responder 404 cuando no tienes permiso es deliberado. Responder 403 para un workspace que no puedes
ver confirmaría que existe.
