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

from __future__ import annotations

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

    Las funciones `get_page`/`latest_page` la devuelven completa, incluidos los
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
    # Columnas extra que añaden los JOIN de get_page/latest_page:
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
class PageRef:
    """Una referencia ligera a una página (solo slug + título).

    Se usa para las migas de pan (ancestros) y para los backlinks.
    """
    slug: str
    title: str


@dataclass
class RelatedPage:
    """Una página relacionada por etiquetas en común (`related_pages`)."""
    slug: str
    title: str
    shared_tags: int


@dataclass
class SearchHit:
    """Un resultado de la búsqueda de texto (`search_pages`).

    `snippet` es el fragmento con la coincidencia resaltada en <mark>…</mark>.
    """
    slug: str
    title: str
    snippet: str


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
class EmbedTarget:
    """Página pendiente de indexar para búsqueda semántica (`pages_to_embed`)."""
    id: int
    workspace_id: int
    content: str


@dataclass
class ChunkVector:
    """Un trozo de página con su vector, para la búsqueda semántica."""
    page_id: int
    ord: int
    text: str
    vector: bytes
    slug: str
    title: str
