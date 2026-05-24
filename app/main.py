"""MiniDocMost — FastAPI + HTMX markdown wiki."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER, HTTP_404_NOT_FOUND

from app import db, seed
from app.markdown import render_markdown

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    seed.seed_if_empty()
    yield


app = FastAPI(title="MiniDocMost", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _sidebar_pages():
    return db.list_pages()


def _not_found(request: Request, slug: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "not_found.html",
        {"pages": _sidebar_pages(), "slug": slug},
        status_code=HTTP_404_NOT_FOUND,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    page = db.latest_page()
    if page is None:
        return templates.TemplateResponse(request, "empty.html", {"pages": _sidebar_pages()})
    return templates.TemplateResponse(
        request,
        "page.html",
        {
            "pages": _sidebar_pages(),
            "page": page,
            "rendered": render_markdown(page["content"]),
            "active_slug": page["slug"],
        },
    )


@app.get("/new", response_class=HTMLResponse)
async def new_page_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "new.html", {"pages": _sidebar_pages(), "active_slug": None}
    )


@app.post("/pages")
async def create_page(title: str = Form(...), content: str = Form("")) -> RedirectResponse:
    slug = db.create_page(title, content)
    return RedirectResponse(f"/pages/{slug}", status_code=HTTP_303_SEE_OTHER)


@app.get("/pages/{slug}", response_class=HTMLResponse)
async def read_page(request: Request, slug: str) -> HTMLResponse:
    page = db.get_page(slug)
    if page is None:
        return _not_found(request, slug)
    return templates.TemplateResponse(
        request,
        "page.html",
        {
            "pages": _sidebar_pages(),
            "page": page,
            "rendered": render_markdown(page["content"]),
            "active_slug": slug,
        },
    )


@app.get("/pages/{slug}/edit", response_class=HTMLResponse)
async def edit_page_form(request: Request, slug: str) -> HTMLResponse:
    page = db.get_page(slug)
    if page is None:
        return _not_found(request, slug)
    return templates.TemplateResponse(
        request,
        "edit.html",
        {"pages": _sidebar_pages(), "page": page, "active_slug": slug},
    )


@app.post("/pages/{slug}")
async def update_page(
    slug: str, title: str = Form(...), content: str = Form("")
) -> RedirectResponse:
    new_slug = db.update_page(slug, title, content)
    target = new_slug or slug
    return RedirectResponse(f"/pages/{target}", status_code=HTTP_303_SEE_OTHER)


@app.post("/pages/{slug}/delete")
async def remove_page(slug: str) -> RedirectResponse:
    db.delete_page(slug)
    return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)


@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = "") -> HTMLResponse:
    results = db.search_pages(q) if q.strip() else []
    return templates.TemplateResponse(
        request,
        "partials/search_results.html",
        {"results": results, "query": q},
    )


@app.post("/preview", response_class=HTMLResponse)
async def preview(content: str = Form("")) -> HTMLResponse:
    return HTMLResponse(render_markdown(content))
