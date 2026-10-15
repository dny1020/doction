---
source_sha256: 18d40d8448aaa927dddc6566fa5f9acdfe80fc4f3179875b83805995a418d127
---
# Tags y metadatos

Una página puede llevar tags de dos maneras: en línea en el texto, o en un bloque de metadatos al
principio. Las dos se analizan en cada guardado y van al mismo sitio, así que un tag escrito de
cualquiera de las dos formas se comporta igual después.

## Tags en línea

Escribe `#tag` en cualquier parte del cuerpo:

```markdown
Notas sobre #kamailio y #sip-trunk.
```

Las reglas, todas medidas:

| Escrito | Queda como | Por qué |
| --- | --- | --- |
| `#Kamailio` | `kamailio` | los tags se pasan a minúsculas |
| `#sip-trunk` | `sip-trunk` | los guiones y guiones bajos forman parte de un tag |
| `#2026` | nada | un tag debe empezar por una letra |
| `` `#incode` `` | nada | el código en línea se elimina antes del análisis |
| `#infence` dentro de ``` | nada | los bloques delimitados también se eliminan |

La exclusión del código es la razón de que un comentario de shell, un color CSS o una directiva
del preprocesador de C en un bloque delimitado no se conviertan en un tag. También es por lo que
una página que documenta los tags puede mostrar ejemplos.

## El bloque de metadatos

Una página puede empezar con un bloque delimitado por `---`:

```markdown
---
title: SIP Trunk Runbook
tags: [kamailio, sip]
---

El cuerpo empieza aquí.
```

**Este bloque no es YAML.** Es un analizador pequeño sin dependencias, y entiende exactamente dos
formas: `clave: valor` y una lista en línea `clave: [a, b]`. Esa diferencia es la forma más común
de perder un tag sin que nadie te avise, así que merece la pena mostrarla como una medición:

```
---                           ---
tags:                         tags: [kamailio, sip]
  - kamailio                  ---
  - sip
---                           → tags: kamailio, sip        ✓

→ tags: (ninguno)    ✗
```

La forma de lista en bloque es YAML válido y se ignora sin avisar. Nada advierte, el guardado
funciona y la página se queda sin tags. Si vienes de Jekyll, Hugo u Obsidian, este es el único
sitio donde doction te sorprenderá, y la solución es escribir la lista en línea.

Una segunda consecuencia del mismo análisis: las líneas que no se entendieron se quedan donde
están. `GET /api/pages/{slug}/raw` en una página con una lista en bloque muestra el bloque
exactamente como se escribió, elementos de la lista incluidos.

El bloque forma parte del contenido de la página. Se guarda con la página y se indexa para la
búsqueda, así que una palabra que solo aparece en el bloque de metadatos sigue siendo encontrable.

## Encontrar páginas por tag

Los tags se guardan por página y son de donde salen los filtros por tag de la interfaz. Ten en
cuenta que **la búsqueda no tiene sintaxis de campos**: `tag:voip` en una consulta no es un filtro
por tag, son dos términos normales, uno de los cuales es la palabra literal «tag». Consulta
[buscar](search.md#no-hay-sintaxis-de-consulta).

## Tags sugeridos

`GET /api/pages/{slug}/suggest-tags` propone tags comparando los términos de la página con el
resto del workspace, mediante TF-IDF. No necesita embeddings ni modelo, así que funciona en
cualquier instancia.

Cada respuesta de sugerencias lleva un campo `mode` que dice cómo se produjo, que es la respuesta
honesta a «¿por qué sugirió eso?»: una sugerencia sacada de estadísticas de términos y una de un
modelo semántico no afirman lo mismo.

## Siguientes pasos

- [Buscar](search.md), incluido lo que hace realmente una consulta
- [Enlazar páginas](linking.md), la otra forma en que se relacionan las páginas
