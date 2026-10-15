---
source_sha256: eec6231c5518285482f4241e1d43745982aff2776f15179e401ea2db8585397f
---
# Configuración

Todo es una variable de entorno. No hay archivo de configuración ni interfaz de ajustes, así que
una instancia en marcha queda descrita por completo por su entorno más sus dos volúmenes.

## Obligatorias en producción

Las dos tienen valores por defecto que permiten arrancar el servidor, lo cual es cómodo en
desarrollo e incorrecto en cualquier otro sitio.

| Variable | Qué hace |
| --- | --- |
| `SECRET_KEY` | Firma las cookies de sesión y los JWT. Quien conozca la clave puede fabricar una sesión válida para cualquier usuario. Genérala con `openssl rand -hex 32`. |
| `DATABASE_URL` | Cadena de conexión a Postgres. Por defecto es `postgresql://doction:doction@postgres:5432/doction`, que es el nombre del servicio de Compose: fuera de Compose no se resolverá. |

Las dos interactúan, y la interacción es deliberada. Con `SECURE_COOKIES` desactivada, una
`SECRET_KEY` sin definir o con un valor de ejemplo recurre a una clave de desarrollo y registra un
aviso, así que un checkout local simplemente funciona. Con `SECURE_COOKIES=1` (la señal de que
estás detrás de TLS, en producción) el servidor **se niega a arrancar** con una clave sin definir.
Los valores de ejemplo de `.env.example` (`change-me`, `changeme`, `dev-secret-key`) cuentan como
sin definir, así que copiar el archivo de ejemplo y olvidarse de editarlo falla de forma ruidosa
en lugar de firmar tokens con una clave que es pública en GitHub.

## Muy recomendadas

| Variable | Por defecto | Qué hace |
| --- | --- | --- |
| `SECURE_COOKIES` | desactivada | Ponla a `1` cuando haya delante un proxy que termine el TLS. Marca la cookie de sesión como `Secure`, así que nunca se envía por HTTP plano. Dejarla desactivada en una instancia pública significa que la cookie de sesión viaja en claro en cualquier petición HTTP accidental. |
| `DISABLE_REGISTRATION` | desactivada | Ponla a `1` para cerrar el registro público. **El registro está abierto por defecto**: en una instancia accesible, cualquiera que encuentre la URL puede crear una cuenta. Con la variable activada, el primer usuario aún puede registrarse (así una instancia nueva nunca queda bloqueada) y todos los demás tienen que ser añadidos como miembros de un workspace por un propietario. |

## Cumplimiento de la licencia

| Variable | Por defecto | Qué hace |
| --- | --- | --- |
| `SOURCE_URL` | el repositorio de este proyecto | Dónde está el código fuente de esta instancia. Lo devuelve `GET /api/system` y se muestra a los usuarios con sesión iniciada en Configuración. |

doction es AGPL-3.0-only, y esa licencia vincula su obligación al *uso en red* y no a repartir
copias. Un operador que modificó doction y deja que otras personas lo usen les debe a esos
usuarios el código modificado. El software muestra la oferta para que no dependa de que el
operador se acuerde.

Tres casos, y no hay más:

| Qué estás haciendo | Qué defines |
| --- | --- |
| Ejecutar una versión publicada, sin modificar | Nada. El valor por defecto apunta al proyecto original, que es el código que ejecutas. |
| Modificado, instancia privada para ti o tu equipo | Nada. No se activa ninguna obligación. |
| Modificado, otras personas lo usan por una red | `SOURCE_URL` debe apuntar a *tu* código. |

Dejar el valor por defecto en una instancia modificada es peor que dejarlo vacío: la instancia
afirma con seguridad que el código que ejecuta está en una URL donde no está. El software no
puede verificar que una URL sirva el código correspondiente, así que esa parte sigue siendo
responsabilidad del operador.

## Almacenamiento

| Variable | Por defecto | Qué hace |
| --- | --- | --- |
| `DATA_DIR` | `/data` | El repositorio git de páginas markdown (`{DATA_DIR}/pages/`) y los archivos subidos. Es la mitad de tu copia de seguridad; la base de datos es la otra mitad. No tiene relación con `DATABASE_URL`. |
| `LOG_DIR` | `/logs` | Directorio del archivo de log rotado. Los logs también van a stdout. Solo para diagnóstico: no forma parte de una copia de seguridad. |
| `MODEL_DIR` | los modelos incluidos en la imagen | Dónde están los modelos ONNX de embeddings y del reranker. Cámbiala solo si montas los tuyos. |

Monta `DATA_DIR` y `LOG_DIR` como volúmenes separados. Compartir uno significa que la rotación de
logs y el historial de páginas compiten por el mismo espacio, y un disco lleno pierde entonces
escrituras de páginas.

## Logs

| Variable | Por defecto | Qué hace |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Nivel del logger raíz: `DEBUG`, `INFO`, `WARNING`, `ERROR`. `DEBUG` es el ajuste correcto al reportar un error. |

El logger raíz se configura al importar, antes de que exista ningún logger, porque uvicorn solo
configura sus propios loggers `uvicorn.*`. Sin eso se descartaría cada línea de `app.*`; por eso
`LOG_LEVEL` llega a los logs de la aplicación y no solo a los de acceso.

## Búsqueda

doction siempre tiene búsqueda de texto completo: una columna `tsvector` generada con un índice
GIN, que mantiene el propio Postgres. La búsqueda semántica va encima y es opcional.

| Variable | Por defecto | Qué hace |
| --- | --- | --- |
| `SEMANTIC_SEARCH` | desactivada | `1` activa los embeddings locales: las herramientas MCP `sgrep` y `rag`, y `mode=semantic` / `mode=hybrid` en `/api/search`. Un modelo ONNX MiniLM int8 (~23 MB) viene en la imagen y se carga bajo demanda. Un proceso en segundo plano calcula los embeddings de las páginas sin bloquear las peticiones. Con la variable desactivada, los modos semánticos vuelven a la búsqueda de texto completo en lugar de dar error. |
| `RERANK` | desactivada | `1` vuelve a puntuar los 20 primeros resultados semánticos con un cross-encoder local. Requiere `SEMANTIC_SEARCH=1`. **Déjala desactivada.** |

### Por qué el reranker viene desactivado

Medido contra una wiki real, no supuesto. Los números están en `evals/results/`.

| Métrica | Semántica | Con reranker |
| --- | --- | --- |
| MRR | 0.72 | 0.73 |
| recall@1 | 0.61 | 0.57 |
| latencia mediana | 12 ms | 350 ms |

Gana 0.01 de MRR, *pierde* recall@1 y cuesta 29 veces la latencia. Reserva 80–100 MB de RAM
adicional si aun así lo activas.

### Por qué el stemmer es el inglés

La búsqueda usa una configuración de búsqueda de texto de Postgres llamada `doction`: `unaccent`
encadenado antes de `english_stem`. El plegado de acentos es lo importante:
`to_tsvector('english', 'Renovación')` indexa el token con acento, así que una búsqueda de
`renovacion` antes no encontraba la página en absoluto.

El stemmer inglés es una medición, no una suposición: `spanish_stem` obtuvo 0.00 de MRR en
consultas en inglés contra páginas en español. También se midió un codificador multilingüe y se
descartó: seis veces más grande y *peor* en paráfrasis en español (0.30 frente a 0.44) y en
consultas conceptuales (0.15 frente a 0.57).

Si el rol de la base de datos no tiene permiso para `CREATE EXTENSION unaccent`, el servidor lo
registra en el log y recurre solo al stemmer en lugar de negarse a arrancar. Pierdes el plegado de
acentos y nada más.

## OCR de archivos subidos

| Variable | Por defecto | Qué hace |
| --- | --- | --- |
| `OCR_UPLOADS` | desactivada | `1` ejecuta el binario `tesseract` sobre las imágenes subidas e indexa el texto extraído, así que una captura de pantalla pegada se puede buscar. Se ejecuta como tarea en segundo plano; un fallo nunca rompe la subida. |
| `OCR_LANGS` | `eng+spa` | Paquetes de idioma de tesseract. Solo funcionan los paquetes presentes en la imagen. |

## Rara vez necesarias

| Variable | Por defecto | Qué hace |
| --- | --- | --- |
| `DOCTION_APP_PATH` | `/app` | Ruta base donde se sirve la aplicación de una sola página. Cambiarla cambia también el basename del router con el que se construyó el bundle, así que solo funciona si vuelves a construir el frontend para que coincida. |
| `TEST_DATABASE_URL` | sin definir | Solo para la batería de tests. Sin definir, `tests/conftest.py` arranca un contenedor Postgres desechable con su directorio de datos en tmpfs. La CI la define en su lugar. No la definas nunca en producción. |

## Un ejemplo completo

Entorno mínimo viable de producción, para una instancia de un solo usuario detrás de nginx:

```bash
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=postgresql://doction:<generada>@postgres:5432/doction
SECURE_COOKIES=1
DISABLE_REGISTRATION=1
SEMANTIC_SEARCH=1
LOG_LEVEL=INFO
```

`.env.example` en la raíz del repositorio es el punto de partida comentado.

## Verificar lo que está activo de verdad

El entorno que *defines* y la configuración que *tiene* el proceso son cosas distintas. Pregunta
al proceso:

```bash
curl -s $DOCTION/health | jq
# {"status":"ok","db":"ok","version":"0.31.3"}
```

`GET /api/system` (con autenticación) indica qué funciones opcionales quedaron activadas, que es
la respuesta honesta a «¿tuvo efecto de verdad `SEMANTIC_SEARCH=1`?».
