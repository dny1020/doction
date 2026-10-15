---
source_sha256: eb9aec79aa2f802aa97c46af2dd9aa01a5f749cb5f3e9a5c01002993cac95c8d
---
# Buscar

```bash
curl -s -H "authorization: Bearer $TOKEN" --get $DOCTION/api/search --data-urlencode "q=kamailio"
```

La búsqueda se limita a un workspace y tiene tres modos, que se eligen con `mode=`:

| Modo | Qué usa | Disponible |
| --- | --- | --- |
| `keyword` | búsqueda de texto completo de PostgreSQL | siempre, y es el modo por defecto |
| `semantic` | embeddings locales | necesita `SEMANTIC_SEARCH=1` |
| `hybrid` | los dos, fusionados por posición | necesita `SEMANTIC_SEARCH=1` |

La barra lateral de la interfaz usa `hybrid`, porque la semántica sola deja que un término exacto
pierda frente a una página que solo está relacionada. El `sgrep` de MCP devuelve la lista ordenada
sin filtrar, porque un agente quiere hacer su propio corte.

En una instancia con la búsqueda semántica desactivada, una consulta `semantic` o `hybrid` se
responde con resultados por palabra clave en lugar de con un error. Medido en una instancia con la
variable desactivada, los tres modos devolvieron las mismas cinco páginas. Es una degradación
deliberada, pero significa que una consulta que parece funcionar no prueba que los embeddings
estén activos. `GET /api/system` informa de `semantic_search` si necesitas saberlo.

## No hay sintaxis de consulta

Se descarta todo carácter que no sea de palabra, y lo que queda se une como **términos de prefijo
obligatorios**. Esa sola frase explica todos los resultados de abajo, medidos contra una instancia
en marcha con una página sobre Kamailio y otra sobre Asterisk:

| Consulta | Resultado | Por qué |
| --- | --- | --- |
| `kamailio` | la página de Kamailio | término normal |
| `kam` | la página de Kamailio | cada término coincide como prefijo |
| `kamailio OR asterisk` | **nada** | `or` es una stopword inglesa y se descarta; los dos términos pasan a ser obligatorios, y ninguna página tiene los dos |
| `-asterisk kamailio` | **nada** | el `-` se descarta, así que el término que querías excluir pasa a ser obligatorio |
| `"asterisk queues"` | páginas con esas palabras separadas y en cualquier orden | las comillas se descartan; no hay búsqueda de frases |
| `the` | **nada** | una consulta hecha solo de stopwords se compila como una consulta vacía |
| `tag:voip` | **nada** | no es un filtro de campo; `tag` pasa a ser un término literal obligatorio |

Tres de ellas no devuelven ningún resultado aunque parece que deberían devolver algo, y una
devuelve lo contrario de lo que se pidió. Ninguna es un error, así que nada te avisa. Si una
consulta te sorprende, redúcela a palabras sueltas y vuelve a intentarlo.

Los acentos se pliegan en las dos direcciones. `renovacion` encuentra una página que contiene
«Renovación», y al revés también. Para eso existe la configuración de búsqueda de texto propia del
proyecto: `unaccent` se ejecuta antes del stemmer, así que las formas con y sin acento se indexan
como el mismo token.

El stemmer es el inglés en todas las instancias, incluidas aquellas cuyo contenido está en
español. Es una elección medida, no un descuido: un stemmer español obtuvo 0.00 en consultas en
inglés contra páginas en español en el banco de pruebas de recuperación de este proyecto. Los
números están en `evals/results/`.

## Qué se devuelve

Cada resultado lleva el slug y el título de la página y un fragmento de hasta doce palabras con
las partes coincidentes marcadas. El fragmento es prosa: antes se quitan el frontmatter, el código
delimitado y los bloques mermaid, las imágenes, las marcas de encabezado, las viñetas de lista,
las barras de tabla y el énfasis, y los enlaces y wikilinks conservan solo su texto. Eso ocurre
antes de elegir las palabras, así que un fragmento nunca sale de un bloque de código. La
ordenación no cambia: se hace sobre el markdown guardado, sintaxis incluida.

Añade `uploads=1` para buscar también en el texto reconocido en imágenes subidas. Eso necesita
`OCR_UPLOADS=1` en la instancia, porque el texto se extrae al subir la imagen y no al consultar.

## Cómo combina hybrid los dos

Hybrid no concatena las dos listas de resultados. Las fusiona por posición recíproca: cada lista
aporta `peso / (60 + posición)` a la puntuación de una página, con la lista vectorial más pesada
que la léxica. Las dos constantes salieron de un barrido sobre el corpus y el conjunto de
consultas del propio proyecto, registrado en `evals/results/`.

La consecuencia práctica es que una página bien situada por los dos métodos gana a una que es la
primera en uno y no aparece en el otro, que es el comportamiento que quieres cuando uno de los dos
tiene un mal día.

## El reranker está desactivado, y debe seguir así

`RERANK=1` vuelve a puntuar los primeros resultados con un cross-encoder. Sobre el corpus de este
proyecto se midió como una pérdida neta: ganó 0.01 en el rango recíproco medio, *perdió* recall en
la posición 1 y costó 29 veces la latencia mediana. Viene desactivado y
[Configuración](configuration.md) dice lo mismo. Actívalo solo si has medido tu propio corpus y
has visto lo contrario.

## Siguientes pasos

- [Tags y metadatos](tags-and-metadata.md), y por qué `tag:` no es un filtro
- [Configuración](configuration.md) para las variables de búsqueda y lo que cuestan
- [Agentes y MCP](mcp.md) para `sgrep` y las herramientas de recuperación
