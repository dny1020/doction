---
source_sha256: 718f751ab9db293b48d3905a0625472054ff6e5a3d7f0d8223182135fb4952d8
---
# Escribir páginas

Todo en doction es una página de markdown. El servidor la guarda en bruto, no renderiza nada y
hace commit en git de cada guardado. Esta página cubre cómo crear páginas, organizarlas,
cambiarlas y recuperarlas.

Los ejemplos usan `$DOCTION` como URL base y un token de acceso personal en `$TOKEN`. Consulta
[Agentes y MCP](mcp.md#autenticacion) para saber cómo obtener uno.

## Crear una página

```bash
curl -s -X POST $DOCTION/api/pages \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"title": "SIP Trunk Runbook", "content": "# SIP Trunk\n\nSteps here.\n"}'
# → {"slug": "sip-trunk-runbook", "title": "SIP Trunk Runbook"}
```

El slug sale del título, en minúsculas y con los espacios convertidos en guiones. Es la identidad
de la página en todas partes: la URL, la ruta de la API, el nombre del archivo en el repositorio
git y el destino de un wikilink. Pasa `slug` explícitamente para elegirlo tú.

`title` es opcional. Si lo omites, el título se toma de la primera línea del contenido, que es lo
que hace que merezca la pena guardar una captura de una línea sin inventarle un encabezado.

Los slugs son únicos por workspace. Los slugs de workspace son únicos en todo el servidor, porque
el slug de un workspace es también el nombre de un directorio en el repositorio git.

## Organizar: el árbol de páginas

Una página se convierte en subpágina indicando su padre al crearla:

```bash
curl -s -X POST $DOCTION/api/pages -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"title": "Dialplan notes", "content": "...", "parent_slug": "sip-trunk-runbook"}'
```

`GET /api/pages` devuelve el árbol completo como una lista plana, en la que cada entrada lleva
`slug`, `title` y `depth`. Es plana a propósito: el cliente dibuja la sangría a partir de
`depth`, y una lista plana cuesta una sola consulta por profundo que sea el árbol.
`GET /api/pages/{slug}/children` devuelve un nivel.

Cambiar de padre más tarde es mover. Pasar `null` mueve la página al nivel superior:

```bash
curl -s -X POST $DOCTION/api/pages/dialplan-notes/move \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"parent_slug": null}'
```

Mover es barato y no reescribe nada en disco. El repositorio git es plano, así que la jerarquía
es un puntero al padre en la base de datos y no una estructura de directorios.

## Cambiar una página

`PUT /api/pages/{slug}` es una actualización parcial. Envía `content`, `title` o los dos, y lo
que omitas se queda como estaba:

```bash
# cambia el título sin tocar el cuerpo
curl -s -X PUT $DOCTION/api/pages/sip-trunk-runbook \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"title": "SIP Trunk Runbook v2"}'
```

Cambiar el *slug* es renombrar, y es una operación distinta porque cambia la identidad de la
página:

```bash
curl -s -X POST $DOCTION/api/pages/sip-trunk-runbook/rename \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"slug": "sip-trunk-runbook-v2"}'
```

Un renombrado deja un alias, así que el slug antiguo se sigue resolviendo y los enlaces escritos
contra él no se rompen. Verificado: después del renombrado de arriba,
`GET /api/pages/sip-trunk-runbook` sigue respondiendo 200.

El contenido de una página está limitado a 1 MiB. Por encima, el guardado se rechaza con un 400 y
un mensaje que indica los dos tamaños:

```
page content is 1,048,586 bytes, over the 1,048,576-byte limit
```

El límite se aplica en la capa de almacenamiento y no en el borde HTTP, así que vale igual para la
API REST que para un agente que escribe por MCP.

## Historial

Cada guardado es un commit de git, hecho en silencio y en segundo plano. Un fallo de git nunca
hace fallar un guardado, lo que significa que el historial es de mejor esfuerzo por diseño: la
página es la fuente de verdad y el repositorio es el registro.

```bash
curl -s $DOCTION/api/pages/sip-trunk-runbook/history -H "authorization: Bearer $TOKEN"
# → [{"sha": "202540c", "timestamp": "...", "author": "you@example.org",
#     "message": "Save: SIP Trunk Runbook"}, ...]
```

A partir de un `sha` puedes leer el contenido tal como era, compararlo con su padre o
restaurarlo:

| Operación | Qué te da |
| --- | --- |
| `GET /api/pages/{slug}/history/{sha}` | el contenido en ese commit |
| `GET /api/pages/{slug}/history/{sha}/diff` | el cambio que hizo ese commit |
| `POST /api/pages/{slug}/restore/{sha}` | ese contenido como un guardado nuevo, así que la restauración queda también en el historial |

## Eliminar, y recuperar

`DELETE /api/pages/{slug}` responde 204 y la página deja de resolverse: una lectura posterior da
404. La fila no desaparece, se marca como eliminada, y la página queda en la papelera:

| Operación | Qué hace |
| --- | --- |
| `GET /api/trash` | lista las páginas eliminadas |
| `POST /api/trash/{slug}/restore` | recupera una |
| `POST /api/trash/{slug}/purge` | la elimina de verdad, 204 |

Así que eliminar se puede deshacer y purgar no. El historial de git sobrevive a una purga, porque
los commits están en el repositorio y no en la base de datos.

## Sacarlo todo

`GET /api/workspaces/{slug}/export` devuelve el workspace como un zip de archivos markdown, uno
por página. Es la respuesta a «¿cómo me voy?», y no necesita más herramientas que `unzip`.

`GET /api/pages/{slug}/raw` devuelve una página como markdown `text/plain`, exactamente como está
guardada, incluido el bloque de metadatos si la página lo tiene.

## Siguientes pasos

- [Enlazar páginas](linking.md) para los `[[wikilinks]]` y lo que significa un enlace roto
- [Tags y metadatos](tags-and-metadata.md) para los `#tags` y el bloque al principio de una
  página
- [Buscar](search.md) para volver a encontrar cualquier cosa
