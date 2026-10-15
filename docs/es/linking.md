---
source_sha256: beb9fc83f784d2d4e8b8bb52e188a52c2da2f2daed223274598c39e94fc7243f
---
# Enlazar páginas

Un wikilink es la forma en que una página apunta a otra. Dos formas:

```markdown
[[sip-trunk-runbook]]              el slug, tal cual
[[sip-trunk-runbook|el runbook]]   el slug, mostrado como "el runbook"
```

Los enlaces se analizan en cada guardado y se guardan en una tabla de aristas, que es de donde
salen los enlaces entrantes, el grafo y los insights del workspace. Nada del enlazado ocurre al
leer, así que el grafo siempre está tan al día como el último guardado.

## Qué cuenta como destino

El destino se convierte en un slug antes de buscarlo. Eso significa que **un título funciona como
destino**, porque un título se convierte en slug de la misma manera:

```markdown
[[Markdown Cheatsheet]]     se resuelve como markdown-cheatsheet
```

Dos enlaces que se reducen al mismo slug son una sola arista. `[[SIP Trunk Runbook]]` y
`[[sip-trunk-runbook]]` en la misma página producen un único enlace.

Un destino también se busca entre los alias que deja un renombrado, así que un enlace escrito
contra el slug antiguo de una página se sigue resolviendo después de renombrarla. Verificado: una
página renombrada desde `links-demo` sigue siendo accesible con `[[links-demo]]`.

Dos límites, los dos medidos:

- Un destino no puede contener `[`. `[[a[b]]` no produce ningún enlace.
- Un destino tiene como mucho 200 caracteres, y una etiqueta como mucho 200. Más largo no produce
  ningún enlace.

Ninguno es cosmético. Los dos vienen del patrón que encuentra los wikilinks: sin ellos, una página
de secuencias `[[` sin cerrar hacía cuadrático el análisis, y 24 KB así costaban 7,9 segundos de
CPU dentro del guardado. El razonamiento está en `app/meta.py` y en el cambio archivado que lo
corrigió.

Los enlaces dentro de código no son enlaces. Tanto un fragmento en línea como un bloque delimitado
se eliminan antes del análisis, así que `` `[[example]]` `` en una página sobre wikilinks sigue
siendo un ejemplo.

## Un enlace roto es información, no un error

Enlazar a una página que no existe está permitido y queda registrado. La arista se guarda con su
slug de destino y sin página resuelta, que es la única representación que tiene un enlace roto.

De ahí salen dos cosas, y la segunda es la útil:

1. `GET /api/insights` informa de `broken_links`, y `GET /api/graph` marca la arista con
   `"broken": true`. Así puedes encontrar todos los enlaces colgantes de un workspace.
2. **El enlace se repara solo cuando se crea el destino.** Medido: una página que enlazaba a
   `[[does-not-exist]]` tenía una arista sin resolver; crear una página con ese slug resolvió la
   arista existente sin volver a guardar la página que enlazaba.

Eso hace razonable escribir enlaces a páginas que aún no has escrito. Es la manera wiki: el enlace
es la nota de que la página debería existir.

## Enlaces entrantes y vecindario

`GET /api/pages/{slug}/view` devuelve en una sola petición lo que necesita la vista de lectura,
`backlinks` incluido, así que abrir una página te dice qué apunta a ella sin una segunda llamada.

Para ir más lejos, `GET /api/graph` devuelve el grafo dibujable y la herramienta MCP
`get_linked_knowledge` recorre el grafo de enlaces en ambas direcciones hasta una profundidad
acotada. Consulta [el grafo](graph.md) para la forma de la respuesta del grafo y sus límites.

## Lo que ve el lector

Los wikilinks los renderiza el cliente, no el servidor. El servidor guarda y sirve markdown en
bruto y no renderiza nada, así que un wikilink en una respuesta `raw` sigue siendo `[[texto]]`.

El cliente los convierte en anclas con una regla en línea de markdown-it que emite tokens en lugar
de construir una cadena HTML. Es deliberado: insertar en un `href` un destino tomado de un
documento es como se produjo el fallo de cross-site scripting almacenado del primer cambio de
endurecimiento de este proyecto. Si escribes tu propio cliente, ten el mismo cuidado.

## Siguientes pasos

- [Tags y metadatos](tags-and-metadata.md), la otra forma en que las páginas se agrupan
- [El grafo](graph.md), que son estos enlaces dibujados
- [Escribir páginas](writing-pages.md) para los slugs, los renombrados y los alias
