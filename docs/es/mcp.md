---
source_sha256: 8a685672101e7562751f7ce8e4bb87ed77df8a7be266524da9e436e135e7be62
---
# Agentes y MCP

doction habla MCP (Model Context Protocol) de forma nativa en `POST /api/mcp`: JSON-RPC 2.0, sin
estado, sin SDK. 27 herramientas sobre los mismos datos que ven la API REST y la interfaz web.

El reparto del trabajo es lo importante. **doction recupera; tu agente genera.** Dentro de doction
no hay ningún modelo de lenguaje, así que ninguna herramienta escribe prosa: `summarize_page` es
TextRank extractivo, que selecciona frases que ya existen.

## Autenticación

`initialize` y `tools/list` son abiertos, así que un cliente puede descubrir el servidor sin
credenciales. `tools/call` requiere un token Bearer.

`initialize` también devuelve `instructions`, que los clientes MCP muestran al modelo: las páginas
solo se conectan mediante wikilinks `[[slug]]` / `[[slug|label]]`, anidar una página bajo un padre
no las enlaza, y `suggest_links` encuentra lo que merece la pena enlazar. Un agente lo aprende al
conectarse, así que un prompt no tiene que repetirlo.

Funcionan dos tipos:

| Token | Duración | Se obtiene con | Úsalo para |
| --- | --- | --- | --- |
| Token de acceso personal, `doction_…` | hasta que se revoque | `POST /api/tokens` | agentes, scripts, cualquier cosa de larga duración |
| JWT | 7 días | `POST /api/token` | sesiones de corta duración |

Crea un token de acceso personal:

```bash
curl -s -X POST $DOCTION/api/tokens \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $EXISTING_TOKEN" \
  -d '{"name":"my-laptop"}' | jq
# {"id":1,"name":"my-laptop","token":"doction_..."}
```

**El texto en claro se muestra una sola vez.** Solo se guarda un hash SHA-256, así que un token
perdido se regenera, nunca se recupera. Lístalos con `GET /api/tokens` y revócalos con
`DELETE /api/tokens/{id}`, que tiene efecto inmediato.

## Conectar un agente

Claude Code:

```bash
claude mcp add --transport http doction $DOCTION/api/mcp \
  --header "Authorization: Bearer doction_..."
```

Cualquier otro cliente MCP: apúntalo a `$DOCTION/api/mcp` por HTTP con esa misma cabecera
`Authorization`. No hay transporte stdio ni proceso local que lanzar: el servidor es el
despliegue.

Verifica la conexión sin un cliente:

```bash
curl -s -X POST $DOCTION/api/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}' | jq
# {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-03-26",
#  "capabilities":{"tools":{}},"serverInfo":{"name":"doction","version":"0.31.3"}}}
```

## Las cinco herramientas que cubren casi todo

El bucle de un agente es: encontrar algo, reunir contexto, entender la forma del workspace, leer
un documento exactamente como está guardado y escribir lo que aprendió.

| Herramienta | Qué hace |
| --- | --- |
| `search_knowledge` | páginas ordenadas para una consulta; rankings léxico y vectorial fusionados por posición recíproca, filtrables por tag y tipo |
| `get_rag_context` | los k mejores pasajes reunidos, con su procedencia, dentro de un presupuesto de caracteres |
| `get_workspace_tree` | workspaces, páginas y subpáginas como una jerarquía |
| `read_page_raw` | el markdown de una página exactamente como está guardado, frontmatter incluido |
| `upsert_page_section` | crea o sustituye una sección de una página sin reescribir el resto |

`upsert_page_section` es la que hay que usar para añadir algo a un runbook. Reescribir una página
entera para añadir un párrafo produce un diff que nadie puede revisar.

## Elegir entre las herramientas de búsqueda

Cuatro herramientas devuelven «páginas relevantes» y no son intercambiables.

| Herramienta | Ordenación | Úsala cuando |
| --- | --- | --- |
| `search_pages` | texto completo de Postgres, `ts_rank` | conoces el término que aparece en la página |
| `sgrep` | semántica, combinada con un refuerzo por palabra clave | conoces la *idea* pero no las palabras |
| `search_knowledge` | léxica y vectorial fusionadas por posición recíproca | uso general; la mejor opción por defecto |
| `rag` | los k mejores fragmentos, no páginas, con su procedencia | vas a sintetizar una respuesta y necesitas pasajes |

`sgrep` y `rag` necesitan `SEMANTIC_SEARCH=1`. Si está desactivada, vuelven a la búsqueda de texto
completo en lugar de fallar, así que una llamada sigue devolviendo algo útil: mira el campo `mode`
de la respuesta para saber qué camino respondió.

A diferencia de la barra lateral de la interfaz web, `sgrep` devuelve la lista ordenada completa,
sin filtrar. Es deliberado: un agente debe decidir qué es relevante, no recibir el corte de otro.

## Recorridos: enlaces frente a tags

Tres herramientas recorren el grafo, y confundirlas da respuestas equivocadas.

| Herramienta | Recorre | Responde |
| --- | --- | --- |
| `list_backlinks` | wikilinks, un salto, de entrada | «¿qué hace referencia a esta página?» |
| `get_linked_knowledge` | wikilinks, hasta 3 saltos, en ambas direcciones | «¿cuál es el vecindario de esta página?»: cada resultado lleva su distancia, dirección, camino y si el destino existe |
| `related_pages` | tags compartidos | «¿qué más trata de este tema?» |

Dos páginas pueden compartir todos los tags y no hacerse referencia nunca. Los enlaces son una
afirmación que hizo alguien; los tags son una categoría que alguien asignó. Preguntas distintas,
herramientas distintas.

Que `get_linked_knowledge` devuelva una página marcada como inexistente no es un error: un
wikilink roto es información, y es como encuentras la página que alguien quería escribir.

## La lista completa de herramientas

| Herramienta | Qué hace |
| --- | --- |
| `list_workspaces` | lista los workspaces |
| `list_members` | lista los miembros de un workspace |
| `list_pages` | árbol de páginas |
| `list_children` | subpáginas directas de una página |
| `get_page` | lee una página (markdown + metadatos) |
| `read_page_raw` | markdown exactamente como está guardado, frontmatter incluido |
| `create_page` | crea una página + commit de git |
| `update_page` | actualiza una página + commit de git |
| `upsert_page_section` | crea o sustituye una sección |
| `move_page` | cambia el padre de una página (sin ciclos) |
| `rename_page` | cambia un slug, dejando un alias para que los enlaces antiguos se resuelvan |
| `delete_page` | eliminación suave, a la papelera |
| `get_page_history` | el historial de git de una página |
| `search_pages` | búsqueda de texto completo |
| `search_knowledge` | ordenación fusionada léxica + vectorial |
| `sgrep` | búsqueda semántica con refuerzo por palabra clave |
| `rag` | los k mejores fragmentos con su procedencia |
| `get_rag_context` | pasajes reunidos dentro de un presupuesto de caracteres |
| `extract` | consulta estructurada por `type:` del frontmatter / tags (sin LLM) |
| `list_backlinks` | wikilinks de entrada, un salto |
| `get_linked_knowledge` | vecindario de wikilinks hasta 3 saltos |
| `related_pages` | vecinas por tags compartidos |
| `get_workspace_tree` | jerarquía de workspaces, páginas y subpáginas |
| `suggest_links` | páginas a las que esta página debería enlazar y no enlaza |
| `suggest_tags` | tags candidatos mediante TF-IDF |
| `summarize_page` | resumen extractivo con TextRank (sin LLM) |
| `workspace_insights` | PageRank, páginas huérfanas, hubs, enlaces rotos, duplicados, clusters de temas |

## Notas para escribir un agente contra esto

- **Cada resultado de inteligencia lleva un campo `mode`** que dice cómo se produjo. Quien llama
  puede distinguir una respuesta vectorial de una de respaldo por palabra clave, lo que importa
  cuando `SEMANTIC_SEARCH` está desactivada y esperabas semántica.
- **Las escrituras son commits.** `create_page` y `update_page` producen un commit de git cada
  una, así que un bucle que guarda tras cada token produce un historial ilegible. Agrupa la
  edición.
- **`rename_page` deja un alias**, así que los wikilinks existentes se siguen resolviendo. No
  necesitas reescribir todas las páginas que hacen referencia.
- **`delete_page` es una eliminación suave.** La página queda en la papelera, recuperable mediante
  la API REST. Un agente no puede destruir contenido de forma permanente.
- **Las páginas recién escritas no se pueden buscar semánticamente al instante.** El proceso de
  embeddings es asíncrono. La búsqueda de texto completo ve la página de inmediato, porque Postgres
  mantiene la columna `tsvector` él solo.
- **Limita tus escrituras a un workspace.** El acceso es por pertenencia, y un token lleva las
  pertenencias de su usuario. Un token no puede llegar a un workspace al que su usuario nunca fue
  añadido.
