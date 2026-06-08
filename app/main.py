"""doction — FastAPI + HTMX markdown wiki."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from fastapi import APIRouter, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.status import HTTP_303_SEE_OTHER, HTTP_404_NOT_FOUND

import app.mcp_server as _mcp_module
from app import db, embeddings, git_repo, seed
from app.auth import hash_password as _hash_password
from app.auth import verify_password as _verify_password
from app.markdown import render_markdown

_MCP_SECRET = os.environ.get("MCP_SECRET", "")


def _build_mcp_app():
    from mcp.server.fastmcp import FastMCP
    _server = FastMCP("doction")
    for fn in (
        _mcp_module.list_workspaces, _mcp_module.list_pages, _mcp_module.get_page,
        _mcp_module.search_pages, _mcp_module.create_page, _mcp_module.update_page,
    ):
        _server.tool()(fn)
    _inner = _server.streamable_http_app()

    async def _auth_wrapper(scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            auth = headers.get(b"authorization", b"").decode()
            if auth != f"Bearer {_MCP_SECRET}":
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"text/plain")]})
                await send({"type": "http.response.body", "body": b"Unauthorized"})
                return
        await _inner(scope, receive, send)

    return _auth_wrapper

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
SESSION_MAX_AGE = 60 * 60 * 24 * 7
WORKSPACE_MAX_AGE = 60 * 60 * 24 * 30


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


@api_router.get("/workspaces")
def api_list_workspaces(request: Request):
    uid = _api_user(request)
    return [dict(w) for w in db.list_workspaces(uid)]


@api_router.post("/workspaces", status_code=201)
def api_create_workspace(request: Request, body: _WorkspaceIn):
    uid = _api_user(request)
    slug = db.create_workspace(uid, body.name)
    return {"slug": slug, "name": body.name.strip() or "Workspace"}


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
    _commit_and_embed(request, uid, wid, slug, body.title, body.content)
    return {"slug": slug, "title": body.title.strip() or "Untitled"}


@api_router.get("/pages/{slug}/history")
def api_page_history(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, uid, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    ws = db.get_workspace_by_id(wid)
    ws_slug = ws["slug"] if ws else "unknown"
    return git_repo.get_page_history(ws_slug, slug)


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
    _commit_and_embed(request, uid, wid, slug, new_title, new_content)
    return {"slug": slug, "title": new_title, "updated": True}


@api_router.delete("/pages/{slug}", status_code=204)
def api_delete_page(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    if not db.delete_page(uid, wid, slug):
        raise HTTPException(status_code=404, detail="Page not found")


@api_router.get("/search")
def api_search(request: Request, q: str = "", mode: str = "fts"):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    if not q.strip():
        return []
    embedder = getattr(request.app.state, "embedder", None)
    if mode == "semantic" and embedder is not None:
        query_emb = embeddings.embed(embedder, q)
        results = db.semantic_search_pages(uid, wid, query_emb)
    elif mode == "hybrid" and embedder is not None:
        query_emb = embeddings.embed(embedder, q)
        results = db.hybrid_search_pages(uid, wid, q, query_emb)
    else:
        results = db.search_pages(uid, wid, q)
    return [
        {"slug": r["slug"], "title": r["title"],
         "snippet": (r.get("snippet") or "") if isinstance(r, dict) else r["snippet"]}
        for r in results
    ]


def _commit_and_embed(
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
    embedder = getattr(request.app.state, "embedder", None)
    if embedder is not None:
        emb = embeddings.embed(embedder, f"{title}\n\n{content}")
        db.update_page_embedding(uid, wid, slug, emb)


async def _load_embedder_bg() -> None:
    """Load the embedding model in the background so startup is not blocked."""
    try:
        model = await asyncio.to_thread(embeddings.load_model)
        app.state.embedder = model
        if model is not None:
            logger.info("Embedding model loaded; semantic search enabled.")
    except Exception:
        logger.warning("Embedding model failed to load; semantic search disabled.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    app.state.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
    app.state.embedder = None
    db.init_db()
    git_repo.ensure_repo()
    _email = os.environ.get("DOCTION_EMAIL", "").strip()
    _password = os.environ.get("DOCTION_PASSWORD", "")
    if _email and _password and _MCP_SECRET:
        _user = db.get_user_by_email(_email)
        if _user and _verify_password(_password, _user["password_hash"]):
            _ws = db.ensure_default_workspace(int(_user["id"]))
            _mcp_module.setup(int(_user["id"]), int(_ws["id"]))
            app.mount("/mcp", _build_mcp_app())
            logger.info("MCP HTTP server ready at /mcp")
        else:
            logger.warning("MCP: invalid DOCTION_EMAIL/DOCTION_PASSWORD — /mcp disabled")
    # Load model in background — app serves immediately, model ready after ~60s on ARM64.
    task = asyncio.create_task(_load_embedder_bg())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="doction", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(api_router)


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


def _anonymous_context(request: Request) -> dict[str, object]:
    return {
        "pages": [],
        "workspaces": [],
        "active_workspace": None,
        "user_email": request.state.user_email,
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
    }


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
async def home(request: Request) -> HTMLResponse:
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
    return templates.TemplateResponse(
        request,
        "page.html",
        {
            **context,
            "page": page,
            "rendered": render_markdown(page["content"]),
            "children": children,
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
    _commit_and_embed(request, user_id, workspace_id, new_slug, title, content)
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
    return templates.TemplateResponse(
        request,
        "page.html",
        {
            **_authed_context(request, user_id),
            "page": page,
            "rendered": render_markdown(page["content"]),
            "children": children,
            "active_slug": slug,
        },
    )


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
    _commit_and_embed(request, user_id, workspace_id, effective_slug, title, content)
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
            {"results": [], "query": ""},
        )
    workspace_id = _require_workspace_id(request, user_id)
    results = db.search_pages(user_id, workspace_id, q) if q.strip() else []
    return templates.TemplateResponse(
        request,
        "partials/search_results.html",
        {"results": results, "query": q},
    )


@app.post("/preview", response_class=HTMLResponse)
async def preview(request: Request, content: str = Form("")) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return HTMLResponse("", status_code=401)
    return HTMLResponse(render_markdown(content))


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
                "error": "Invalid credentials.",
            },
            status_code=400,
        )

    user_id = int(user["id"])
    workspace = db.ensure_default_workspace(user_id)
    token = _encode_token(user_id)
    response = RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    response.set_cookie(
        "session",
        token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )
    response.set_cookie(
        "workspace",
        workspace["slug"],
        httponly=True,
        samesite="lax",
        max_age=WORKSPACE_MAX_AGE,
    )
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
    if not email or "@" not in email:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                **_anonymous_context(request),
                "active_slug": None,
                "error": "Enter a valid email.",
            },
            status_code=400,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                **_anonymous_context(request),
                "active_slug": None,
                "error": "Password must be 8+ chars.",
            },
            status_code=400,
        )
    if db.get_user_by_email(email) is not None:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                **_anonymous_context(request),
                "active_slug": None,
                "error": "Email already registered.",
            },
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
        "session",
        token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )
    response.set_cookie(
        "workspace",
        workspace["slug"],
        httponly=True,
        samesite="lax",
        max_age=WORKSPACE_MAX_AGE,
    )
    return response


@app.post("/workspaces")
async def create_workspace(request: Request, name: str = Form(...)) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    slug = db.create_workspace(user_id, name)
    response = RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    response.set_cookie(
        "workspace",
        slug,
        httponly=True,
        samesite="lax",
        max_age=WORKSPACE_MAX_AGE,
    )
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
        response.set_cookie(
            "workspace",
            workspace["slug"],
            httponly=True,
            samesite="lax",
            max_age=WORKSPACE_MAX_AGE,
        )
    return response


@app.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.state.workspace = None
    response = RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
    response.delete_cookie("session")
    response.delete_cookie("workspace")
    return response


@app.middleware("http")
async def attach_user(request: Request, call_next):
    if request.url.path.startswith("/mcp"):
        return await call_next(request)
    request.state.user_id = None
    request.state.user_email = None
    request.state.workspaces = []
    request.state.workspace = None

    user_id = _get_user_id(request)
    if user_id is None:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            user_id = _decode_token(auth[7:])

    if user_id is not None:
        user = db.get_user_by_id(user_id)
        if user is not None:
            user_id = int(user["id"])
            request.state.user_id = user_id
            request.state.user_email = user["email"]

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
        response.set_cookie(
            "workspace",
            workspace["slug"],
            httponly=True,
            samesite="lax",
            max_age=WORKSPACE_MAX_AGE,
        )

    return response
