---
source_sha256: 18c562575e06f2f0bc2fcddb8b9d71d6e39789eefd22c2b1ecea2dfb6b1f76b2
---
# Arquitectura

doction es una aplicación FastAPI, una base de datos Postgres y un repositorio git de archivos
markdown. Ese es todo el sistema. Esta página explica cómo se relacionan los tres, y por qué varias
decisiones deliberadamente raras son las que son.

## La forma

```
            ┌──────────── doction (contenedor de la aplicación) ────────────┐    ┌─── postgres ───┐
  Navegador ┤  SPA de React en /app                                        │    │ páginas, FTS    │
  curl    ──┤  REST  /api/*                                                ├────┤ (tsvector/GIN), │
  Agente  ──┤  MCP   /api/mcp        repo git (un commit por guardado)     │    │ tags, enlaces,  │
            │                        embeddings (asíncrono, opcional)      │    │ vectores        │
            │                                           MiniLM ONNX        │    └─────────────────┘
            └───────────────────────────────────────────────────────────────┘
```

El servidor solo habla JSON. Guarda markdown en bruto y no renderiza nada en el servidor: el
navegador recibe el markdown y lo renderiza. Eso es lo que permite que los mismos endpoints sirvan
a un navegador, a `curl` y a un agente sin una API aparte.

## Dónde vive una página

Una página guardada existe en dos sitios a la vez, y cada uno responde a preguntas distintas.

**En disco**, como un archivo markdown en un repositorio git en
`{DATA_DIR}/pages/<workspace>/<slug>.md`. Es la fuente de verdad del contenido y del historial.
Cada guardado es un commit, así que `GET /api/pages/{slug}/history` es `git log` y la vista de
diferencias es `git diff`. Los fallos de git nunca rompen un guardado: la página se escribe y se
indexa igualmente, solo pierdes ese commit.

**En Postgres**, como una fila más sus metadatos extraídos. Es la fuente de verdad de las
*consultas*: la búsqueda, el índice de tags, el grafo de enlaces, el árbol de páginas. Aquí no hay
nada de contenido que fueras a echar de menos; todo se puede derivar de los archivos.

Esa división es la razón de que la copia de seguridad tenga dos mitades. La base de datos sola te
da un índice de páginas que ya no tienes; el volumen solo te da páginas sin búsqueda hasta que se
reindexan.

## El esquema converge, no migra

`init_db()` crea el esquema entero con `CREATE TABLE IF NOT EXISTS`. No hay escalera de
migraciones, ni tabla de versiones, ni `alembic upgrade head` en el procedimiento de despliegue.
Cada arranque ejecuta el mismo código.

Lo interesante es qué pasa cuando cambia la *definición*. `search_vector` es una columna generada,
así que su expresión está fijada en la tabla. Al arrancar, `_converge_search_vectors()` compara la
expresión de generación guardada de cada columna con la que declara el código, y reconstruye la
columna y su índice GIN solo cuando difieren.

Eso es lo que permite que un cambio en la configuración de búsqueda de texto llegue a una base de
datos existente sin SQL manual. También hace que volver atrás sea seguro en las dos direcciones:
una imagen anterior compara de la misma forma y hace converger la columna *de vuelta* por sí sola.

El coste es honesto: una reescritura de la tabla en el primer arranque tras un cambio así. A la
escala de una wiki es instantáneo.

## Búsqueda

Tres modos en `GET /api/search?mode=`:

- **`keyword`** (el modo por defecto): búsqueda de texto completo de Postgres sobre la columna
  `tsvector` generada, ordenada con `ts_rank`. Siempre disponible.
- **`semantic`**: similitud del coseno sobre los embeddings de los fragmentos, opcional.
- **`hybrid`**: primero los resultados de texto completo, luego los semánticos por encima de un
  umbral de puntuación, sin duplicados por slug.

**La barra lateral usa `hybrid`, y la elección importa.** La búsqueda semántica sola deja que un
término exacto pierda frente a una página que solo trata del mismo tema: escribes un nombre de host
y obtienes un ensayo. Poner primero los resultados léxicos lo arregla sin renunciar a la
recuperación conceptual.

**El `sgrep` de MCP se queda sin filtrar a propósito.** Una persona quiere la mejor respuesta
arriba; un agente quiere la lista ordenada completa para decidir él. Recortarla para un agente
tira el contexto sobre el que iba a razonar.

### La configuración de búsqueda de texto

La búsqueda usa una configuración de Postgres con nombre, `doction`: `unaccent` encadenado antes
de `english_stem`. La razón es concreta y merece la pena conocerla.

`to_tsvector('english', 'Renovación')` indexa el token con acento, así que una búsqueda de
`renovacion` no encontraba la página en absoluto. El plegado de acentos lo arregla, pero
`unaccent()` no se puede llamar directamente en una columna generada, porque es `STABLE`, no
`IMMUTABLE`. Dentro de una configuración de búsqueda de texto con nombre, sí. Esa indirección es la
única razón de que exista la configuración.

Cada constante del camino de búsqueda cita una medición en `evals/results/`. El banco de pruebas de
evaluación vive fuera de pytest deliberadamente: un número de calidad que puede romper un build es
un build que se acaba ignorando.

## Embeddings, cuando están activados

- Un modelo ONNX MiniLM int8, ~23 MB, incluido en la imagen. Se carga bajo demanda, así que con la
  variable desactivada no cuesta nada, y con ella activada no cuesta nada hasta la primera
  consulta.
- Los vectores viven en `page_chunks` como `BYTEA`. La similitud es el coseno de numpy más un
  refuerzo por palabra clave. No hay extensión de vectores ni base de datos vectorial.
- Un proceso en segundo plano calcula los embeddings de las páginas marcadas `embed_dirty`
  mediante `asyncio.to_thread`. Sin broker, sin Celery, sin Redis.
- Las lecturas de fragmentos se filtran por `model`, y el proceso vuelve a encolar las páginas
  cuyos vectores salieron de otro codificador. **Dos espacios de embeddings nunca deben mezclarse
  en un mismo coseno**: los números no tendrían sentido, y sin avisar.

doction solo recupera. Dentro no hay ningún LLM; el agente conectado es quien genera.

## Wikilinks y el grafo

`[[target]]` y `[[target|label]]` se analizan en cada guardado y van a `page_links`, que guarda
tanto el `dst_slug` en bruto como el `dst_page_id` resuelto.

Guardar la forma sin resolver es lo importante: **un enlace roto es información.** Es la única
representación que puede tener un enlace a una página que aún no existe, y mostrarla es como
`workspace_insights` informa de los enlaces rotos.

En el cliente, los wikilinks se convierten en anclas mediante una *regla en línea* de markdown-it
que emite tokens, nunca una cadena HTML. Insertar en `<a href>` un destino derivado de un
documento es exactamente la forma de un XSS almacenado, y esta es la mitigación.

`GET /api/graph` sirve el grafo dibujable, recortado al subgrafo de mayor PageRank pasado un
límite de nodos, y la ruta `/graph` lo dibuja como un SVG que escribe la propia aplicación. Por eso
los dos temas funcionan sin puentear la paleta: cada color es un token de diseño. mermaid, que es
un renderizador de terceros, necesitaba justo ese puente.

## ML local sin LLM

`suggest.py` y `graph.py` hacen el trabajo que normalmente se le encarga a un modelo:

| Función | Cómo |
| --- | --- |
| Sugerencias de enlaces | similitud TF-IDF contra el corpus del workspace |
| Sugerencias de tags | TF-IDF, sin necesidad de vectores |
| Detección de casi duplicados | coseno sobre los vectores de los fragmentos |
| Resúmenes | TextRank, **extractivo**: selecciona frases existentes y nunca escribe texto nuevo |
| Páginas centrales, hubs, páginas huérfanas | PageRank |
| Clusters de temas | k-means determinista |

Solo numpy. Ni NetworkX ni scikit-learn. Cada resultado lleva un campo `mode` que dice cómo se
produjo, así que quien llama puede distinguir una respuesta vectorial de una de respaldo por
palabra clave.

## Colaboración y acceso

Los workspaces se comparten mediante `workspace_members(workspace_id, user_id, role)` con los
roles `owner` y `member`. El acceso se controla al resolver el workspace, y por eso las consultas
de páginas filtran solo por `workspace_id`.

`pages.user_id` es quien la creó y `pages.updated_by` quien la editó por última vez. **Los dos son
autoría, nunca un control de acceso.** Leerlos como permisos es el error que este párrafo existe
para evitar.

Los slugs de workspace son únicos en todo el servidor, porque un slug es también el nombre de un
directorio en el repositorio git.

## Por qué no hay ORM

SQL directo sobre psycopg3 con un `ConnectionPool`. Las consultas de aquí son sobre todo búsqueda
de texto completo, recorridos recursivos del árbol y mantenimiento de columnas generadas: las tres
cosas que un ORM peor expresa y mejor esconde. Leer el SQL es como entiendes el rendimiento.

## Lo que no se busca, a propósito

- **Ningún LLM dentro de doction.** Solo recuperación.
- **Ninguna petición de red saliente en tiempo de ejecución**, salvo los webhooks que configures.
  Las fuentes, KaTeX, mermaid, highlight.js y d3-force los sirve el propio despliegue;
  `npm run check` rompe el build si se cuela un recurso remoto. doction funciona aislado de la red.
- **Sin SDK.** El servidor MCP es JSON-RPC 2.0 escrito a mano. Sin SDK de MCP, sin biblioteca de
  vectores, sin biblioteca de grafos.
- **Sin cuotas por inquilino.** Nada limita cuánto puede indexar un workspace. Carencia conocida.
