"""MiniDocMost — FastAPI + HTMX markdown wiki."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import os
from pathlib import Path
import secrets

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import jwt
from starlette.status import HTTP_303_SEE_OTHER, HTTP_404_NOT_FOUND

from app import db, seed
from app.markdown import render_markdown

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    app.state.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
    db.init_db()
    seed.seed_if_empty()
    yield


app = FastAPI(title="MiniDocMost", lifespan=lifespan)
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
    user_id = _get_user_id(request)
    if user_id is None:
        return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
    return user_id


def _sidebar_pages(user_id: int):
    return db.list_pages(user_id)


def _not_found(request: Request, slug: str) -> HTMLResponse:
    user_id = _get_user_id(request)
    return templates.TemplateResponse(
        request,
        "not_found.html",
        {
            "pages": _sidebar_pages(user_id) if user_id else [],
            "slug": slug,
            "user_email": request.state.user_email,
        },
        status_code=HTTP_404_NOT_FOUND,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    user_id = _get_user_id(request)
    if user_id is None:
        return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
    page = db.latest_page(user_id)
    if page is None:
        return templates.TemplateResponse(
            request,
            "empty.html",
            {"pages": _sidebar_pages(user_id), "user_email": request.state.user_email},
        )
    return templates.TemplateResponse(
        request,
        "page.html",
        {
            "pages": _sidebar_pages(user_id),
            "page": page,
            "rendered": render_markdown(page["content"]),
            "active_slug": page["slug"],
            "user_email": request.state.user_email,
        },
    )


@app.get("/new", response_class=HTMLResponse)
async def new_page_form(request: Request) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    return templates.TemplateResponse(
        request,
        "new.html",
        {
            "pages": _sidebar_pages(user_id),
            "active_slug": None,
            "user_email": request.state.user_email,
        },
    )


@app.post("/pages")
async def create_page_authed(
    request: Request, title: str = Form(...), content: str = Form("")
) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    slug = db.create_page(user_id, title, content)
    return RedirectResponse(f"/pages/{slug}", status_code=HTTP_303_SEE_OTHER)


@app.get("/pages/{slug}", response_class=HTMLResponse)
async def read_page(request: Request, slug: str) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    page = db.get_page(slug, user_id)
    if page is None:
        return _not_found(request, slug)
    return templates.TemplateResponse(
        request,
        "page.html",
        {
            "pages": _sidebar_pages(user_id),
            "page": page,
            "rendered": render_markdown(page["content"]),
            "active_slug": slug,
            "user_email": request.state.user_email,
        },
    )


@app.get("/pages/{slug}/edit", response_class=HTMLResponse)
async def edit_page_form(request: Request, slug: str) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    page = db.get_page(slug, user_id)
    if page is None:
        return _not_found(request, slug)
    return templates.TemplateResponse(
        request,
        "edit.html",
        {
            "pages": _sidebar_pages(user_id),
            "page": page,
            "active_slug": slug,
            "user_email": request.state.user_email,
        },
    )


@app.post("/pages/{slug}")
async def update_page(
    request: Request, slug: str, title: str = Form(...), content: str = Form("")
) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    new_slug = db.update_page(user_id, slug, title, content)
    target = new_slug or slug
    return RedirectResponse(f"/pages/{target}", status_code=HTTP_303_SEE_OTHER)


@app.post("/pages/{slug}/delete")
async def remove_page(request: Request, slug: str) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    db.delete_page(user_id, slug)
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
    results = db.search_pages(user_id, q) if q.strip() else []
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
    if _get_user_id(request) is not None:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"pages": [], "active_slug": None, "user_email": None},
    )


@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)) -> Response:
    user = db.get_user_by_email(email.strip().lower())
    if user is None or not _verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"pages": [], "active_slug": None, "error": "Invalid credentials."},
            status_code=400,
        )
    token = _encode_token(int(user["id"]))
    response = RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    response.set_cookie("session", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7)
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_form(request: Request) -> Response:
    if _get_user_id(request) is not None:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "register.html",
        {"pages": [], "active_slug": None, "user_email": None},
    )


@app.post("/register")
async def register(request: Request, email: str = Form(...), password: str = Form(...)) -> Response:
    email = email.strip().lower()
    if not email or "@" not in email:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"pages": [], "active_slug": None, "error": "Enter a valid email."},
            status_code=400,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"pages": [], "active_slug": None, "error": "Password must be 8+ chars."},
            status_code=400,
        )
    if db.get_user_by_email(email) is not None:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"pages": [], "active_slug": None, "error": "Email already registered."},
            status_code=400,
        )
    user_id = db.create_user(email, _hash_password(password))
    db.claim_unowned_pages(user_id)
    for title, content in seed.SEED_PAGES:
        db.create_page(user_id, title, content)
    token = _encode_token(user_id)
    response = RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    response.set_cookie("session", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7)
    return response


@app.post("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
    response.delete_cookie("session")
    return response


@app.middleware("http")
async def attach_user(request: Request, call_next):
    request.state.user_email = None
    user_id = _get_user_id(request)
    if user_id is not None:
        user = db.get_user_by_id(user_id)
        if user is not None:
            request.state.user_email = user["email"]
    return await call_next(request)
