"""Backend data types.

Optional fields (`= None`) are the norm rather than the exception: a class such as
`Page` comes back complete from `get_page` and only half-filled from the short
listings. Each `db.py` function's docstring says which fields it populates.
"""

from dataclasses import dataclass


@dataclass
class User:
    id: int
    email: str
    password_hash: str
    created_at: str
    display_name: str | None = None
    avatar_color: str | None = None
    # Travels as the JWT `ver` claim; bumping it on a password change invalidates
    # every token issued before.
    token_version: int = 0


@dataclass
class Workspace:
    id: int
    slug: str
    name: str
    role: str | None = None
    user_id: int | None = None
    created_at: str | None = None


@dataclass
class Member:
    user_id: int
    email: str
    display_name: str | None
    role: str
    created_at: str


@dataclass
class ApiToken:
    id: int
    name: str
    created_at: str
    last_used_at: str | None


@dataclass
class Page:
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
    # Extra columns the get_page JOINs add.
    parent_slug: str | None = None
    parent_title: str | None = None
    updated_by_email: str | None = None
    updated_by_name: str | None = None


@dataclass
class PageNode:
    """A page in the sidebar tree; `depth` is for indentation, not a column."""

    slug: str
    title: str
    depth: int


@dataclass
class Webhook:
    """`secret` is shown once at creation and never returned again; empty `events` means all."""

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
    """One row per event, not per attempt: the worker retries in place with backoff."""

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
    id: int
    webhook_id: int
    url: str
    secret: str
    event: str
    payload_json: str
    attempts: int


@dataclass
class NoteRef:
    """`created_at` is the pagination cursor for the note feed."""

    slug: str
    title: str
    created_at: str
    excerpt: str


@dataclass
class PageRef:
    slug: str
    title: str


@dataclass
class Mention:
    """A backlink plus the sentence the link sits in."""

    slug: str
    title: str
    context: list["SnippetPart"]


@dataclass
class RelatedPage:
    slug: str
    title: str
    shared_tags: int


@dataclass
class SnippetPart:
    """A span of a search snippet; `match` marks what matched.

    Highlighting travels as spans rather than HTML so page text never re-enters the
    DOM as markup. See `db._split_snippet`.
    """

    text: str
    match: bool


@dataclass
class SearchHit:
    """`snippet` is the plain text and `parts` the same text split for highlighting."""

    slug: str
    title: str
    snippet: str
    parts: list[SnippetPart]


@dataclass
class PageMeta:
    slug: str
    type: str | None
    tags: list[str]
    frontmatter: dict


@dataclass
class ExtractedPage:
    slug: str
    title: str
    type: str | None
    tags: list[str]
    frontmatter: dict
    updated_at: str | None


@dataclass
class HistoryEntry:
    sha: str
    timestamp: str
    author: str
    message: str


@dataclass
class Chunk:
    """`headings` runs outermost first, and is empty for a page's preamble."""

    text: str
    headings: list[str]


@dataclass
class EmbedTarget:
    id: int
    workspace_id: int
    title: str
    content: str


@dataclass
class ChunkVector:
    """`path` is the joined heading chain (`"Operations > TLS renewal"`), empty for the preamble."""

    page_id: int
    ord: int
    text: str
    path: str
    vector: bytes
    slug: str
    title: str
    # Read from page_meta/page_tags at query time, not copied here: retagging a page
    # shows up immediately instead of waiting for a reindex.
    page_type: str | None
    tags: list[str]


@dataclass
class UploadHit:
    name: str
    snippet: str
    parts: list[SnippetPart]


@dataclass
class LinkEdge:
    """`dst_slug` is stored as written and may resolve to nothing (a broken link)."""

    src_page_id: int
    dst_slug: str
