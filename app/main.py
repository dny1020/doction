import asyncio
import dataclasses
import hashlib
import io
import logging
import os
import re
import secrets
import zipfile
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from fastapi import APIRouter, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.status import HTTP_303_SEE_OTHER

from app import db, embeddings, git_repo, graph, i18n, mcp, meta, ocr, seed, suggest, webhooks
from app.auth import (
    TOKEN_PREFIX,
    generate_api_token,
    hash_api_token,
)
from app.auth import hash_password as _hash_password
from app.auth import verify_password as _verify_password
from app.avatar import normalize_color
from app.logging_config import configure_logging
from app.models import Workspace
from app.version import LICENSE_ID, VERSION

configure_logging()
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
SESSION_MAX_AGE = 60 * 60 * 24 * 7
WORKSPACE_MAX_AGE = 60 * 60 * 24 * 30
LANG_MAX_AGE = 60 * 60 * 24 * 365
# Only behind TLS; off by default so http dev needs no configuration.
SECURE_COOKIES = os.environ.get("SECURE_COOKIES", "").lower() in {"1", "true", "yes"}
# Closes web registration on public instances. The first user can always be created, or
# the instance would be unreachable; the rest go through scripts/create_user.py.
DISABLE_REGISTRATION = os.environ.get("DISABLE_REGISTRATION", "").lower() in {"1", "true", "yes"}

# AGPL-3.0 §13: anyone using the instance over a network is owed the corresponding source.
# Configurable because an operator who modifies doction owes their changes to *their* users;
# a fixed upstream URL would leave a modified fork believing it complied.
SOURCE_URL = os.environ.get("SOURCE_URL", "").strip() or "https://github.com/dny1020/doction"

# Security headers set on every response, as defence in depth. 'unsafe-inline' in
# script-src is still needed by the inline theme script in frontend/index.html, which
# applies light or dark before the first paint.
_CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": _CSP,
}

# Images embeddable in documents, validated by content-type *and* magic bytes.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_IMAGE_SIGNATURES = {
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/gif": (b"GIF8", ".gif"),
}


def _image_extension(content_type: str | None, data: bytes) -> str | None:
    """The extension when content-type and magic bytes agree, otherwise None."""
    sig = _IMAGE_SIGNATURES.get(content_type or "")
    if sig is not None and data.startswith(sig[0]):
        return sig[1]
    if content_type == "image/webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


# ── REST API ─────────────────────────────────────────────────────────────────

# PBKDF2 processes whatever it is given, so without a cap a megabyte-long password
# would be free CPU for an attacker.
_MAX_PASSWORD_LEN = 256


class _TokenIn(BaseModel):
    email: str
    password: str = Field(max_length=_MAX_PASSWORD_LEN)


class _PageIn(BaseModel):
    # Optional: a one-line capture should not force a title. db.create_page derives
    # one from the first line of the content.
    title: str = ""
    content: str = ""
    parent_slug: str | None = None
    slug: str | None = None


class _WebhookIn(BaseModel):
    url: str
    # Empty means all events; otherwise a comma-separated list:
    # page.created, page.updated, page.deleted, page.moved, page.renamed
    events: str = ""


class _MoveIn(BaseModel):
    parent_slug: str | None = None


class _RenameIn(BaseModel):
    slug: str


class _PagePatch(BaseModel):
    title: str | None = None
    content: str | None = None


class _WorkspaceIn(BaseModel):
    name: str


class _ApiTokenIn(BaseModel):
    name: str = "token"


class _MemberIn(BaseModel):
    email: str
    role: str = "member"


api_router = APIRouter(prefix="/api")


def _api_user(request: Request) -> int:
    uid = getattr(request.state, "user_id", None)
    if uid is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return int(uid)


def _api_workspace(request: Request, user_id: int) -> int:
    if getattr(request.state, "workspace_denied", False):
        # Existing but not yours answers the same as not existing: a 403 would say
        # the workspace is there.
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws = getattr(request.state, "workspace", None)
    if ws is None:
        ws = db.ensure_default_workspace(user_id)
    return int(ws.id)


# Levels the response time when the email does not exist: without it, the missing
# ~100ms of PBKDF2 tells an attacker which emails are registered.
_DUMMY_PASSWORD_HASH = _hash_password("doction-timing-dummy")


def _authenticate(request: Request, email: str, password: str):
    """Email and password to User, rate-limited per (ip, email).

    Shared by the SPA login and POST /api/token, which would otherwise be unguarded.
    """
    email = email.strip().lower()
    ip = request.client.host if request.client else "?"
    key = f"{ip}:{email}"
    if _login_too_many(key):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    user = db.get_user_by_email(email)
    if user is None:
        _verify_password(password, _DUMMY_PASSWORD_HASH)
    if user is None or not _verify_password(password, user.password_hash):
        _login_record_failure(key)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    _login_clear(key)
    return user


@api_router.post("/token", tags=["auth"])
def api_token(request: Request, body: _TokenIn):
    user = _authenticate(request, body.email, body.password)
    return {
        "token": _encode_token(int(user.id), user.token_version),
        "token_type": "bearer",
    }


@api_router.post("/tokens", status_code=201, tags=["auth"])
def api_create_token(request: Request, body: _ApiTokenIn):
    uid = _api_user(request)
    token = generate_api_token()
    token_id = db.create_api_token(uid, body.name, hash_api_token(token))
    # The plaintext is returned once and never stored.
    return {"id": token_id, "name": body.name.strip() or "token", "token": token}


@api_router.get("/tokens", tags=["auth"])
def api_list_tokens(request: Request):
    uid = _api_user(request)
    return [dataclasses.asdict(t) for t in db.list_api_tokens(uid)]


@api_router.get("/webhooks", tags=["webhooks"])
def api_list_webhooks(request: Request):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    # Pending and failed counts ride along so a webhook that is not delivering shows
    # up without opening it: `last_status` covers only the last attempt.
    counts = db.delivery_counts(wid)
    hooks = []
    for hook in db.list_webhooks(wid):
        row = dataclasses.asdict(hook)
        row.update(counts.get(hook.id, {"pending": 0, "failed": 0}))
        hooks.append(row)
    return hooks


@api_router.get("/webhooks/{webhook_id}/deliveries", tags=["webhooks"])
def api_webhook_deliveries(request: Request, webhook_id: int):
    """What this webhook has delivered and what it has not. Read-only: looking is not a retry."""
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    if not any(hook.id == webhook_id for hook in db.list_webhooks(wid)):
        raise HTTPException(status_code=404, detail="Webhook not found")
    return [dataclasses.asdict(d) for d in db.list_deliveries(webhook_id)]


@api_router.post("/webhooks", status_code=201, tags=["webhooks"])
def api_create_webhook(request: Request, body: _WebhookIn):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must be http(s)")
    secret = secrets.token_hex(24)
    hook_id = db.create_webhook(wid, url, secret, body.events.strip())
    # Shown once and never returned again, like a PAT. The receiver needs it to verify
    # the X-Doction-Signature header.
    return {"id": hook_id, "url": url, "events": body.events.strip(), "secret": secret}


@api_router.delete("/webhooks/{webhook_id}", status_code=204, tags=["webhooks"])
def api_delete_webhook(request: Request, webhook_id: int):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    if not db.delete_webhook(wid, webhook_id):
        raise HTTPException(status_code=404, detail="Webhook not found")


@api_router.delete("/tokens/{token_id}", status_code=204, tags=["auth"])
def api_revoke_token(request: Request, token_id: int):
    uid = _api_user(request)
    if not db.revoke_api_token(uid, token_id):
        raise HTTPException(status_code=404, detail="Token not found")


@api_router.get("/workspaces", tags=["workspaces"])
def api_list_workspaces(request: Request):
    uid = _api_user(request)
    # Built by hand to return only these fields, not user_id and the rest.
    return [
        {"id": w.id, "slug": w.slug, "name": w.name, "role": w.role}
        for w in db.list_workspaces(uid)
    ]


@api_router.post("/workspaces", status_code=201, tags=["workspaces"])
def api_create_workspace(request: Request, body: _WorkspaceIn):
    uid = _api_user(request)
    slug = db.create_workspace(uid, body.name)
    return {"slug": slug, "name": body.name.strip() or "Workspace"}


def _api_owned_workspace(uid: int, slug: str) -> Workspace:
    """Resolve a workspace by slug, requiring the user to be its owner."""
    ws = db.get_workspace_by_slug(uid, slug)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.role != "owner":
        raise HTTPException(status_code=403, detail="Owner role required")
    return ws


@api_router.put("/workspaces/{slug}", tags=["workspaces"])
def api_rename_workspace(request: Request, slug: str, body: _WorkspaceIn):
    uid = _api_user(request)
    _api_owned_workspace(uid, slug)  # exige ser owner
    if not db.rename_workspace(uid, slug, body.name):
        raise HTTPException(status_code=400, detail="Enter a valid name")
    return {"slug": slug, "name": body.name.strip()}


@api_router.delete("/workspaces/{slug}", tags=["workspaces"])
def api_delete_workspace(request: Request, slug: str) -> Response:
    uid = _api_user(request)
    _api_owned_workspace(uid, slug)  # owner only
    if not db.delete_workspace(uid, slug):
        raise HTTPException(status_code=400, detail="Cannot delete your only workspace")
    response = JSONResponse({"slug": slug, "ok": True})
    # If the active workspace was deleted, point the cookie at one that remains.
    if request.cookies.get("workspace") == slug:
        remaining = db.list_workspaces(uid)
        if remaining:
            _ws_cookie(response, remaining[0].slug)
    return response


@api_router.get("/workspaces/{slug}/members", tags=["workspaces"])
def api_list_members(request: Request, slug: str):
    uid = _api_user(request)
    ws = db.get_workspace_by_slug(uid, slug)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return [
        {
            "user_id": m.user_id,
            "email": m.email,
            "display_name": m.display_name,
            "role": m.role,
        }
        for m in db.list_workspace_members(int(ws.id))
    ]


@api_router.post("/workspaces/{slug}/members", status_code=201, tags=["workspaces"])
def api_add_member(request: Request, slug: str, body: _MemberIn):
    uid = _api_user(request)
    ws = _api_owned_workspace(uid, slug)
    target = db.get_user_by_email(body.email.strip().lower())
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if db.get_member_role(int(target.id), int(ws.id)) is not None:
        raise HTTPException(status_code=409, detail="Already a member")
    db.add_workspace_member(int(ws.id), int(target.id), "member")
    return {"workspace": slug, "user_id": int(target.id), "role": "member"}


@api_router.delete("/workspaces/{slug}/members/{member_id}", status_code=204, tags=["workspaces"])
def api_remove_member(request: Request, slug: str, member_id: int):
    uid = _api_user(request)
    ws = _api_owned_workspace(uid, slug)
    if db.get_member_role(member_id, int(ws.id)) == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the owner")
    if not db.remove_workspace_member(int(ws.id), member_id):
        raise HTTPException(status_code=404, detail="Member not found")


@api_router.get("/workspaces/{slug}/export", tags=["workspaces"])
def api_export_workspace(request: Request, slug: str) -> Response:
    """Downloads the workspace as a zip of markdown files, one .md per page."""
    uid = _api_user(request)
    ws = db.get_workspace_by_slug(uid, slug)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for page in db.pages_for_export(int(ws.id)):
            zf.writestr(f"{slug}/{page.slug}.md", page.content)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}.zip"'},
    )


@api_router.get("/pages", tags=["pages"])
def api_list_pages(request: Request):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    return db.list_pages_tree(wid)


@api_router.post("/pages", status_code=201, tags=["pages"])
def api_create_page(request: Request, body: _PageIn):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    try:
        slug = db.create_page(
            uid,
            wid,
            body.title,
            body.content,
            parent_slug=body.parent_slug,
            requested_slug=body.slug,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    page = db.get_page(slug, wid)
    title = page.title if page else body.title
    _commit_page(request, wid, slug, title, body.content)
    return {"slug": slug, "title": title}


@api_router.get("/pages/{slug}/history", tags=["pages"])
def api_page_history(request: Request, slug: str, limit: int = 50):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return git_repo.get_page_history(_workspace_slug(request, wid), slug, limit=limit)


@api_router.get("/pages/{slug}/history/{sha}", tags=["pages"])
def api_page_at_commit(request: Request, slug: str, sha: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    content = git_repo.get_page_at_commit(_workspace_slug(request, wid), slug, sha)
    if content is None:
        raise HTTPException(status_code=404, detail="Commit not found")
    return {"slug": slug, "sha": sha, "content": content}


@api_router.get("/pages/{slug}/history/{sha}/diff", tags=["pages"])
def api_page_diff(request: Request, slug: str, sha: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    diff = git_repo.diff_page(_workspace_slug(request, wid), slug, sha)
    if diff is None:
        raise HTTPException(status_code=404, detail="Commit not found")
    return {"slug": slug, "sha": sha, "diff": diff}


@api_router.get("/pages/{slug}/raw", response_class=PlainTextResponse, tags=["pages"])
def api_get_page_raw(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page.content


@api_router.get("/pages/{slug}", tags=["pages"])
def api_get_page(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    children = db.list_child_pages(wid, int(page.id or 0))
    return {
        "slug": page.slug,
        "title": page.title,
        "content": page.content,
        "parent_slug": page.parent_slug,
        "children": [{"slug": c.slug, "title": c.title} for c in children],
        "created_at": page.created_at,
        "updated_at": page.updated_at,
    }


@api_router.put("/pages/{slug}", tags=["pages"])
def api_update_page(request: Request, slug: str, body: _PagePatch):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    new_title = body.title if body.title is not None else page.title
    new_content = body.content if body.content is not None else page.content
    try:
        db.update_page(uid, wid, slug, new_title, new_content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _commit_page(request, wid, slug, new_title, new_content)
    return {"slug": slug, "title": new_title, "updated": True}


@api_router.post("/pages/{slug}/move", tags=["pages"])
def api_move_page(request: Request, slug: str, body: _MoveIn):
    """Reparents a page. Cheap: the git repo is flat, so no file moves."""
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    try:
        moved = db.move_page(wid, slug, body.parent_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if moved is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"slug": moved, "parent_slug": body.parent_slug}


@api_router.post("/pages/{slug}/rename", tags=["pages"])
def api_rename_page(request: Request, slug: str, body: _RenameIn):
    """Changes the slug, leaving an alias for the old one so [[wikilinks]] keep resolving."""
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    try:
        renamed = db.rename_page(wid, slug, body.slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if renamed is None:
        raise HTTPException(status_code=404, detail="Page not found")
    if renamed != slug:
        author = getattr(request.state, "user_email", None) or "user"
        git_repo.rename_page_file(_workspace_slug(request, wid), slug, renamed, author)
    return {"slug": renamed, "previous_slug": slug}


@api_router.get("/pages/{slug}/children", tags=["pages"])
def api_page_children(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    children = db.list_children(wid, slug)
    if children is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return children


@api_router.delete("/pages/{slug}", status_code=204, tags=["pages"])
def api_delete_page(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    if not db.delete_page(wid, slug):
        raise HTTPException(status_code=404, detail="Page not found")


@api_router.get("/pages/{slug}/suggest-links", tags=["intelligence"])
def api_suggest_links(request: Request, slug: str):
    """Candidate wikilinks: related pages, by embeddings or title mentions, that this
    page does not link to yet."""
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    result = suggest.suggest_links(wid, slug)
    if result is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return result


@api_router.get("/pages/{slug}/suggest-tags", tags=["intelligence"])
def api_suggest_tags(request: Request, slug: str):
    """Candidate tags, by TF-IDF against the rest of the workspace."""
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    result = suggest.suggest_tags(wid, slug)
    if result is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return result


@api_router.get("/pages/{slug}/summary", tags=["intelligence"])
def api_page_summary(request: Request, slug: str, k: int = 3):
    """Extractive summary (TextRank) of the page; `lead` when semantic search is off."""
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    k = max(1, min(k, 10))
    return {"slug": slug, **suggest.summarize(page.content, k=k)}


@api_router.get("/insights", tags=["intelligence"])
def api_insights(request: Request):
    """Workspace health: the wikilink graph plus duplicates and semantic clusters."""
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    return suggest.workspace_insights(wid)


@api_router.get("/graph", tags=["intelligence"])
def api_graph(request: Request):
    """Nodes and edges of the wikilink graph, ready to draw.

    Separate from `/insights`, which summarises: there the question is the workspace's
    health and here it is its shape. The workspace comes from the request context as in
    the rest of the API, not from the path.
    """
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    return graph.workspace_graph(wid)


@api_router.get("/system", tags=["system"])
def api_system(request: Request):
    """What this deployment is running: version, database and retrieval.

    Read-only. The flags come from the process environment, so a form that appeared to
    change them would be lying: there is no way to rewrite that file and restart. It
    exists because until now there was no way to tell which search mode a server was in
    except by looking at the shape of its results.

    Separate from /health, which is anonymous and is what the container healthcheck uses.
    """
    uid = _api_user(request)
    wid = _api_workspace(request, uid)

    try:
        with db.connect() as conn:
            conn.execute("SELECT 1")
        db_state = "ok"
    except Exception:
        logger.exception("system report: base de datos inalcanzable")
        db_state = "unreachable"

    semantic = embeddings.semantic_enabled()
    report = {
        "version": VERSION,
        "db": db_state,
        # The AGPL obligation is the instance's, not the repository's: a network user
        # has to be able to reach the source from the application itself.
        "license": LICENSE_ID,
        "source_url": SOURCE_URL,
        "semantic_search": semantic,
        "rerank": embeddings.rerank_enabled(),
        "ocr_uploads": ocr.ocr_enabled(),
        # The constants that decide every hybrid result's order. Reported even with
        # semantics off: they are process configuration, not an index counter.
        "rrf_k": embeddings.RRF_K,
        "rrf_vector_weight": embeddings.RRF_VECTOR_WEIGHT,
        "search_min_score": embeddings.SEARCH_MIN_SCORE,
    }
    if semantic and db_state == "ok":
        # current_model_name() reads a class attribute, so reporting never loads the
        # model. The counters only appear with semantics on: a 0 with it off would be
        # indistinguishable from a broken index.
        model = embeddings.current_model_name()
        total, indexed = db.index_counts(wid, model, meta.CHUNKER_ID)
        report["embedding_model"] = model
        report["indexed_pages"] = indexed
        report["pending_pages"] = total - indexed
    return report


@api_router.get("/notes", tags=["pages"])
def api_notes(request: Request, limit: int = 50, before: str | None = None):
    """Chronological feed of quick captures (`type: memo`), paginated by cursor.

    Deliberately separate from the tree: list_pages_tree does not paginate and quick
    capture grows without bound.
    """
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    return db.list_notes(wid, limit=limit, before=before)


@api_router.get("/search", tags=["search"])
def api_search(request: Request, q: str = "", mode: str = "keyword", uploads: bool = False):
    """Workspace search: `keyword` (FTS), `semantic` (embeddings) or `hybrid`.

    `uploads=1` also matches text recognised in uploaded images (items with
    `type: "upload"`). Opt-in, so clients that expect only pages keep working."""
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    results = embeddings.search(wid, q, mode=mode)
    if uploads:
        results += [
            {
                "type": "upload",
                "name": h.name,
                "url": f"/uploads/{h.name}",
                "snippet": h.snippet,
                "parts": h.parts,
            }
            for h in db.search_uploads(wid, q)
        ]
    return results


# ── SPA bootstrap and JSON auth ──────────────────────────────────────────────
# Same httponly session cookie as REST and MCP; the SPA calls with
# `fetch(..., {credentials: 'same-origin'})`, so the cookie travels on its own.


def _workspace_brief(ws) -> dict:
    return {"slug": ws.slug, "name": ws.name, "role": ws.role}


def _me_payload(user_id: int, active_slug: str | None) -> dict:
    """The current user and their workspaces, for the SPA to start from."""
    user = db.get_user_by_id(user_id)
    workspaces = db.list_workspaces(user_id)
    active = None
    for w in workspaces:
        if w.slug == active_slug:
            active = w
    if active is None and workspaces:
        active = workspaces[0]
    return {
        "email": user.email if user else None,
        "display_name": user.display_name if user else None,
        "avatar_color": user.avatar_color if user else None,
        "workspaces": [_workspace_brief(w) for w in workspaces],
        "active_workspace": _workspace_brief(active) if active else None,
        "registration_open": _registration_open(),
    }


@api_router.get("/me", tags=["account"])
def api_me(request: Request):
    user_id = _api_user(request)
    active = getattr(request.state, "workspace", None)
    return _me_payload(user_id, active.slug if active else None)


@api_router.post("/auth/login", tags=["auth"])
def api_login(request: Request, body: _TokenIn) -> Response:
    user = _authenticate(request, body.email, body.password)
    user_id = int(user.id)
    workspace = db.ensure_default_workspace(user_id)
    response = JSONResponse(_me_payload(user_id, workspace.slug))
    _issue_session(response, user_id, workspace.slug, user.token_version)
    return response


@api_router.post("/auth/register", status_code=201, tags=["auth"])
def api_register(body: _TokenIn) -> Response:
    email = body.email.strip().lower()
    if not _registration_open():
        raise HTTPException(status_code=403, detail="Registration is closed")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if db.get_user_by_email(email) is not None:
        raise HTTPException(status_code=409, detail="That email is already registered")
    first_user = not db.has_users()
    user_id = db.create_user(email, _hash_password(body.password))
    workspace = db.ensure_default_workspace(user_id)
    workspace_id = int(workspace.id)
    if first_user:
        db.claim_unowned_pages(user_id, workspace_id)
    for title, content in seed.SEED_PAGES:
        db.create_page(user_id, workspace_id, title, content)
    response = JSONResponse(_me_payload(user_id, workspace.slug), status_code=201)
    _issue_session(response, user_id, workspace.slug)
    return response


@api_router.post("/auth/logout", tags=["auth"])
def api_logout() -> Response:
    response = JSONResponse({"ok": True})
    response.delete_cookie("session")
    response.delete_cookie("workspace")
    return response


@api_router.get("/i18n", tags=["system"])
def api_i18n(request: Request):
    """Translation catalogue for the active language, for the SPA. Public, login included."""
    lang = _lang(request)
    return {"lang": lang, "langs": list(i18n.LANGS), "t": i18n.get_catalog(lang)}


@api_router.post("/lang/{code}", tags=["account"])
def api_set_lang(code: str) -> Response:
    """Switches the SPA's language by setting the `lang` cookie."""
    if code not in i18n.LANGS:
        raise HTTPException(status_code=400, detail="Unsupported language")
    response = JSONResponse({"lang": code})
    _lang_cookie(response, code)
    return response


@api_router.post("/workspaces/{slug}/switch", tags=["workspaces"])
def api_switch_workspace(request: Request, slug: str) -> Response:
    uid = _api_user(request)
    ws = db.get_workspace_by_slug(uid, slug)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    response = JSONResponse(_workspace_brief(ws))
    _ws_cookie(response, ws.slug)
    return response


@api_router.get("/pages/{slug}/view", tags=["pages"])
def api_page_view(request: Request, slug: str):
    """Everything the SPA's reading view needs, in one call."""
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    # `or 0`: get_page always fills id, but the dataclass declares it optional.
    breadcrumbs = db.get_ancestors(int(page.id or 0), wid)
    children = db.list_child_pages(wid, int(page.id or 0))
    related = db.related_pages(wid, slug) or []
    return {
        "slug": page.slug,
        "title": page.title,
        "content": page.content,
        "parent_slug": page.parent_slug,
        "updated_at": page.updated_at,
        "updated_by_email": page.updated_by_email,
        "updated_by_name": page.updated_by_name,
        "breadcrumbs": [{"slug": c.slug, "title": c.title} for c in breadcrumbs],
        "children": [
            {"slug": c.slug, "title": c.title, "updated_at": c.updated_at} for c in children
        ],
        # Each mention carries its sentence as spans, so one page's text never
        # re-enters another's DOM as markup.
        "backlinks": [
            {
                "slug": m.slug,
                "title": m.title,
                "context": [{"text": part.text, "match": part.match} for part in m.context],
            }
            for m in db.mentions(wid, slug)
        ],
        "related": [
            {"slug": r.slug, "title": r.title, "shared_tags": r.shared_tags} for r in related
        ],
    }


# ── Settings, trash and version restore ──────────────────────────────────────


class _ProfileIn(BaseModel):
    display_name: str = ""
    avatar_color: str = ""


class _PasswordIn(BaseModel):
    current_password: str = Field(max_length=_MAX_PASSWORD_LEN)
    new_password: str = Field(max_length=_MAX_PASSWORD_LEN)
    confirm_password: str = Field(max_length=_MAX_PASSWORD_LEN)


@api_router.post("/settings/profile", tags=["account"])
def api_update_profile(request: Request, body: _ProfileIn):
    uid = _api_user(request)
    name = body.display_name.strip()[:40]
    color = normalize_color(body.avatar_color)
    db.update_user_profile(uid, name or None, color)
    active = getattr(request.state, "workspace", None)
    return _me_payload(uid, active.slug if active else None)


@api_router.post("/settings/password", tags=["account"])
def api_update_password(request: Request, body: _PasswordIn):
    uid = _api_user(request)
    user = db.get_user_by_id(uid)
    if user is None or not _verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")
    new_version = db.update_user_password(uid, _hash_password(body.new_password))
    # The token_version bump invalidates every JWT, so this tab's session is reissued
    # rather than logging out whoever just changed their password.
    response = JSONResponse({"ok": True})
    _issue_session(response, uid, token_version=new_version)
    return response


@api_router.get("/trash", tags=["pages"])
def api_trash(request: Request):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    return [
        {"slug": p.slug, "title": p.title, "deleted_at": p.deleted_at}
        for p in db.list_deleted_pages(wid)
    ]


@api_router.post("/trash/{slug}/restore", tags=["pages"])
def api_trash_restore(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    if not db.restore_page(wid, slug):
        raise HTTPException(status_code=404, detail="Page not found in trash")
    return {"slug": slug, "ok": True}


@api_router.post("/trash/{slug}/purge", status_code=204, tags=["pages"])
def api_trash_purge(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    if not db.purge_page(wid, slug):
        raise HTTPException(status_code=404, detail="Page not found in trash")


@api_router.post("/pages/{slug}/restore/{sha}", tags=["pages"])
def api_restore_version(request: Request, slug: str, sha: str):
    """Restores the content of an older version (a git commit) as a new version."""
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    ws_slug = _workspace_slug(request, wid)
    content = git_repo.get_page_at_commit(ws_slug, slug, sha)
    if content is None:
        raise HTTPException(status_code=404, detail="Version not found")
    title = page.title
    new_slug = db.update_page(uid, wid, slug, title, content)
    effective_slug = new_slug or slug
    author = getattr(request.state, "user_email", None) or "user"
    new_sha = git_repo.commit_page(
        ws_slug, effective_slug, content, author, f"Restore {sha}: {title}"
    )
    if new_sha:
        db.set_page_git_commit(wid, effective_slug, new_sha)
    return {"slug": effective_slug, "ok": True}


def _workspace_slug(request: Request, wid: int) -> str:
    """The active workspace's slug, which is also its directory name in git."""
    ws = getattr(request.state, "workspace", None)
    if ws is not None and int(ws.id) == wid:
        return ws.slug
    ws = db.get_workspace_by_id(wid)
    return ws.slug if ws else "default"


def _commit_page(request: Request, wid: int, slug: str, title: str, content: str) -> None:
    author = getattr(request.state, "user_email", None) or "user"
    git_repo.commit_and_record(wid, _workspace_slug(request, wid), slug, title, content, author)


@asynccontextmanager
async def lifespan(_: FastAPI):
    secret_key = os.environ.get("SECRET_KEY")
    # Known placeholders count as unset: an example compose with `change-me` would
    # sign JWTs with a key everyone has.
    if not secret_key or secret_key in {"change-me", "changeme", "dev-secret-key"}:
        if SECURE_COOKIES:
            # SECURE_COOKIES=1 means production behind TLS.
            raise RuntimeError(
                "SECRET_KEY must be set to a real secret when SECURE_COOKIES is enabled — "
                "refusing to start with an insecure default/placeholder in production"
            )
        secret_key = "dev-secret-key"
        logger.warning("SECRET_KEY not set — using insecure dev default, do not use in production")
    app.state.secret_key = secret_key
    db.init_db()
    git_repo.ensure_repo()
    logger.info("doction ready — db: %s", db.masked_database_url())

    embed_task: asyncio.Task | None = None
    if embeddings.semantic_enabled():
        embed_task = asyncio.create_task(embeddings.enrichment_worker())
        logger.info("semantic search ON — embedding worker running")

    # Unconditional: with no webhooks registered the query returns nothing and the
    # worker sleeps. One more flag would be one more way to lose events silently.
    webhook_task = asyncio.create_task(webhooks.delivery_worker())

    yield

    webhook_task.cancel()
    try:
        await webhook_task
    except asyncio.CancelledError:
        pass

    if embed_task is not None:
        embed_task.cancel()
        try:
            await embed_task
        except asyncio.CancelledError:
            # Cancelling the task raises this on purpose.
            pass
    db.reset_pool()


# Same version /health reports and the image is tagged with. Without it FastAPI declares 0.1.0
# in /openapi.json, and a reference announcing a version the server never reports leaves the
# reader unable to tell which of the two numbers is the software they are talking to.
app = FastAPI(title="doction", version=VERSION, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Uploads live next to the database, not in the image, and are served through an
# authenticated route rather than StaticFiles: an image pasted into a private workspace
# would otherwise be a public URL forever.
UPLOADS_DIR = db.data_dir() / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
_UPLOAD_NAME_RE = re.compile(r"[0-9a-f]{32}\.[a-z0-9]{2,5}")


@app.get("/uploads/{name}", tags=["uploads"])
async def serve_upload(request: Request, name: str) -> Response:
    _api_user(request)
    if not _UPLOAD_NAME_RE.fullmatch(name):
        raise HTTPException(status_code=404, detail="Not found")
    path = UPLOADS_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)


app.include_router(api_router)
app.include_router(mcp.router)

# Must match the `base` the bundle was built with (DOCTION_APP_PATH in vite.config.js):
# the HTML requests its assets by absolute path, so a bundle built for /app and served
# at /wiki cannot find its own JavaScript.
APP_PATH = "/" + os.getenv("DOCTION_APP_PATH", "/app").strip("/")
SPA_DIR = BASE_DIR / "static" / "app"


async def serve_spa(full_path: str = "") -> Response:
    """Serves the React SPA.

    Returns the requested file when it exists (assets such as /app/assets/...);
    otherwise returns index.html, so reloading a client-side route such as
    /app/p/my-page is resolved by React Router.
    """
    if full_path:
        candidate = (SPA_DIR / full_path).resolve()
        # Stay inside SPA_DIR and serve only real files.
        if SPA_DIR.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
    index = SPA_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(
        status_code=404,
        detail="SPA not built. Run: cd frontend && npm install && npm run build",
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, _exc: Exception) -> Response:
    """Any uncaught exception becomes a JSON 500, without leaking the traceback."""
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


def _encode_token(user_id: int, token_version: int = 0) -> str:
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "exp": datetime.now(UTC) + timedelta(days=7),
    }
    return jwt.encode(payload, app.state.secret_key, algorithm="HS256")


def _decode_token(token: str) -> tuple[int, int] | None:
    """(user_id, token_version) from the JWT, or None if invalid or expired.

    The middleware compares the version against users.token_version, so a token issued
    before a password change no longer matches. Old JWTs without a `ver` claim are 0.
    """
    try:
        payload = jwt.decode(token, app.state.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str):
        return None
    try:
        uid = int(subject)
    except ValueError:
        return None
    version = payload.get("ver")
    return uid, version if isinstance(version, int) else 0


def _lang(request: Request) -> str:
    return getattr(request.state, "lang", i18n.DEFAULT_LANG)


def _registration_open() -> bool:
    """DISABLE_REGISTRATION closes web registration, except for the very first user."""
    return not DISABLE_REGISTRATION or not db.has_users()


def _ws_cookie(response: Response, slug: str) -> None:
    response.set_cookie(
        "workspace",
        slug,
        httponly=True,
        samesite="lax",
        secure=SECURE_COOKIES,
        max_age=WORKSPACE_MAX_AGE,
    )


def _issue_session(
    response: Response, user_id: int, ws_slug: str | None = None, token_version: int = 0
) -> None:
    """Set the httponly session cookie and, when given, the active workspace cookie."""
    response.set_cookie(
        "session",
        _encode_token(user_id, token_version),
        httponly=True,
        samesite="lax",
        secure=SECURE_COOKIES,
        max_age=SESSION_MAX_AGE,
    )
    if ws_slug:
        _ws_cookie(response, ws_slug)


def _lang_cookie(response: Response, lang: str) -> None:
    response.set_cookie(
        "lang",
        lang,
        httponly=True,
        samesite="lax",
        secure=SECURE_COOKIES,
        max_age=LANG_MAX_AGE,
    )


@app.get("/health", tags=["system"])
async def health() -> Response:
    """Liveness and readiness: checks that the database answers. 503 if it does not."""
    version = mcp.SERVER_INFO["version"]
    try:
        with db.connect() as conn:
            conn.execute("SELECT 1")
    except Exception:
        logger.exception("health check failed: db unreachable")
        return JSONResponse(
            {"status": "error", "db": "unreachable", "version": version},
            status_code=503,
        )
    return JSONResponse({"status": "ok", "db": "ok", "version": version})


if APP_PATH != "/":
    # With the SPA on a subpath, the root and the familiar shortcuts still reach it.
    @app.get("/", tags=["app"])
    async def home() -> Response:
        """The frontend is the React SPA, served at APP_PATH."""
        return RedirectResponse(APP_PATH + "/", status_code=HTTP_303_SEE_OTHER)

    @app.get("/login", tags=["app"])
    async def login_redirect() -> Response:
        return RedirectResponse(APP_PATH + "/login", status_code=HTTP_303_SEE_OTHER)

    @app.get("/register", tags=["app"])
    async def register_redirect() -> Response:
        return RedirectResponse(APP_PATH + "/register", status_code=HTTP_303_SEE_OTHER)


# In-flight OCR tasks, held strongly so the GC cannot cancel them halfway.
_OCR_TASKS: set[asyncio.Task] = set()


async def _ocr_index_upload(name: str, user_id: int, workspace_id: int, path: Path) -> None:
    """OCR in a threadpool after the upload has answered, so it waits on nothing."""
    try:
        await asyncio.to_thread(ocr.index_upload, name, user_id, workspace_id, path)
    except Exception:
        logger.exception("ocr: failed to index %s", name)


@app.post("/api/uploads", tags=["uploads"])
async def upload_image(request: Request, file: UploadFile = File(...)) -> Response:
    """Takes an image pasted or dragged into the editor, stores it under a name derived
    from its hash, and returns the URL to insert as markdown."""
    uid = _api_user(request)
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB)")
    ext = _image_extension(file.content_type, data)
    if ext is None:
        raise HTTPException(status_code=400, detail="Unsupported image type")
    name = hashlib.sha256(data).hexdigest()[:32] + ext
    dest = UPLOADS_DIR / name
    if not dest.exists():
        dest.write_bytes(data)
    if ocr.ocr_enabled():
        wid = _api_workspace(request, uid)
        task = asyncio.create_task(_ocr_index_upload(name, uid, wid, dest))
        _OCR_TASKS.add(task)
        task.add_done_callback(_OCR_TASKS.discard)
    return JSONResponse({"url": f"/uploads/{name}"})


# In-memory login rate limit, keyed by (ip, email) over a sliding window. Enough for a
# single instance; it resets on restart.
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW = timedelta(minutes=5)
_login_attempts: dict[str, list[datetime]] = {}


def _login_too_many(key: str) -> bool:
    now = datetime.now(UTC)
    cutoff = now - _LOGIN_WINDOW
    recent = [t for t in _login_attempts.get(key, []) if t > cutoff]
    if recent:
        _login_attempts[key] = recent
    else:
        _login_attempts.pop(key, None)
    return len(recent) >= _LOGIN_MAX_ATTEMPTS


def _login_record_failure(key: str) -> None:
    _login_attempts.setdefault(key, []).append(datetime.now(UTC))


def _login_clear(key: str) -> None:
    _login_attempts.pop(key, None)


@app.middleware("http")
async def attach_user(request: Request, call_next):
    request.state.user_id = None
    request.state.user_email = None
    request.state.user_display_name = None
    request.state.user_avatar_color = None
    request.state.workspaces = []
    request.state.workspace = None
    request.state.workspace_denied = False
    request.state.lang = i18n.resolve_lang(
        request.cookies.get("lang"), request.headers.get("accept-language")
    )

    # token_ver is validated against users.token_version; None means a PAT, which is
    # revoked individually rather than by version.
    user_id: int | None = None
    token_ver: int | None = None
    session_claims = _decode_token(request.cookies.get("session") or "")
    if session_claims is not None:
        user_id, token_ver = session_claims
    else:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            bearer = auth[7:].strip()
            if bearer.startswith(TOKEN_PREFIX):
                user_id = db.resolve_api_token(hash_api_token(bearer))
            else:
                bearer_claims = _decode_token(bearer)
                if bearer_claims is not None:
                    user_id, token_ver = bearer_claims

    if user_id is not None:
        user = db.get_user_by_id(user_id)
        if user is not None and token_ver is not None and token_ver != user.token_version:
            user = None  # JWT issued before a password change: revoked
        if user is not None:
            user_id = int(user.id)
            request.state.user_id = user_id
            request.state.user_email = user.email
            request.state.user_display_name = user.display_name
            request.state.user_avatar_color = user.avatar_color

            # Only when the user really has none: called unconditionally this put an
            # UPDATE in every authenticated request, pure WAL churn on the Pi.
            workspaces = db.list_workspaces(user_id)
            if not workspaces:
                db.ensure_default_workspace(user_id)
                workspaces = db.list_workspaces(user_id)
            request.state.workspaces = workspaces

            # ?ws= is sent by a caller that knows which workspace it wants; the cookie
            # is only a memory of the last visit. So a ?ws= that does not resolve is an
            # error and a cookie that does not resolve is not: silently falling into
            # another workspace would show a shared link the wrong page.
            requested_slug = (request.query_params.get("ws") or "").strip()
            explicit = bool(requested_slug)
            if not requested_slug:
                requested_slug = request.cookies.get("workspace") or ""

            workspace = None
            if requested_slug:
                for ws in workspaces:
                    if ws.slug == requested_slug:
                        workspace = ws
                        break
            request.state.workspace_denied = explicit and workspace is None
            if workspace is None and workspaces and not request.state.workspace_denied:
                workspace = workspaces[0]
            request.state.workspace = workspace

    response = await call_next(request)

    workspace = getattr(request.state, "workspace", None)
    if workspace is not None and request.cookies.get("workspace") != workspace.slug:
        _ws_cookie(response, workspace.slug)

    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    # HSTS only behind TLS, never on http dev.
    if SECURE_COOKIES:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )

    return response


# Registered last on purpose: Starlette resolves in registration order, so mounted at
# the root its `/{full_path:path}` would swallow /api, /health, /uploads and /static.
if APP_PATH == "/":
    app.get("/", tags=["app"])(serve_spa)
    app.get("/{full_path:path}", tags=["app"])(serve_spa)
else:
    app.get(APP_PATH, tags=["app"])(serve_spa)
    app.get(APP_PATH + "/{full_path:path}", tags=["app"])(serve_spa)
