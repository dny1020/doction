from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.status import HTTP_303_SEE_OTHER, HTTP_404_NOT_FOUND

from app import db, embeddings, git_repo, i18n, mcp, seed
from app.auth import (
    TOKEN_PREFIX,
    generate_api_token,
    hash_api_token,
)
from app.auth import hash_password as _hash_password
from app.auth import verify_password as _verify_password
from app.markdown import render_markdown

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
SESSION_MAX_AGE = 60 * 60 * 24 * 7
WORKSPACE_MAX_AGE = 60 * 60 * 24 * 30
LANG_MAX_AGE = 60 * 60 * 24 * 365
# Activo solo detrás de TLS; por defecto apagado para que dev http no requiera configuración.
SECURE_COOKIES = os.environ.get("SECURE_COOKIES", "").lower() in {"1", "true", "yes"}

# Paleta de colores para el avatar (debe coincidir con el fallback JS en base.html).
AVATAR_COLORS = [
    "#c0604a", "#4a7fc0", "#4aab6e", "#8b5fc0",
    "#c0914a", "#4aabc0", "#c05473", "#7a9c4a",
]

# Imágenes embebibles en documentos. Validamos por content-type + magic bytes.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_IMAGE_SIGNATURES = {
    "image/png":  (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/gif":  (b"GIF8", ".gif"),
}


def _image_extension(content_type: str | None, data: bytes) -> str | None:
    """Devuelve la extensión si content-type y magic bytes concuerdan, si no None."""
    sig = _IMAGE_SIGNATURES.get(content_type or "")
    if sig is not None and data.startswith(sig[0]):
        return sig[1]
    if content_type == "image/webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


# ── REST API ─────────────────────────────────────────────────────────────────

class _TokenIn(BaseModel):
    email: str
    password: str


class _PageIn(BaseModel):
    title: str
    content: str = ""
    parent_slug: str | None = None
    slug: str | None = None


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
    ws = getattr(request.state, "workspace", None)
    if ws is None:
        ws = db.ensure_default_workspace(user_id)
    return int(ws["id"])


@api_router.post("/token")
def api_token(body: _TokenIn):
    user = db.get_user_by_email(body.email.strip().lower())
    if user is None or not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": _encode_token(int(user["id"])), "token_type": "bearer"}


@api_router.post("/tokens", status_code=201)
def api_create_token(request: Request, body: _ApiTokenIn):
    uid = _api_user(request)
    token = generate_api_token()
    token_id = db.create_api_token(uid, body.name, hash_api_token(token))
    # El plaintext se devuelve una sola vez; nunca se almacena.
    return {"id": token_id, "name": body.name.strip() or "token", "token": token}


@api_router.get("/tokens")
def api_list_tokens(request: Request):
    uid = _api_user(request)
    return [dict(t) for t in db.list_api_tokens(uid)]


@api_router.delete("/tokens/{token_id}", status_code=204)
def api_revoke_token(request: Request, token_id: int):
    uid = _api_user(request)
    if not db.revoke_api_token(uid, token_id):
        raise HTTPException(status_code=404, detail="Token not found")


@api_router.get("/workspaces")
def api_list_workspaces(request: Request):
    uid = _api_user(request)
    return [dict(w) for w in db.list_workspaces(uid)]


@api_router.post("/workspaces", status_code=201)
def api_create_workspace(request: Request, body: _WorkspaceIn):
    uid = _api_user(request)
    slug = db.create_workspace(uid, body.name)
    return {"slug": slug, "name": body.name.strip() or "Workspace"}


def _api_owned_workspace(request: Request, uid: int, slug: str) -> dict:
    """Resuelve el workspace por slug exigiendo que el usuario sea owner."""
    ws = db.get_workspace_by_slug(uid, slug)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner role required")
    return dict(ws)


@api_router.get("/workspaces/{slug}/members")
def api_list_members(request: Request, slug: str):
    uid = _api_user(request)
    ws = db.get_workspace_by_slug(uid, slug)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return [
        {
            "user_id": m["user_id"],
            "email": m["email"],
            "display_name": m["display_name"],
            "role": m["role"],
        }
        for m in db.list_workspace_members(int(ws["id"]))
    ]


@api_router.post("/workspaces/{slug}/members", status_code=201)
def api_add_member(request: Request, slug: str, body: _MemberIn):
    uid = _api_user(request)
    ws = _api_owned_workspace(request, uid, slug)
    target = db.get_user_by_email(body.email.strip().lower())
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if db.get_member_role(int(target["id"]), int(ws["id"])) is not None:
        raise HTTPException(status_code=409, detail="Already a member")
    db.add_workspace_member(int(ws["id"]), int(target["id"]), "member")
    return {"workspace": slug, "user_id": int(target["id"]), "role": "member"}


@api_router.delete("/workspaces/{slug}/members/{member_id}", status_code=204)
def api_remove_member(request: Request, slug: str, member_id: int):
    uid = _api_user(request)
    ws = _api_owned_workspace(request, uid, slug)
    if db.get_member_role(member_id, int(ws["id"])) == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the owner")
    if not db.remove_workspace_member(int(ws["id"]), member_id):
        raise HTTPException(status_code=404, detail="Member not found")


@api_router.get("/pages")
def api_list_pages(request: Request):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    return db.list_pages_tree(uid, wid)


@api_router.post("/pages", status_code=201)
def api_create_page(request: Request, body: _PageIn):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    slug = db.create_page(
        uid, wid, body.title, body.content,
        parent_slug=body.parent_slug, requested_slug=body.slug,
    )
    _commit_page(request, uid, wid, slug, body.title, body.content)
    return {"slug": slug, "title": body.title.strip() or "Untitled"}


@api_router.get("/pages/{slug}/history")
def api_page_history(request: Request, slug: str, limit: int = 50):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, uid, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    ws = db.get_workspace_by_id(wid)
    ws_slug = ws["slug"] if ws else "unknown"
    return git_repo.get_page_history(ws_slug, slug, limit=limit)


@api_router.get("/pages/{slug}/history/{sha}")
def api_page_at_commit(request: Request, slug: str, sha: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, uid, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    ws = db.get_workspace_by_id(wid)
    ws_slug = ws["slug"] if ws else "unknown"
    content = git_repo.get_page_at_commit(ws_slug, slug, sha)
    if content is None:
        raise HTTPException(status_code=404, detail="Commit not found")
    return {"slug": slug, "sha": sha, "content": content}


@api_router.get("/pages/{slug}/raw", response_class=PlainTextResponse)
def api_get_page_raw(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, uid, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page["content"]


@api_router.get("/pages/{slug}")
def api_get_page(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, uid, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    children = db.list_child_pages(uid, wid, int(page["id"]))
    return {
        "slug": page["slug"],
        "title": page["title"],
        "content": page["content"],
        "parent_slug": page["parent_slug"],
        "children": [{"slug": c["slug"], "title": c["title"]} for c in children],
        "created_at": page["created_at"],
        "updated_at": page["updated_at"],
    }


@api_router.put("/pages/{slug}")
def api_update_page(request: Request, slug: str, body: _PagePatch):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, uid, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    new_title = body.title if body.title is not None else page["title"]
    new_content = body.content if body.content is not None else page["content"]
    db.update_page(uid, wid, slug, new_title, new_content)
    _commit_page(request, uid, wid, slug, new_title, new_content)
    return {"slug": slug, "title": new_title, "updated": True}


@api_router.delete("/pages/{slug}", status_code=204)
def api_delete_page(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    if not db.delete_page(uid, wid, slug):
        raise HTTPException(status_code=404, detail="Page not found")


@api_router.get("/search")
def api_search(request: Request, q: str = "", mode: str = "keyword"):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    if not q.strip():
        return []
    if mode == "semantic":
        return embeddings.semantic_search(uid, wid, q)
    results = db.search_pages(uid, wid, q)
    return [
        {"slug": r["slug"], "title": r["title"], "snippet": r["snippet"]}
        for r in results
    ]


def _commit_page(
    request: Request, uid: int, wid: int, slug: str, title: str, content: str
) -> None:
    ws = getattr(request.state, "workspace", None)
    if ws:
        ws_slug = ws["slug"]
    else:
        _ws = db.get_workspace_by_id(wid)
        ws_slug = _ws["slug"] if _ws else "default"
    author = getattr(request.state, "user_email", None) or "user"
    sha = git_repo.commit_page(ws_slug, slug, content, author, f"Save: {title}")
    if sha:
        db.set_page_git_commit(uid, wid, slug, sha)


@asynccontextmanager
async def lifespan(_: FastAPI):
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        secret_key = "dev-secret-key"
        logger.warning("SECRET_KEY not set — using insecure dev default, do not use in production")
    app.state.secret_key = secret_key
    db.init_db()
    git_repo.ensure_repo()
    logger.info("doction ready — db: %s", db.db_path())

    embed_task: asyncio.Task | None = None
    if embeddings.semantic_enabled():
        embed_task = asyncio.create_task(embeddings.enrichment_worker())
        logger.info("semantic search ON — embedding worker running")

    yield

    if embed_task is not None:
        embed_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await embed_task


app = FastAPI(title="doction", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Imágenes subidas (pegadas/arrastradas en el editor) viven junto a la BD, no en la imagen.
UPLOADS_DIR = db.db_path().parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

app.include_router(api_router)
app.include_router(mcp.router)


def _encode_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(days=7),
    }
    return jwt.encode(payload, app.state.secret_key, algorithm="HS256")


def _decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, app.state.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str):
        return None
    try:
        return int(subject)
    except ValueError:
        return None


def _get_user_id(request: Request) -> int | None:
    token = request.cookies.get("session")
    if not token:
        return None
    return _decode_token(token)


def _require_user(request: Request) -> int | Response:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
    return int(user_id)


def _require_workspace_id(request: Request, user_id: int) -> int:
    workspace = getattr(request.state, "workspace", None)
    if workspace is None:
        workspace = db.ensure_default_workspace(user_id)
        request.state.workspaces = db.list_workspaces(user_id)
        request.state.workspace = workspace
    return int(workspace["id"])


def _lang(request: Request) -> str:
    return getattr(request.state, "lang", i18n.DEFAULT_LANG)


def _i18n(request: Request) -> dict[str, object]:
    lang = _lang(request)
    return {"lang": lang, "t": i18n.get_catalog(lang)}


def _anonymous_context(request: Request) -> dict[str, object]:
    return {
        "pages": [],
        "workspaces": [],
        "active_workspace": None,
        "user_email": request.state.user_email,
        "user_display_name": getattr(request.state, "user_display_name", None),
        "user_avatar_color": getattr(request.state, "user_avatar_color", None),
        **_i18n(request),
    }


def _authed_context(request: Request, user_id: int) -> dict[str, object]:
    workspace = getattr(request.state, "workspace", None)
    pages = []
    if workspace is not None:
        pages = db.list_pages_tree(user_id, int(workspace["id"]))
    return {
        "pages": pages,
        "workspaces": getattr(request.state, "workspaces", []),
        "active_workspace": workspace,
        "user_email": request.state.user_email,
        "user_display_name": getattr(request.state, "user_display_name", None),
        "user_avatar_color": getattr(request.state, "user_avatar_color", None),
        **_i18n(request),
    }


def _ws_cookie(response: Response, slug: str) -> None:
    response.set_cookie(
        "workspace", slug,
        httponly=True, samesite="lax", secure=SECURE_COOKIES, max_age=WORKSPACE_MAX_AGE,
    )


def _lang_cookie(response: Response, lang: str) -> None:
    response.set_cookie(
        "lang", lang,
        httponly=True, samesite="lax", secure=SECURE_COOKIES, max_age=LANG_MAX_AGE,
    )


def _safe_next(path: str) -> str:
    if not path.startswith("/") or path.startswith("//"):
        return "/"
    return path


def _not_found(request: Request, slug: str) -> HTMLResponse:
    user_id = getattr(request.state, "user_id", None)
    if user_id is not None:
        context = _authed_context(request, user_id)
    else:
        context = _anonymous_context(request)
    context.update({"slug": slug})
    return templates.TemplateResponse(
        request,
        "not_found.html",
        context,
        status_code=HTTP_404_NOT_FOUND,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    workspace_id = _require_workspace_id(request, user_id)
    page = db.latest_page(user_id, workspace_id)
    context = _authed_context(request, user_id)
    if page is None:
        return templates.TemplateResponse(
            request,
            "empty.html",
            {**context, "active_slug": None},
        )
    children = db.list_child_pages(user_id, workspace_id, int(page["id"]))
    breadcrumbs = db.get_ancestors(int(page["id"]), user_id, workspace_id)
    return templates.TemplateResponse(
        request,
        "page.html",
        {
            **context,
            "page": page,
            "rendered": render_markdown(page["content"]),
            "children": children,
            "breadcrumbs": breadcrumbs,
            "active_slug": page["slug"],
        },
    )


@app.get("/new", response_class=HTMLResponse)
async def new_page_form(
    request: Request,
    parent: str = "",
    title: str = "",
    slug: str = "",
) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    workspace_id = _require_workspace_id(request, user_id)

    parent_page = db.get_page(parent, user_id, workspace_id) if parent else None
    prefill_slug = slug.strip()
    prefill_title = title.strip()
    if not prefill_title and prefill_slug:
        prefill_title = prefill_slug.replace("-", " ").strip().title()

    return templates.TemplateResponse(
        request,
        "new.html",
        {
            **_authed_context(request, user_id),
            "active_slug": None,
            "parent": parent_page,
            "prefill_title": prefill_title,
            "prefill_slug": prefill_slug,
        },
    )


@app.post("/pages")
async def create_page_authed(
    request: Request,
    title: str = Form(...),
    content: str = Form(""),
    parent_slug: str = Form(""),
    slug: str = Form(""),
) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    workspace_id = _require_workspace_id(request, user_id)
    new_slug = db.create_page(
        user_id,
        workspace_id,
        title,
        content,
        parent_slug=parent_slug or None,
        requested_slug=slug or None,
    )
    _commit_page(request, user_id, workspace_id, new_slug, title, content)
    return RedirectResponse(f"/pages/{new_slug}", status_code=HTTP_303_SEE_OTHER)


@app.get("/pages/{slug}", response_class=HTMLResponse)
async def read_page(request: Request, slug: str) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    workspace_id = _require_workspace_id(request, user_id)
    page = db.get_page(slug, user_id, workspace_id)
    if page is None:
        return _not_found(request, slug)
    children = db.list_child_pages(user_id, workspace_id, int(page["id"]))
    breadcrumbs = db.get_ancestors(int(page["id"]), user_id, workspace_id)
    return templates.TemplateResponse(
        request,
        "page.html",
        {
            **_authed_context(request, user_id),
            "page": page,
            "rendered": render_markdown(page["content"]),
            "children": children,
            "breadcrumbs": breadcrumbs,
            "active_slug": slug,
        },
    )


@app.get("/pages/{slug}/history", response_class=HTMLResponse)
async def page_history(request: Request, slug: str) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    workspace_id = _require_workspace_id(request, user_id)
    page = db.get_page(slug, user_id, workspace_id)
    if page is None:
        return _not_found(request, slug)
    ws = db.get_workspace_by_id(workspace_id)
    ws_slug = ws["slug"] if ws else "default"
    history = git_repo.get_page_history(ws_slug, slug)
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            **_authed_context(request, user_id),
            "page": page,
            "history": history,
            "active_slug": slug,
        },
    )


@app.get("/pages/{slug}/history/{sha}", response_class=HTMLResponse)
async def page_history_detail(request: Request, slug: str, sha: str) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    workspace_id = _require_workspace_id(request, user_id)
    page = db.get_page(slug, user_id, workspace_id)
    if page is None:
        return _not_found(request, slug)
    ws = db.get_workspace_by_id(workspace_id)
    ws_slug = ws["slug"] if ws else "default"
    content = git_repo.get_page_at_commit(ws_slug, slug, sha)
    if content is None:
        return _not_found(request, slug)
    return templates.TemplateResponse(
        request,
        "history_detail.html",
        {
            **_authed_context(request, user_id),
            "page": page,
            "sha": sha,
            "rendered": render_markdown(content),
            "active_slug": slug,
        },
    )


@app.post("/pages/{slug}/restore/{sha}")
async def restore_page(request: Request, slug: str, sha: str) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    workspace_id = _require_workspace_id(request, user_id)
    page = db.get_page(slug, user_id, workspace_id)
    if page is None:
        return _not_found(request, slug)
    ws = db.get_workspace_by_id(workspace_id)
    ws_slug = ws["slug"] if ws else "default"
    content = git_repo.get_page_at_commit(ws_slug, slug, sha)
    if content is None:
        return _not_found(request, slug)
    title = page["title"]
    new_slug = db.update_page(user_id, workspace_id, slug, title, content)
    effective_slug = new_slug or slug
    author = getattr(request.state, "user_email", None) or "user"
    new_sha = git_repo.commit_page(
        ws_slug, effective_slug, content, author, f"Restore {sha}: {title}"
    )
    if new_sha:
        db.set_page_git_commit(user_id, workspace_id, effective_slug, new_sha)
    return RedirectResponse(f"/pages/{effective_slug}", status_code=HTTP_303_SEE_OTHER)


@app.get("/pages/{slug}/edit", response_class=HTMLResponse)
async def edit_page_form(request: Request, slug: str) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    workspace_id = _require_workspace_id(request, user_id)
    page = db.get_page(slug, user_id, workspace_id)
    if page is None:
        return _not_found(request, slug)
    return templates.TemplateResponse(
        request,
        "edit.html",
        {
            **_authed_context(request, user_id),
            "page": page,
            "active_slug": slug,
        },
    )


@app.post("/pages/{slug}")
async def update_page(
    request: Request,
    slug: str,
    title: str = Form(...),
    content: str = Form(""),
) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    workspace_id = _require_workspace_id(request, user_id)
    new_slug = db.update_page(user_id, workspace_id, slug, title, content)
    effective_slug = new_slug or slug
    _commit_page(request, user_id, workspace_id, effective_slug, title, content)
    return RedirectResponse(f"/pages/{effective_slug}", status_code=HTTP_303_SEE_OTHER)


@app.post("/pages/{slug}/delete")
async def remove_page(request: Request, slug: str) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    workspace_id = _require_workspace_id(request, user_id)
    db.delete_page(user_id, workspace_id, slug)
    return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)


@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = "") -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return templates.TemplateResponse(
            request,
            "partials/search_results.html",
            {"results": [], "query": "", **_i18n(request)},
        )
    workspace_id = _require_workspace_id(request, user_id)
    results = db.search_pages(user_id, workspace_id, q) if q.strip() else []
    return templates.TemplateResponse(
        request,
        "partials/search_results.html",
        {"results": results, "query": q, **_i18n(request)},
    )


@app.post("/preview", response_class=HTMLResponse)
async def preview(request: Request, content: str = Form("")) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return HTMLResponse("", status_code=401)
    return HTMLResponse(render_markdown(content))


@app.post("/api/uploads")
async def upload_image(request: Request, file: UploadFile = File(...)) -> Response:
    """Recibe una imagen (pegada/arrastrada en el editor), la guarda con nombre
    derivado de su hash y devuelve la URL para insertarla como markdown."""
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        return JSONResponse({"error": "file too large"}, status_code=413)
    ext = _image_extension(file.content_type, data)
    if ext is None:
        return JSONResponse({"error": "unsupported image type"}, status_code=400)
    name = hashlib.sha256(data).hexdigest()[:32] + ext
    dest = UPLOADS_DIR / name
    if not dest.exists():
        dest.write_bytes(data)
    return JSONResponse({"url": f"/uploads/{name}"})


@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request) -> Response:
    if getattr(request.state, "user_id", None) is not None:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "login.html",
        {**_anonymous_context(request), "active_slug": None},
    )


@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)) -> Response:
    user = db.get_user_by_email(email.strip().lower())
    if user is None or not _verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                **_anonymous_context(request),
                "active_slug": None,
                "error": i18n.get_catalog(_lang(request))["err_invalid_credentials"],
            },
            status_code=400,
        )

    user_id = int(user["id"])
    workspace = db.ensure_default_workspace(user_id)
    token = _encode_token(user_id)
    response = RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    response.set_cookie(
        "session", token,
        httponly=True, samesite="lax", secure=SECURE_COOKIES, max_age=SESSION_MAX_AGE,
    )
    _ws_cookie(response, workspace["slug"])
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_form(request: Request) -> Response:
    if getattr(request.state, "user_id", None) is not None:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "register.html",
        {**_anonymous_context(request), "active_slug": None},
    )


@app.post("/register")
async def register(request: Request, email: str = Form(...), password: str = Form(...)) -> Response:
    email = email.strip().lower()
    cat = i18n.get_catalog(_lang(request))
    if not email or "@" not in email:
        return templates.TemplateResponse(
            request, "register.html",
            {**_anonymous_context(request), "active_slug": None, "error": cat["err_valid_email"]},
            status_code=400,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request, "register.html",
            {**_anonymous_context(request), "active_slug": None,
             "error": cat["err_password_min"]},
            status_code=400,
        )
    if db.get_user_by_email(email) is not None:
        return templates.TemplateResponse(
            request, "register.html",
            {**_anonymous_context(request), "active_slug": None,
             "error": cat["err_email_registered"]},
            status_code=400,
        )

    user_id = db.create_user(email, _hash_password(password))
    workspace = db.ensure_default_workspace(user_id)
    workspace_id = int(workspace["id"])
    db.claim_unowned_pages(user_id, workspace_id)
    for title, content in seed.SEED_PAGES:
        db.create_page(user_id, workspace_id, title, content)

    token = _encode_token(user_id)
    response = RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    response.set_cookie(
        "session", token,
        httponly=True, samesite="lax", secure=SECURE_COOKIES, max_age=SESSION_MAX_AGE,
    )
    _ws_cookie(response, workspace["slug"])
    return response


@app.get("/lang/{code}")
async def switch_language(request: Request, code: str, next_url: str = "/") -> Response:
    """Cambia el idioma (cookie). Público: funciona también en login/registro."""
    target = _safe_next(next_url)
    response = RedirectResponse(target, status_code=HTTP_303_SEE_OTHER)
    if code in i18n.LANGS:
        _lang_cookie(response, code)
    return response


@app.post("/workspaces")
async def create_workspace(request: Request, name: str = Form(...)) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    slug = db.create_workspace(user_id, name)
    response = RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    _ws_cookie(response, slug)
    return response


@app.get("/workspaces/switch/{slug}")
async def switch_workspace(request: Request, slug: str, next_url: str = "/") -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    workspace = db.get_workspace_by_slug(user_id, slug)
    target = _safe_next(next_url)
    response = RedirectResponse(target, status_code=HTTP_303_SEE_OTHER)
    if workspace is not None:
        _ws_cookie(response, workspace["slug"])
    return response


# code → (tono, clave de traducción). El texto se resuelve según el idioma activo.
_SETTINGS_MESSAGES = {
    "profile":    ("ok",    "msg_profile"),
    "password":   ("ok",    "msg_password"),
    "ws_renamed": ("ok",    "msg_ws_renamed"),
    "ws_deleted": ("ok",    "msg_ws_deleted"),
    "pw_current": ("error", "msg_pw_current"),
    "pw_match":   ("error", "msg_pw_match"),
    "pw_len":     ("error", "msg_pw_len"),
    "ws_last":    ("error", "msg_ws_last"),
    "ws_name":    ("error", "msg_ws_name"),
    "member_added":   ("ok",    "msg_member_added"),
    "member_removed": ("ok",    "msg_member_removed"),
    "member_404":     ("error", "err_user_not_found"),
    "member_dup":     ("error", "err_already_member"),
    "not_owner":      ("error", "err_not_owner"),
}


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, m: str | None = None) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    user = db.get_user_by_id(user_id)
    tone, msg_key = _SETTINGS_MESSAGES.get(m or "", (None, None))
    message = i18n.get_catalog(_lang(request))[msg_key] if msg_key else None
    workspaces = getattr(request.state, "workspaces", [])
    ws_list = [
        {
            "slug": w["slug"],
            "name": w["name"],
            "role": w["role"],
            "members": (
                db.list_workspace_members(int(w["id"])) if w["role"] == "owner" else []
            ),
        }
        for w in workspaces
    ]
    owned_count = sum(1 for w in workspaces if w["role"] == "owner")
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            **_authed_context(request, user_id),
            "active_slug": None,
            "avatar_colors": AVATAR_COLORS,
            "profile_name": (user["display_name"] if user else "") or "",
            "current_color": (user["avatar_color"] if user else "") or "",
            "ws_list": ws_list,
            "owned_count": owned_count,
            "flash_tone": tone,
            "flash_msg": message,
        },
    )


@app.post("/settings/profile")
async def update_profile(
    request: Request,
    display_name: str = Form(""),
    avatar_color: str = Form(""),
) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    name = display_name.strip()[:40]
    color = avatar_color if avatar_color in AVATAR_COLORS else None
    db.update_user_profile(user_id, name or None, color)
    return RedirectResponse("/settings?m=profile", status_code=HTTP_303_SEE_OTHER)


@app.post("/settings/password")
async def update_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    user = db.get_user_by_id(user_id)
    if user is None or not _verify_password(current_password, user["password_hash"]):
        return RedirectResponse("/settings?m=pw_current", status_code=HTTP_303_SEE_OTHER)
    if len(new_password) < 8:
        return RedirectResponse("/settings?m=pw_len", status_code=HTTP_303_SEE_OTHER)
    if new_password != confirm_password:
        return RedirectResponse("/settings?m=pw_match", status_code=HTTP_303_SEE_OTHER)
    db.update_user_password(user_id, _hash_password(new_password))
    return RedirectResponse("/settings?m=password", status_code=HTTP_303_SEE_OTHER)


def _owned_workspace(user_id: int, slug: str):
    """Workspace resuelto por slug solo si el usuario es su owner; si no, None."""
    ws = db.get_workspace_by_slug(user_id, slug)
    if ws is None or ws["role"] != "owner":
        return None
    return ws


@app.post("/workspaces/{slug}/rename")
async def rename_workspace_route(request: Request, slug: str, name: str = Form(...)) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    if _owned_workspace(user_id, slug) is None:
        return RedirectResponse("/settings?m=not_owner", status_code=HTTP_303_SEE_OTHER)
    ok = db.rename_workspace(user_id, slug, name)
    return RedirectResponse(
        f"/settings?m={'ws_renamed' if ok else 'ws_name'}", status_code=HTTP_303_SEE_OTHER
    )


@app.post("/workspaces/{slug}/delete")
async def delete_workspace_route(request: Request, slug: str) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    if _owned_workspace(user_id, slug) is None:
        return RedirectResponse("/settings?m=not_owner", status_code=HTTP_303_SEE_OTHER)
    ok = db.delete_workspace(user_id, slug)
    response = RedirectResponse(
        f"/settings?m={'ws_deleted' if ok else 'ws_last'}", status_code=HTTP_303_SEE_OTHER
    )
    # Si se borró el workspace activo, mover la cookie a uno que quede.
    if ok and request.cookies.get("workspace") == slug:
        remaining = db.list_workspaces(user_id)
        if remaining:
            _ws_cookie(response, remaining[0]["slug"])
    return response


@app.post("/workspaces/{slug}/members")
async def add_member_route(
    request: Request, slug: str, email: str = Form(...), role: str = Form("member")
) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    ws = _owned_workspace(user_id, slug)
    if ws is None:
        return RedirectResponse("/settings?m=not_owner", status_code=HTTP_303_SEE_OTHER)
    target = db.get_user_by_email(email.strip().lower())
    if target is None:
        return RedirectResponse("/settings?m=member_404", status_code=HTTP_303_SEE_OTHER)
    if db.get_member_role(int(target["id"]), int(ws["id"])) is not None:
        return RedirectResponse("/settings?m=member_dup", status_code=HTTP_303_SEE_OTHER)
    db.add_workspace_member(int(ws["id"]), int(target["id"]), "member")
    return RedirectResponse("/settings?m=member_added", status_code=HTTP_303_SEE_OTHER)


@app.post("/workspaces/{slug}/members/{member_id}/remove")
async def remove_member_route(request: Request, slug: str, member_id: int) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    ws = _owned_workspace(user_id, slug)
    if ws is None:
        return RedirectResponse("/settings?m=not_owner", status_code=HTTP_303_SEE_OTHER)
    if db.get_member_role(member_id, int(ws["id"])) == "owner":
        return RedirectResponse("/settings?m=not_owner", status_code=HTTP_303_SEE_OTHER)
    db.remove_workspace_member(int(ws["id"]), member_id)
    return RedirectResponse("/settings?m=member_removed", status_code=HTTP_303_SEE_OTHER)


@app.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.state.workspace = None
    response = RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
    response.delete_cookie("session")
    response.delete_cookie("workspace")
    return response


@app.middleware("http")
async def attach_user(request: Request, call_next):
    request.state.user_id = None
    request.state.user_email = None
    request.state.user_display_name = None
    request.state.user_avatar_color = None
    request.state.workspaces = []
    request.state.workspace = None
    request.state.lang = i18n.resolve_lang(
        request.cookies.get("lang"), request.headers.get("accept-language")
    )

    user_id = _get_user_id(request)
    if user_id is None:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            bearer = auth[7:].strip()
            if bearer.startswith(TOKEN_PREFIX):
                user_id = db.resolve_api_token(hash_api_token(bearer))
            else:
                user_id = _decode_token(bearer)

    if user_id is not None:
        user = db.get_user_by_id(user_id)
        if user is not None:
            user_id = int(user["id"])
            request.state.user_id = user_id
            request.state.user_email = user["email"]
            request.state.user_display_name = user["display_name"]
            request.state.user_avatar_color = user["avatar_color"]

            db.ensure_default_workspace(user_id)
            workspaces = db.list_workspaces(user_id)
            request.state.workspaces = workspaces

            requested_slug = request.query_params.get("ws") or request.cookies.get("workspace")
            workspace = None
            if requested_slug:
                workspace = next((ws for ws in workspaces if ws["slug"] == requested_slug), None)
            if workspace is None and workspaces:
                workspace = workspaces[0]
            request.state.workspace = workspace

    response = await call_next(request)

    workspace = getattr(request.state, "workspace", None)
    if workspace is not None and request.cookies.get("workspace") != workspace["slug"]:
        _ws_cookie(response, workspace["slug"])

    return response
