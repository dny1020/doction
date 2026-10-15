---
source_sha256: 191827d62aaafe22d8eaff783a90d9525cdc99923ca1b119232d75cbce8072ce
---
# El grafo

Cada wikilink de un workspace es una arista, y `GET /api/graph` sirve el conjunto como algo
dibujable:

```bash
curl -s -H "authorization: Bearer $TOKEN" $DOCTION/api/graph
```

```json
{
  "nodes": [{"slug": "welcome", "title": "Welcome", "incoming": 0, "outgoing": 0, "orphan": true}],
  "edges": [{"source": "links-demo", "target": "does-not-exist", "broken": true}],
  "pages": 15,
  "truncated": false
}
```

Cuatro cosas que conviene saber de esa respuesta:

- `orphan` significa sin enlaces de entrada ni de salida. En un workspace joven la mayoría de las
  páginas son huérfanas, lo cual es exacto y no un defecto: medido en un workspace de 15 páginas,
  10 eran huérfanas.
- `broken` en una arista significa que el destino aún no existe. La arista sigue en el grafo,
  porque [un enlace roto es información](linking.md#un-enlace-roto-es-informacion-no-un-error).
- `pages` es el número de páginas del workspace, así que puedes saber si estás viéndolo entero.
- `truncated` dice si no lo estás. Por encima de 300 nodos la respuesta se recorta al subgrafo de
  mayor PageRank, así que un workspace grande devuelve su parte más conectada en lugar de una
  respuesta que nadie puede dibujar ni leer.

El recorte se hace por PageRank y no por antigüedad ni por orden alfabético porque la pregunta que
responde un grafo es qué páginas importan y cómo se conectan. Quitar la periferia mantiene eso
legible; quitar el centro no.

## La vista de grafo

La interfaz lo dibuja en `/w/<workspace>/graph`, como un SVG que escribe la propia aplicación y no
mediante una biblioteca de gráficos. Cada color es un token de diseño, y eso es lo que hace que los
dos temas funcionen sin una segunda paleta.

Cada etiqueta va centrada bajo su nodo, y un título de más de 24 caracteres se abrevia. Hasta 40
nodos se etiquetan todas las páginas; por encima, solo las que tienen enlaces. La disposición se
dimensiona según los títulos que tiene que colocar, así que las etiquetas no se solapan:
`frontend/src/graphLayout.test.js` estabiliza la simulación y falla si dos cajas de etiqueta se
cruzan.

## Leer el grafo sin dibujarlo

`GET /api/insights` responde a las mismas preguntas en prosa en lugar de en geometría, y suele ser
la llamada más útil:

| Campo | Qué te dice |
| --- | --- |
| `central`, `authorities`, `hubs` | a qué páginas apunta la estructura de enlaces |
| `orphans` | páginas a las que nada enlaza y que no enlazan a ninguna parte |
| `broken_links` | cada enlace cuyo destino no existe |
| `duplicates` | páginas que parecen casi copias unas de otras |
| `clusters` | grupos que sugiere la estructura de enlaces |

Para un agente que sale desde una página, la herramienta MCP `get_linked_knowledge` hace un
recorrido en anchura del grafo de enlaces en ambas direcciones, limitado a profundidad 3 y 100
nodos. Esos límites existen porque un recorrido sin límite de una wiki bien enlazada devuelve la
wiki entera.

Las matemáticas del grafo son numpy simple, sin biblioteca de grafos: PageRank, un k-means
determinista para los clusters y las estadísticas de enlaces de arriba. Eso mantiene corta la
lista de dependencias y los resultados reproducibles entre ejecuciones.

## Siguientes pasos

- [Enlazar páginas](linking.md) para los enlaces de los que está hecho
- [Agentes y MCP](mcp.md) para `get_linked_knowledge` y las demás herramientas
