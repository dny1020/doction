---
source_sha256: 07274b2acc0cf687b9a8c23a8d21f46200cb45a2aad4c9ce694a128fe1c097a3
description: Una base de conocimiento autoalojada, markdown primero, para personas y agentes de código. Markdown plano en git, búsqueda local, una API REST y un servidor MCP nativo.
hide:
  - toc
---

<div class="dx-hero" markdown>
<div class="dx-hero-text" markdown>

<p class="dx-eyebrow">autoalojado · markdown primero · REST + MCP</p>

# doction

<p class="dx-lead">Una base de conocimiento en markdown para personas y agentes de código.
Escribe markdown plano en el navegador, guarda cada cambio en git y deja que tus agentes busquen,
lean y escriban las mismas páginas mediante una API REST o un servidor MCP nativo, en tu propio
hardware.</p>

<div class="dx-actions" markdown>

[Empezar](install.md){ .md-button .md-button--primary }
[API REST](api.md){ .md-button }
[MCP](mcp.md){ .md-button }

</div>

</div>

<div class="dx-hero-figure" role="img" aria-label="Un navegador, un agente y un script llegan a doction por /app, /api/mcp y /api; doction guarda las páginas en git, Postgres y embeddings."></div>

</div>

## Por qué doction

El conocimiento de ingeniería acaba repartido entre una wiki que leen las personas y lo que se le
dijo a un agente en su último prompt. doction guarda una sola copia: las páginas son markdown plano
en un repositorio git, la búsqueda se ejecuta en local y un agente llega a las mismas páginas que
una persona mediante una interfaz estándar.

Es aburrido a propósito. doction hace **recuperación**: el modelo de lenguaje vive en tu agente, no
aquí. Dentro no hay ningún LLM, ninguna clave de API ni ningún SaaS.

## Hecho para personas y agentes de código

<div class="grid cards" markdown>

-   **Markdown**

    ---

    Páginas, workspaces, `[[wikilinks]]`, `#tags` y un bloque de frontmatter. Se renderiza en
    el navegador a partir del markdown tal como está guardado.

-   **API primero**

    ---

    El servidor solo habla JSON. Los mismos endpoints sirven al navegador, a `curl` y a un
    agente.

-   **MCP**

    ---

    Un servidor MCP nativo en `/api/mcp` con 27 herramientas, desde la búsqueda y el contexto
    RAG hasta escribir una sola sección de una página.

-   **Búsqueda**

    ---

    Búsqueda de texto completo de PostgreSQL por defecto, con búsqueda semántica local opcional
    que funciona totalmente sin conexión.

-   **Grafo de conocimiento**

    ---

    Los wikilinks se convierten en aristas. Enlaces entrantes, enlaces rotos, páginas huérfanas
    y un grafo dibujable de todo el workspace.

-   **Autoalojado**

    ---

    Un contenedor de la aplicación y un contenedor de Postgres. Imagen multiarquitectura, amd64 y
    arm64, sin ninguna petición externa en tiempo de ejecución.

</div>

## Cómo funciona

La aplicación del navegador y los scripts usan la API REST bajo `/api`; los agentes usan MCP en
`/api/mcp`. En cada guardado, doction hace commit de la página en git y extrae su frontmatter, sus
tags y sus wikilinks a tablas indexadas. Con la búsqueda semántica activada, un proceso en segundo
plano trocea la página y calcula sus embeddings sin bloquear el guardado. Los detalles, y el porqué
de las decisiones que parecen raras, están en [Arquitectura](architecture.md).

## Funciones

- **Historial git por página**: cada guardado es un commit; consulta diferencias y versiones
  anteriores.
- **Búsqueda de texto completo**: `tsvector`/GIN de PostgreSQL con plegado de acentos, ordenada
  por `ts_rank`.
- **Búsqueda semántica local** (opcional): embeddings ONNX MiniLM incluidos en la imagen, sin
  claves de API; vuelve a la búsqueda de texto completo cuando está desactivada.
- **Un grafo que se ve**: los wikilinks se pueden seguir, cada página muestra qué enlaza a ella y
  la vista de grafo dibuja el workspace señalando las páginas huérfanas y los enlaces rotos.
- **ML local, sin LLM**: sugerencias de enlaces y de tags, detección de casi duplicados,
  resúmenes extractivos e insights del workspace, calculados con numpy.
- **Workspaces compartidos**: los colaboradores entran como `owner` o `member`.
- **Webhooks salientes**: eventos de página entregados a una URL que tú controlas, firmados con
  HMAC-SHA256.
- **OCR de archivos subidos** (opcional): tesseract indexa el texto de las capturas de pantalla
  pegadas.

## API + MCP

Los programas usan doction de dos maneras, sobre las mismas páginas y con la misma autenticación.

<div class="grid cards" markdown>

-   **[API REST](api.md)**

    ---

    Todos los endpoints que sirve la aplicación, agrupados, con la autenticación que necesita
    cada uno. Úsala desde scripts, trabajos de CI y `curl`.

-   **[MCP](mcp.md)**

    ---

    JSON-RPC 2.0 en `/api/mcp`, sin SDK. Conecta un agente con un token de acceso personal y
    elige entre las 27 herramientas.

</div>

```bash
claude mcp add --transport http doction $DOCTION/api/mcp \
  --header "Authorization: Bearer doction_..."
```

## Autoalojado

doction funciona como dos contenedores, la aplicación y Postgres, en hardware modesto que tú
controlas. Todo lo que carga el navegador lo sirve tu instancia, así que funciona en una LAN, por
una VPN o sin ruta a internet. Tus páginas siguen siendo markdown plano en un repositorio git que
es tuyo.

[Instalación](install.md) cubre Docker Compose, un `docker run` simple detrás de un proxy inverso
y la ejecución desde el código fuente. [Configuración](configuration.md) enumera todas las
variables de entorno y qué se rompe si te saltas alguna.

## Arquitectura

Una aplicación FastAPI, una base de datos Postgres y un repositorio git de archivos markdown. Ese
es todo el sistema. [Arquitectura](architecture.md) explica cómo se relacionan los tres: dónde vive
una página, cómo se construye la búsqueda, por qué el esquema converge en lugar de migrar y por qué
no hay ORM.

## Documentación

### Usar doction

| Página | Qué responde |
| --- | --- |
| [Escribir páginas](writing-pages.md) | Crear páginas, el árbol, los renombrados, el historial y recuperar una página eliminada |
| [Enlazar páginas](linking.md) | `[[wikilinks]]`, qué se resuelve como destino y por qué se conserva un enlace roto |
| [Tags y metadatos](tags-and-metadata.md) | `#tags`, el bloque al principio de una página y la única forma de escribirlo que se ignora sin avisar |
| [Buscar](search.md) | Los tres modos y lo que una consulta hace realmente con lo que escribiste |
| [El grafo](graph.md) | El grafo de enlaces, sus límites y los insights que lo leen sin dibujarlo |

### Desarrollo

| Página | Qué responde |
| --- | --- |
| [API REST](api.md) | Todos los endpoints que sirve la aplicación, agrupados, con la autenticación que necesita cada uno |
| [Agentes y MCP](mcp.md) | Conectar un agente, el modelo de autenticación y cuál de las 27 herramientas usar |
| [Arquitectura](architecture.md) | Cómo encajan las piezas y por qué las decisiones que parecen raras son las que son |

### Operar doction

| Página | Qué responde |
| --- | --- |
| [Introducción (en inglés)](https://doction.site/introduction/) | Capturas de pantalla y un inicio rápido |
| [Instalación](install.md) | Obtener una instancia funcionando, desde Compose hasta un `docker run` simple detrás de un proxy |
| [Configuración](configuration.md) | Cada variable de entorno, qué hace y qué se rompe si te la saltas |
| [Operación](operations.md) | Actualizaciones, copias de seguridad y restauración, logs, capacidad, qué hacer a las 3 de la madrugada |
| [Resolución de problemas](troubleshooting.md) | Índice por síntoma de los fallos que la gente encuentra de verdad |

### Proyecto (en inglés)

- [Contribuir](https://doction.site/CONTRIBUTING/): configuración local, la puerta de
  comprobaciones y cómo conseguir que se fusione un cambio.
- [Seguridad](https://doction.site/SECURITY/): el modelo de seguridad, el canal para reportar y la
  lista de endurecimiento.
- [Diseño](https://doction.site/DESIGN/): el sistema visual, que describe lo que está
  *implementado*.
- [Cambios](https://doction.site/CHANGELOG/): qué cambió en cada versión.
- `evals/results/`: las mediciones de recuperación detrás de las constantes de búsqueda: por qué
  el reranker viene desactivado y por qué el stemmer es el inglés.

### Convenciones de esta documentación

- Los comandos asumen el contenedor. Antepón `docker compose exec doction` si usas la pila de
  Compose.
- `$DOCTION` es la URL base de tu instancia, por ejemplo `https://wiki.example.com`.
- Todo lo marcado como **opcional** está desactivado salvo que actives su variable. doction arranca
  con todo lo costoso desactivado.

## Empezar

Dos contenedores, un `.env` y un primer usuario.

[Instalar doction](install.md){ .md-button .md-button--primary }
[Leer la introducción (en inglés)](https://doction.site/introduction/){ .md-button }
