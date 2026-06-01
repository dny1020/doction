"""doction — FastAPI + HTMX markdown wiki."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER, HTTP_404_NOT_FOUND

from app import db, seed
from app.markdown import render_markdown

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
SESSION_MAX_AGE = 60 * 60 * 24 * 7
WORKSPACE_MAX_AGE = 60 * 60 * 24 * 30


@asynccontextmanager
async def lifespan(_: FastAPI):
    app.state.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
    db.init_db()
    seed.seed_if_empty()
    yield


app = FastAPI(title="doction", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        200_000,
    )
    return f"{salt}${digest.hex()}"


def _verify_password(password: str, hashed: str) -> bool:
    try:
        salt, digest = hashed.split("$", 1)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        200_000,
    ).hex()
    return hmac.compare_digest(candidate, digest)


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
    target = new_slug or slug
    return RedirectResponse(f"/pages/{target}", status_code=HTTP_303_SEE_OTHER)


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
    request.state.user_id = None
    request.state.user_email = None
    request.state.workspaces = []
    request.state.workspace = None

    user_id = _get_user_id(request)
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
