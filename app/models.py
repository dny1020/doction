"""Tipos de datos del backend (dataclasses).

Antes, cada fila de la base de datos viajaba como un diccionario `sqlite3.Row`, así
que la *forma* de un usuario, una página o un workspace no estaba escrita en ningún
sitio y había que adivinarla. Aquí queda definida una sola vez.

Reglas para leer este archivo:
- Cada clase es un `@dataclass` simple: solo campos con su tipo, sin métodos.
- Algunas consultas SQL solo seleccionan unas pocas columnas. Por eso varios campos
  son opcionales (`= None`): una misma clase (p. ej. `Page`) puede venir "completa"
  o "a medias" según la función de `db.py` que la haya creado. El docstring de cada
  función de `db.py` dice qué campos rellena.
"""

from dataclasses import dataclass


@dataclass
class User:
    """Un usuario (tabla `users`)."""

    id: int
    email: str
    password_hash: str
    created_at: str
    display_name: str | None = None
    avatar_color: str | None = None
    # Versión de sesión: va como claim `ver` en el JWT; al cambiar la contraseña se
    # incrementa y todos los JWT anteriores (cookies o bearer) dejan de valer.
    token_version: int = 0


@dataclass
class Workspace:
    """Un espacio de trabajo (tabla `workspaces`).

    `role` solo viene cuando se lista para un usuario concreto (su rol en él);
    `user_id` y `created_at` solo en algunas consultas.
    """

    id: int
    slug: str
    name: str
    role: str | None = None
    user_id: int | None = None
    created_at: str | None = None


@dataclass
class Member:
    """Un miembro de un workspace (usuario + su rol)."""

    user_id: int
    email: str
    display_name: str | None
    role: str
    created_at: str


@dataclass
class ApiToken:
    """Un token de API (se muestra el hash una sola vez al crearlo)."""

    id: int
    name: str
    created_at: str
    last_used_at: str | None


@dataclass
class Page:
    """Una página de la wiki (tabla `pages`).

    La función `get_page` la devuelve completa, incluidos los
    campos extra de los JOIN (`parent_slug`, `updated_by_email`, …). Las listas
    cortas (papelera, exportación, subpáginas) rellenan solo unas columnas y dejan
    el resto en `None`.
    """

    id: int | None = None
    slug: str = ""
    title: str = ""
    content: str = ""
    user_id: int | None = None
    workspace_id: int | None = None
    parent_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    git_commit: str | None = None
    embed_dirty: int | None = None
    updated_by: int | None = None
    deleted_at: str | None = None
    # Columnas extra que añaden los JOIN de get_page:
    parent_slug: str | None = None
    parent_title: str | None = None
    updated_by_email: str | None = None
    updated_by_name: str | None = None


@dataclass
class PageNode:
    """Una página dentro del árbol de la barra lateral (`list_pages_tree`).

    `depth` es la profundidad para la indentación; no es una columna de la tabla.
    """

    slug: str
    title: str
    depth: int


@dataclass
class Webhook:
    """Un receptor de eventos de salida (`POST /api/webhooks`).

    `secret` no se devuelve nunca por la API: solo se muestra al crearlo, igual
    que un PAT. `events` vacío significa "todos".
    """

    id: int
    workspace_id: int
    url: str
    events: str
    active: bool
    created_at: str
    last_status: str | None
    last_attempt_at: str | None


@dataclass
class Delivery:
    """El resultado de intentar entregar un evento a un webhook.

    Una fila por evento, no por intento: el worker reintenta sobre la misma fila
    con backoff, así que `attempts` es cuántas veces se ha probado. El estado sale
    de las dos columnas juntas — `delivered_at` sin `last_error` es entregado, con
    `last_error` es que se agotaron los reintentos, y sin `delivered_at` sigue en
    cola.
    """

    id: int
    webhook_id: int
    event: str
    status: str  # delivered | failed | pending
    attempts: int
    last_error: str | None
    next_attempt_at: str
    delivered_at: str | None


@dataclass
class PendingDelivery:
    """Una entrega pendiente que el worker debe intentar."""

    id: int
    webhook_id: int
    url: str
    secret: str
    event: str
    payload_json: str
    attempts: int


@dataclass
class NoteRef:
    """Una nota en el feed cronológico (`list_notes`).

    Lleva `created_at` porque es el cursor de la paginación: el árbol de la
    barra lateral no sirve para captura rápida, que crece sin límite.
    """

    slug: str
    title: str
    created_at: str
    excerpt: str


@dataclass
class PageRef:
    """Una referencia ligera a una página (solo slug + título).

    Se usa para las migas de pan (ancestros) y para los backlinks.
    """

    slug: str
    title: str


@dataclass
class Mention:
    """Un backlink con la frase donde está escrito el enlace.

    Una lista de títulos dice quién apunta aquí; no dice si la referencia importa.
    El contexto viaja como tramos, igual que los fragmentos de búsqueda, para que
    el texto de una página no pueda meter markup en el renderizado de otra.
    """

    slug: str
    title: str
    context: list["SnippetPart"]


@dataclass
class RelatedPage:
    """Una página relacionada por etiquetas en común (`related_pages`)."""

    slug: str
    title: str
    shared_tags: int


@dataclass
class SnippetPart:
    """Un tramo de un fragmento de búsqueda; `match` marca lo que coincidió.

    El resaltado viaja como tramos y no como HTML: el cliente decide cómo pintar
    una coincidencia y el texto de la página nunca vuelve a entrar en el DOM como
    markup. Ver `db._split_snippet`.
    """

    text: str
    match: bool


@dataclass
class SearchHit:
    """Un resultado de la búsqueda de texto (`search_pages`).

    `snippet` es el fragmento en texto plano —sin ningún markup— y `parts` es el
    mismo fragmento partido en tramos para poder resaltar las coincidencias. Se
    mandan los dos porque quien solo quiere leer el fragmento (un agente por MCP,
    un `jq` sobre /api/search) sigue leyendo una cadena.
    """

    slug: str
    title: str
    snippet: str
    parts: list[SnippetPart]


@dataclass
class PageMeta:
    """Metadatos de una página: tipo, etiquetas y frontmatter (`get_page_meta`)."""

    slug: str
    type: str | None
    tags: list[str]
    frontmatter: dict


@dataclass
class ExtractedPage:
    """Página filtrada por tipo/etiqueta del frontmatter (`extract_pages`)."""

    slug: str
    title: str
    type: str | None
    tags: list[str]
    frontmatter: dict
    updated_at: str | None


@dataclass
class HistoryEntry:
    """Una versión (commit de git) de una página (`git_repo.get_page_history`)."""

    sha: str
    timestamp: str
    author: str
    message: str


@dataclass
class Chunk:
    """Un fragmento indexable y la cadena de encabezados que lo sitúa.

    `headings` va de fuera hacia dentro (`["Operaciones", "Renovación TLS"]`) y puede
    estar vacía: el preámbulo de una página, lo que va antes del primer encabezado,
    no cuelga de ninguno.
    """

    text: str
    headings: list[str]


@dataclass
class EmbedTarget:
    """Página pendiente de indexar para búsqueda semántica (`pages_to_embed`)."""

    id: int
    workspace_id: int
    title: str
    content: str


@dataclass
class ChunkVector:
    """Un trozo de página con su vector, para la búsqueda semántica.

    `path` es la cadena de encabezados dentro del documento, ya unida (`"Operaciones
    > Renovación TLS"`). Vacía para el preámbulo. La ruta completa que ve un agente
    —workspace, página, sección— se compone al leer, donde el workspace ya se conoce.
    """

    page_id: int
    ord: int
    text: str
    path: str
    vector: bytes
    slug: str
    title: str
    # Tipo y etiquetas de la página, para que un agente sepa si el pasaje viene de un
    # runbook o de un acta sin una segunda llamada. Se leen de page_meta/page_tags al
    # consultar, no se copian aquí: si alguien reetiqueta la página, el fragmento lo
    # refleja al instante en vez de esperar a un reindexado.
    page_type: str | None
    tags: list[str]


@dataclass
class UploadHit:
    """Un upload cuyo texto OCR coincide con la búsqueda (`search_uploads`)."""

    name: str
    snippet: str
    parts: list[SnippetPart]


@dataclass
class LinkEdge:
    """Una arista del grafo de wikilinks (`workspace_links`).

    `dst_slug` es el destino tal como se guardó (slugificado); puede no resolver
    a ninguna página existente (enlace roto).
    """

    src_page_id: int
    dst_slug: str
