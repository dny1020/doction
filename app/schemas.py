"""Response bodies of the REST API, declared so /openapi.json describes what comes back.

Each model forbids extra keys: a field a handler adds without declaring it fails the
response in the tests instead of vanishing from the output. Where a key is present only
sometimes, the route sets `response_model_exclude_unset`, so an absent key stays absent
rather than turning into a null.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Shared ───────────────────────────────────────────────────────────────────


class Ok(_Out):
    ok: bool


class SlugOk(_Out):
    slug: str
    ok: bool


class PageRef(_Out):
    slug: str
    title: str


class SnippetPart(_Out):
    """A span of text; `match` marks what the query matched."""

    text: str
    match: bool


# ── Auth and account ─────────────────────────────────────────────────────────


class Token(_Out):
    token: str
    token_type: str


class ApiTokenCreated(_Out):
    """The only response that carries the plaintext token."""

    id: int
    name: str
    token: str


class ApiToken(_Out):
    id: int
    name: str
    created_at: str
    last_used_at: str | None


class WorkspaceBrief(_Out):
    slug: str
    name: str
    role: str


class Me(_Out):
    email: str | None
    display_name: str | None
    avatar_color: str | None
    workspaces: list[WorkspaceBrief]
    active_workspace: WorkspaceBrief | None
    registration_open: bool


class Lang(_Out):
    lang: str


class Catalog(_Out):
    lang: str
    langs: list[str]
    t: dict[str, str]


# ── Workspaces ───────────────────────────────────────────────────────────────


class Workspace(_Out):
    id: int
    slug: str
    name: str
    role: str


class WorkspaceName(_Out):
    slug: str
    name: str


class Member(_Out):
    user_id: int
    email: str
    display_name: str | None
    role: str


class MemberAdded(_Out):
    workspace: str
    user_id: int
    role: str


# ── Webhooks ─────────────────────────────────────────────────────────────────


class Webhook(_Out):
    """`pending` and `failed` count deliveries; `last_status` covers the last attempt only."""

    id: int
    workspace_id: int
    url: str
    events: str
    active: bool
    created_at: str
    last_status: str | None
    last_attempt_at: str | None
    pending: int
    failed: int


class WebhookCreated(_Out):
    """The only response that carries the signing secret."""

    id: int
    url: str
    events: str
    secret: str


class Delivery(_Out):
    id: int
    webhook_id: int
    event: str
    status: str
    attempts: int
    last_error: str | None
    next_attempt_at: str
    delivered_at: str | None


# ── Pages ────────────────────────────────────────────────────────────────────


class PageNode(_Out):
    """A row of the sidebar tree, in depth-first order."""

    slug: str
    title: str
    depth: int


class Page(_Out):
    slug: str
    title: str
    content: str
    parent_slug: str | None
    children: list[PageRef]
    created_at: str | None
    updated_at: str | None


class PageCreated(_Out):
    slug: str
    title: str


class PageUpdated(_Out):
    slug: str
    title: str
    updated: bool


class PageMoved(_Out):
    slug: str
    parent_slug: str | None


class PageRenamed(_Out):
    slug: str
    previous_slug: str


class HistoryEntry(_Out):
    sha: str
    timestamp: str
    author: str
    message: str


class PageAtCommit(_Out):
    slug: str
    sha: str
    content: str


class PageDiff(_Out):
    slug: str
    sha: str
    diff: str


class Note(_Out):
    """`created_at` is the cursor for the next page of the feed (`before`)."""

    slug: str
    title: str
    created_at: str
    excerpt: str


class ViewChild(_Out):
    slug: str
    title: str
    updated_at: str | None


class Backlink(_Out):
    slug: str
    title: str
    context: list[SnippetPart]


class RelatedPage(_Out):
    slug: str
    title: str
    shared_tags: int


class PageView(_Out):
    slug: str
    title: str
    content: str
    parent_slug: str | None
    updated_at: str | None
    updated_by_email: str | None
    updated_by_name: str | None
    breadcrumbs: list[PageRef]
    children: list[ViewChild]
    backlinks: list[Backlink]
    related: list[RelatedPage]


class TrashItem(_Out):
    slug: str
    title: str
    deleted_at: str | None


# ── Search ───────────────────────────────────────────────────────────────────


class SearchHit(_Out):
    """A page. `keyword` returns the first four fields; `semantic` and `hybrid` add the
    scoring fields that explain the order."""

    slug: str
    title: str
    snippet: str
    parts: list[SnippetPart]
    score: float | None = None
    chunk: str | None = None
    ord: int | None = None
    section: str | None = None
    page_type: str | None = None
    tags: list[str] | None = None
    via: str | None = None
    rerank_score: float | None = None
    keyword_match: bool | None = None
    rrf: float | None = None
    lexical_rank: int | None = None
    vector_rank: int | None = None


class UploadHit(_Out):
    """Text recognised in an uploaded image, with `uploads=1`."""

    type: Literal["upload"]
    name: str
    url: str
    snippet: str
    parts: list[SnippetPart]


# ── Intelligence ─────────────────────────────────────────────────────────────


class LinkSuggestion(_Out):
    slug: str
    title: str
    # Cosine similarity; null under `title-match`, which has no score.
    score: float | None


class LinkSuggestions(_Out):
    slug: str
    mode: str
    suggestions: list[LinkSuggestion]


class TagSuggestion(_Out):
    tag: str
    score: float


class TagSuggestions(_Out):
    slug: str
    suggestions: list[TagSuggestion]


class Summary(_Out):
    slug: str
    mode: str
    summary: list[str]


class CentralPage(_Out):
    slug: str
    title: str
    score: float


class Hub(_Out):
    slug: str
    title: str
    outgoing: int


class Authority(_Out):
    slug: str
    title: str
    incoming: int


class BrokenLink(_Out):
    target: str
    sources: list[str]


class DuplicatePair(_Out):
    a: PageRef
    b: PageRef
    score: float


class Duplicates(_Out):
    mode: str
    pairs: list[DuplicatePair]


class TopicGroup(_Out):
    label: list[str]
    pages: list[PageRef]


class Clusters(_Out):
    mode: str
    groups: list[TopicGroup]


class Insights(_Out):
    pages: int
    links: int
    central: list[CentralPage]
    orphans: list[PageRef]
    hubs: list[Hub]
    authorities: list[Authority]
    broken_links: list[BrokenLink]
    duplicates: Duplicates
    clusters: Clusters


class GraphNode(_Out):
    slug: str
    title: str
    incoming: int
    outgoing: int
    orphan: bool


class GraphEdge(_Out):
    source: str
    target: str
    broken: bool


class Graph(_Out):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    pages: int
    truncated: bool


# ── System and uploads ───────────────────────────────────────────────────────


class System(_Out):
    """The index fields appear only with semantic search on and the database reachable."""

    version: str
    db: str
    license: str
    source_url: str
    semantic_search: bool
    rerank: bool
    ocr_uploads: bool
    rrf_k: int
    rrf_vector_weight: float
    search_min_score: float
    embedding_model: str | None = None
    indexed_pages: int | None = None
    pending_pages: int | None = None


class Health(_Out):
    status: str
    db: str
    version: str


class Upload(_Out):
    url: str


# ── MCP ──────────────────────────────────────────────────────────────────────


class JsonRpcError(_Out):
    code: int
    message: str


class JsonRpcResponse(BaseModel):
    """One JSON-RPC 2.0 response; a batch request gets a list of these. Not validated:
    `result` is whatever the called method returns, described in docs/mcp.md."""

    jsonrpc: Literal["2.0"]
    id: int | str | None
    result: dict | list | None = None
    error: JsonRpcError | None = None
