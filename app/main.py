from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import io
import logging
import os
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
from pydantic import BaseModel
from starlette.status import HTTP_303_SEE_OTHER

from app import db, embeddings, git_repo, i18n, mcp, seed
from app.auth import (
    TOKEN_PREFIX,
    generate_api_token,
    hash_api_token,
)
from app.auth import hash_password as _hash_password
from app.auth import verify_password as _verify_password
from app.models import Workspace

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
SESSION_MAX_AGE = 60 * 60 * 24 * 7
WORKSPACE_MAX_AGE = 60 * 60 * 24 * 30
LANG_MAX_AGE = 60 * 60 * 24 * 365
# Activo solo detrás de TLS; por defecto apagado para que dev http no requiera configuración.
SECURE_COOKIES = os.environ.get("SECURE_COOKIES", "").lower() in {"1", "true", "yes"}
# Cierra el registro web en instancias públicas. El primer usuario (bootstrap de primer
# arranque) siempre puede crearse para no dejar la instancia inaccesible; los demás se
# dan de alta con scripts/create_user.py.
DISABLE_REGISTRATION = os.environ.get("DISABLE_REGISTRATION", "").lower() in {"1", "true", "yes"}

# Cabeceras de seguridad fijadas en cada respuesta (defensa en profundidad).
# CSP pragmática: 'unsafe-inline' en script-src sigue siendo necesario porque base.html
# tiene JS inline y handlers onclick, y Lucide carga desde unpkg. El XSS real ya queda
# tapado al renderizar CommonMark plano (markdown.py html=False); la CSP es capa extra.
# Endurecer a futuro: vendorizar Lucide + externalizar el JS inline para quitar 'unsafe-inline'.
_CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline' https://unpkg.com; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": _CSP,
}

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
    return int(ws.id)


@api_router.post("/token")
def api_token(body: _TokenIn):
    user = db.get_user_by_email(body.email.strip().lower())
    if user is None or not _verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": _encode_token(int(user.id)), "token_type": "bearer"}


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
    return [dataclasses.asdict(t) for t in db.list_api_tokens(uid)]


@api_router.delete("/tokens/{token_id}", status_code=204)
def api_revoke_token(request: Request, token_id: int):
    uid = _api_user(request)
    if not db.revoke_api_token(uid, token_id):
        raise HTTPException(status_code=404, detail="Token not found")


@api_router.get("/workspaces")
def api_list_workspaces(request: Request):
    uid = _api_user(request)
    # Construimos el dict a mano para devolver solo estos campos (no user_id, etc.).
    return [
        {"id": w.id, "slug": w.slug, "name": w.name, "role": w.role}
        for w in db.list_workspaces(uid)
    ]


@api_router.post("/workspaces", status_code=201)
def api_create_workspace(request: Request, body: _WorkspaceIn):
    uid = _api_user(request)
    slug = db.create_workspace(uid, body.name)
    return {"slug": slug, "name": body.name.strip() or "Workspace"}


def _api_owned_workspace(request: Request, uid: int, slug: str) -> Workspace:
    """Resuelve el workspace por slug exigiendo que el usuario sea owner."""
    ws = db.get_workspace_by_slug(uid, slug)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.role != "owner":
        raise HTTPException(status_code=403, detail="Owner role required")
    return ws


@api_router.put("/workspaces/{slug}")
def api_rename_workspace(request: Request, slug: str, body: _WorkspaceIn):
    uid = _api_user(request)
    _api_owned_workspace(request, uid, slug)  # exige ser owner
    if not db.rename_workspace(uid, slug, body.name):
        raise HTTPException(status_code=400, detail="Enter a valid name")
    return {"slug": slug, "name": body.name.strip()}


@api_router.delete("/workspaces/{slug}")
def api_delete_workspace(request: Request, slug: str) -> Response:
    uid = _api_user(request)
    _api_owned_workspace(request, uid, slug)  # exige ser owner
    if not db.delete_workspace(uid, slug):
        raise HTTPException(status_code=400, detail="Cannot delete your only workspace")
    response = JSONResponse({"slug": slug, "ok": True})
    # Si se borró el workspace activo, mover la cookie a uno que quede.
    if request.cookies.get("workspace") == slug:
        remaining = db.list_workspaces(uid)
        if remaining:
            _ws_cookie(response, remaining[0].slug)
    return response


@api_router.get("/workspaces/{slug}/members")
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


@api_router.post("/workspaces/{slug}/members", status_code=201)
def api_add_member(request: Request, slug: str, body: _MemberIn):
    uid = _api_user(request)
    ws = _api_owned_workspace(request, uid, slug)
    target = db.get_user_by_email(body.email.strip().lower())
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if db.get_member_role(int(target.id), int(ws.id)) is not None:
        raise HTTPException(status_code=409, detail="Already a member")
    db.add_workspace_member(int(ws.id), int(target.id), "member")
    return {"workspace": slug, "user_id": int(target.id), "role": "member"}


@api_router.delete("/workspaces/{slug}/members/{member_id}", status_code=204)
def api_remove_member(request: Request, slug: str, member_id: int):
    uid = _api_user(request)
    ws = _api_owned_workspace(request, uid, slug)
    if db.get_member_role(member_id, int(ws.id)) == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the owner")
    if not db.remove_workspace_member(int(ws.id), member_id):
        raise HTTPException(status_code=404, detail="Member not found")


@api_router.get("/workspaces/{slug}/export")
def api_export_workspace(request: Request, slug: str) -> Response:
    """Descarga el workspace como zip de archivos markdown (una página por .md)."""
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
    ws_slug = ws.slug if ws else "unknown"
    return git_repo.get_page_history(ws_slug, slug, limit=limit)


@api_router.get("/pages/{slug}/history/{sha}")
def api_page_at_commit(request: Request, slug: str, sha: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, uid, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    ws = db.get_workspace_by_id(wid)
    ws_slug = ws.slug if ws else "unknown"
    content = git_repo.get_page_at_commit(ws_slug, slug, sha)
    if content is None:
        raise HTTPException(status_code=404, detail="Commit not found")
    return {"slug": slug, "sha": sha, "content": content}


@api_router.get("/pages/{slug}/history/{sha}/diff")
def api_page_diff(request: Request, slug: str, sha: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, uid, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    ws = db.get_workspace_by_id(wid)
    ws_slug = ws.slug if ws else "unknown"
    diff = git_repo.diff_page(ws_slug, slug, sha)
    if diff is None:
        raise HTTPException(status_code=404, detail="Commit not found")
    return {"slug": slug, "sha": sha, "diff": diff}


@api_router.get("/pages/{slug}/raw", response_class=PlainTextResponse)
def api_get_page_raw(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, uid, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page.content


@api_router.get("/pages/{slug}")
def api_get_page(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, uid, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    children = db.list_child_pages(uid, wid, int(page.id))
    return {
        "slug": page.slug,
        "title": page.title,
        "content": page.content,
        "parent_slug": page.parent_slug,
        "children": [{"slug": c.slug, "title": c.title} for c in children],
        "created_at": page.created_at,
        "updated_at": page.updated_at,
    }


@api_router.put("/pages/{slug}")
def api_update_page(request: Request, slug: str, body: _PagePatch):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, uid, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    new_title = body.title if body.title is not None else page.title
    new_content = body.content if body.content is not None else page.content
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
        {"slug": r.slug, "title": r.title, "snippet": r.snippet}
        for r in results
    ]


# ── SPA (React) — bootstrap + auth por JSON ──────────────────────────────────
# Estos endpoints alimentan el frontend React (carpeta frontend/). Usan la misma
# cookie de sesión httponly que el sitio Jinja; la SPA llama con
# `fetch(..., {credentials: 'same-origin'})`, así que la cookie viaja sola.

def _workspace_brief(ws) -> dict:
    """Forma mínima de un workspace para el frontend."""
    return {"slug": ws.slug, "name": ws.name, "role": ws.role}


def _me_payload(user_id: int, active_slug: str | None) -> dict:
    """Datos del usuario actual + sus workspaces para arrancar la SPA."""
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


@api_router.get("/me")
def api_me(request: Request):
    user_id = _api_user(request)  # lanza 401 si no hay sesión
    active = getattr(request.state, "workspace", None)
    return _me_payload(user_id, active.slug if active else None)


@api_router.post("/auth/login")
def api_login(request: Request, body: _TokenIn) -> Response:
    email = body.email.strip().lower()
    ip = request.client.host if request.client else "?"
    key = f"{ip}:{email}"
    if _login_too_many(key):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    user = db.get_user_by_email(email)
    if user is None or not _verify_password(body.password, user.password_hash):
        _login_record_failure(key)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    _login_clear(key)
    user_id = int(user.id)
    workspace = db.ensure_default_workspace(user_id)
    response = JSONResponse(_me_payload(user_id, workspace.slug))
    _issue_session(response, user_id, workspace.slug)
    return response


@api_router.post("/auth/register", status_code=201)
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


@api_router.post("/auth/logout")
def api_logout() -> Response:
    response = JSONResponse({"ok": True})
    response.delete_cookie("session")
    response.delete_cookie("workspace")
    return response


@api_router.get("/i18n")
def api_i18n(request: Request):
    """Catálogo de traducciones del idioma activo, para la SPA. Público (también en login)."""
    lang = _lang(request)
    return {"lang": lang, "langs": list(i18n.LANGS), "t": i18n.get_catalog(lang)}


@api_router.post("/lang/{code}")
def api_set_lang(code: str) -> Response:
    """Cambia el idioma de la SPA fijando la misma cookie `lang` que usa el sitio Jinja."""
    if code not in i18n.LANGS:
        raise HTTPException(status_code=400, detail="Unsupported language")
    response = JSONResponse({"lang": code})
    _lang_cookie(response, code)
    return response


@api_router.post("/workspaces/{slug}/switch")
def api_switch_workspace(request: Request, slug: str) -> Response:
    uid = _api_user(request)
    ws = db.get_workspace_by_slug(uid, slug)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    response = JSONResponse(_workspace_brief(ws))
    _ws_cookie(response, ws.slug)
    return response


@api_router.get("/pages/{slug}/view")
def api_page_view(request: Request, slug: str):
    """Todo lo que la vista de lectura de la SPA necesita en una sola llamada."""
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, uid, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    breadcrumbs = db.get_ancestors(int(page.id), uid, wid)
    children = db.list_child_pages(uid, wid, int(page.id))
    related = db.related_pages(uid, wid, slug) or []
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
        "backlinks": [
            {"slug": b.slug, "title": b.title} for b in db.backlinks(uid, wid, slug)
        ],
        "related": [
            {"slug": r.slug, "title": r.title, "shared_tags": r.shared_tags} for r in related
        ],
    }


# ── SPA fase 2: settings (perfil/contraseña), papelera, restaurar versión ────

class _ProfileIn(BaseModel):
    display_name: str = ""
    avatar_color: str = ""


class _PasswordIn(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


@api_router.post("/settings/profile")
def api_update_profile(request: Request, body: _ProfileIn):
    uid = _api_user(request)
    name = body.display_name.strip()[:40]
    color = body.avatar_color if body.avatar_color in AVATAR_COLORS else None
    db.update_user_profile(uid, name or None, color)
    active = getattr(request.state, "workspace", None)
    return _me_payload(uid, active.slug if active else None)


@api_router.post("/settings/password")
def api_update_password(request: Request, body: _PasswordIn):
    uid = _api_user(request)
    user = db.get_user_by_id(uid)
    if user is None or not _verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")
    db.update_user_password(uid, _hash_password(body.new_password))
    return {"ok": True}


@api_router.get("/trash")
def api_trash(request: Request):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    return [
        {"slug": p.slug, "title": p.title, "deleted_at": p.deleted_at}
        for p in db.list_deleted_pages(uid, wid)
    ]


@api_router.post("/trash/{slug}/restore")
def api_trash_restore(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    if not db.restore_page(uid, wid, slug):
        raise HTTPException(status_code=404, detail="Page not found in trash")
    return {"slug": slug, "ok": True}


@api_router.post("/trash/{slug}/purge", status_code=204)
def api_trash_purge(request: Request, slug: str):
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    if not db.purge_page(uid, wid, slug):
        raise HTTPException(status_code=404, detail="Page not found in trash")


@api_router.post("/pages/{slug}/restore/{sha}")
def api_restore_version(request: Request, slug: str, sha: str):
    """Restaura el contenido de una versión antigua (commit git) como nueva versión."""
    uid = _api_user(request)
    wid = _api_workspace(request, uid)
    page = db.get_page(slug, uid, wid)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    ws = db.get_workspace_by_id(wid)
    ws_slug = ws.slug if ws else "default"
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
        db.set_page_git_commit(uid, wid, effective_slug, new_sha)
    return {"slug": effective_slug, "ok": True}


def _commit_page(
    request: Request, uid: int, wid: int, slug: str, title: str, content: str
) -> None:
    ws = getattr(request.state, "workspace", None)
    if ws:
        ws_slug = ws.slug
    else:
        _ws = db.get_workspace_by_id(wid)
        ws_slug = _ws.slug if _ws else "default"
    author = getattr(request.state, "user_email", None) or "user"
    sha = git_repo.commit_page(ws_slug, slug, content, author, f"Save: {title}")
    if sha:
        db.set_page_git_commit(uid, wid, slug, sha)


@asynccontextmanager
async def lifespan(_: FastAPI):
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        if SECURE_COOKIES:
            # SECURE_COOKIES=1 es señal de producción (tras TLS): no arrancar con clave insegura.
            raise RuntimeError(
                "SECRET_KEY must be set when SECURE_COOKIES is enabled — refusing to start "
                "with the insecure dev default in production"
            )
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
        try:
            await embed_task
        except asyncio.CancelledError:
            # Cancelar la tarea lanza esta excepción a propósito; la ignoramos.
            pass


app = FastAPI(title="doction", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Imágenes subidas (pegadas/arrastradas en el editor) viven junto a la BD, no en la imagen.
UPLOADS_DIR = db.db_path().parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

app.include_router(api_router)
app.include_router(mcp.router)

# La SPA de React (carpeta frontend/) se construye en static/app/ y se sirve bajo /app.
SPA_DIR = BASE_DIR / "static" / "app"


@app.get("/app")
@app.get("/app/{full_path:path}")
async def serve_spa(full_path: str = "") -> Response:
    """Sirve la SPA de React.

    Devuelve el archivo pedido si existe (assets como /app/assets/...); en caso
    contrario devuelve index.html, para que al recargar una ruta del lado cliente
    (p. ej. /app/p/mi-pagina) React Router la resuelva.
    """
    if full_path:
        candidate = (SPA_DIR / full_path).resolve()
        # Evita salir de SPA_DIR (path traversal) y solo sirve archivos reales.
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
async def unhandled_error(request: Request, exc: Exception) -> Response:
    """Cualquier excepción no capturada → 500 JSON, sin filtrar el traceback."""
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


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


def _lang(request: Request) -> str:
    return getattr(request.state, "lang", i18n.DEFAULT_LANG)


def _registration_open() -> bool:
    """El registro web puede cerrarse con DISABLE_REGISTRATION; aun así el primer usuario
    siempre puede crearse (bootstrap de primer arranque), o la instancia quedaría inaccesible."""
    return not DISABLE_REGISTRATION or not db.has_users()


def _ws_cookie(response: Response, slug: str) -> None:
    response.set_cookie(
        "workspace", slug,
        httponly=True, samesite="lax", secure=SECURE_COOKIES, max_age=WORKSPACE_MAX_AGE,
    )


def _issue_session(response: Response, user_id: int, ws_slug: str | None = None) -> None:
    """Fija la cookie de sesión (httponly, JWT) y, si se da, la del workspace activo.

    Lo comparten el login/registro web (form) y los endpoints JSON de la SPA.
    """
    response.set_cookie(
        "session", _encode_token(user_id),
        httponly=True, samesite="lax", secure=SECURE_COOKIES, max_age=SESSION_MAX_AGE,
    )
    if ws_slug:
        _ws_cookie(response, ws_slug)


def _lang_cookie(response: Response, lang: str) -> None:
    response.set_cookie(
        "lang", lang,
        httponly=True, samesite="lax", secure=SECURE_COOKIES, max_age=LANG_MAX_AGE,
    )


@app.get("/health")
async def health() -> Response:
    """Liveness + readiness: comprueba que la BD responde. 503 si no."""
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


@app.get("/")
async def home() -> Response:
    """El frontend es la SPA de React, servida en /app."""
    return RedirectResponse("/app/", status_code=HTTP_303_SEE_OTHER)


@app.get("/login")
async def login_redirect() -> Response:
    return RedirectResponse("/app/login", status_code=HTTP_303_SEE_OTHER)


@app.get("/register")
async def register_redirect() -> Response:
    return RedirectResponse("/app/register", status_code=HTTP_303_SEE_OTHER)


@app.post("/api/uploads")
async def upload_image(request: Request, file: UploadFile = File(...)) -> Response:
    """Recibe una imagen (pegada/arrastrada en el editor), la guarda con nombre
    derivado de su hash y devuelve la URL para insertarla como markdown."""
    _api_user(request)  # lanza 401 si no hay sesión
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


# Rate-limit de login en memoria. Single-instance ⇒ basta; se resetea al reiniciar.
# Clave por (ip, email) con ventana deslizante.
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
            user_id = int(user.id)
            request.state.user_id = user_id
            request.state.user_email = user.email
            request.state.user_display_name = user.display_name
            request.state.user_avatar_color = user.avatar_color

            db.ensure_default_workspace(user_id)
            workspaces = db.list_workspaces(user_id)
            request.state.workspaces = workspaces

            requested_slug = request.query_params.get("ws") or request.cookies.get("workspace")
            workspace = None
            if requested_slug:
                for ws in workspaces:
                    if ws.slug == requested_slug:
                        workspace = ws
                        break
            if workspace is None and workspaces:
                workspace = workspaces[0]
            request.state.workspace = workspace

    response = await call_next(request)

    workspace = getattr(request.state, "workspace", None)
    if workspace is not None and request.cookies.get("workspace") != workspace.slug:
        _ws_cookie(response, workspace.slug)

    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    # HSTS solo tras TLS (señal de producción), nunca en dev http.
    if SECURE_COOKIES:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )

    return response
