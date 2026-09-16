"""Tests for collaborative workspaces (membership + owner/member roles)."""


def _register(client, email: str) -> None:
    # Registering logs in; clear the cookie so it cannot leak into the next user.
    client.cookies.clear()
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    client.cookies.clear()


def _token(client, email: str) -> str:
    r = client.post("/api/token", json={"email": email, "password": "password123"})
    return r.json()["token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _default_slug(client, token: str) -> str:
    return client.get("/api/workspaces", headers=_h(token)).json()[0]["slug"]


def _members(client, token: str, slug: str) -> list[dict]:
    return client.get(f"/api/workspaces/{slug}/members", headers=_h(token)).json()


def test_member_sees_and_edits_shared_workspace(client):
    _register(client, "a@test.com")
    _register(client, "b@test.com")
    ta, tb = _token(client, "a@test.com"), _token(client, "b@test.com")
    a_slug = _default_slug(client, ta)

    r = client.post("/api/pages", json={"title": "Shared", "content": "v1"}, headers=_h(ta))
    assert r.status_code == 201
    page_slug = r.json()["slug"]

    # B is not a member yet and cannot see A's workspace.
    b_slugs = {w["slug"] for w in client.get("/api/workspaces", headers=_h(tb)).json()}
    assert a_slug not in b_slugs

    # A adds B as a member.
    r = client.post(
        f"/api/workspaces/{a_slug}/members", json={"email": "b@test.com"}, headers=_h(ta)
    )
    assert r.status_code == 201

    # Now B sees the workspace and reads the page, pointing at it with ?ws=.
    b_slugs = {w["slug"] for w in client.get("/api/workspaces", headers=_h(tb)).json()}
    assert a_slug in b_slugs
    r = client.get(f"/api/pages/{page_slug}?ws={a_slug}", headers=_h(tb))
    assert r.status_code == 200
    assert r.json()["content"] == "v1"

    # B edits (member means CRUD); the git author and updated_by are both B.
    r = client.put(
        f"/api/pages/{page_slug}?ws={a_slug}", json={"content": "v2 by b"}, headers=_h(tb)
    )
    assert r.status_code == 200
    hist = client.get(f"/api/pages/{page_slug}/history?ws={a_slug}", headers=_h(tb)).json()
    assert hist[0]["author"] == "b@test.com"

    import app.db as db_module

    user_a = db_module.get_user_by_email("a@test.com")
    assert user_a is not None
    a_uid = int(user_a.id)
    workspace = db_module.get_workspace_by_slug(a_uid, a_slug)
    assert workspace is not None
    page = db_module.get_page(page_slug, int(workspace.id))
    assert page is not None
    assert page.updated_by_email == "b@test.com"


def test_member_cannot_manage_workspace(client):
    _register(client, "a@test.com")
    _register(client, "b@test.com")
    ta, tb = _token(client, "a@test.com"), _token(client, "b@test.com")
    a_slug = _default_slug(client, ta)
    client.post(f"/api/workspaces/{a_slug}/members", json={"email": "b@test.com"}, headers=_h(ta))

    # B, a member, cannot add or remove members.
    r = client.post(
        f"/api/workspaces/{a_slug}/members", json={"email": "a@test.com"}, headers=_h(tb)
    )
    assert r.status_code == 403

    b_id = next(m["user_id"] for m in _members(client, ta, a_slug) if m["email"] == "b@test.com")
    r = client.delete(f"/api/workspaces/{a_slug}/members/{b_id}", headers=_h(tb))
    assert r.status_code == 403


def test_removing_member_revokes_access(client):
    _register(client, "a@test.com")
    _register(client, "b@test.com")
    ta, tb = _token(client, "a@test.com"), _token(client, "b@test.com")
    a_slug = _default_slug(client, ta)
    page_slug = client.post(
        "/api/pages", json={"title": "Shared", "content": "v1"}, headers=_h(ta)
    ).json()["slug"]
    client.post(f"/api/workspaces/{a_slug}/members", json={"email": "b@test.com"}, headers=_h(ta))

    b_id = next(m["user_id"] for m in _members(client, ta, a_slug) if m["email"] == "b@test.com")
    r = client.delete(f"/api/workspaces/{a_slug}/members/{b_id}", headers=_h(ta))
    assert r.status_code == 204

    # B can no longer see the workspace or read the page by slug.
    b_slugs = {w["slug"] for w in client.get("/api/workspaces", headers=_h(tb)).json()}
    assert a_slug not in b_slugs
    r = client.get(f"/api/pages/{page_slug}?ws={a_slug}", headers=_h(tb))
    assert r.status_code == 404


def test_cannot_remove_owner(client):
    _register(client, "a@test.com")
    ta = _token(client, "a@test.com")
    a_slug = _default_slug(client, ta)
    owner_id = next(m["user_id"] for m in _members(client, ta, a_slug) if m["role"] == "owner")
    r = client.delete(f"/api/workspaces/{a_slug}/members/{owner_id}", headers=_h(ta))
    assert r.status_code == 400


def test_add_unknown_user_is_404(client):
    _register(client, "a@test.com")
    ta = _token(client, "a@test.com")
    a_slug = _default_slug(client, ta)
    r = client.post(
        f"/api/workspaces/{a_slug}/members", json={"email": "ghost@test.com"}, headers=_h(ta)
    )
    assert r.status_code == 404


def test_workspace_slugs_are_globally_unique(client):
    # Two users mean two "Personal" workspaces, and the slugs must not collide —
    # a slug is also a directory name in the git repo.
    _register(client, "a@test.com")
    _register(client, "b@test.com")
    ta, tb = _token(client, "a@test.com"), _token(client, "b@test.com")
    assert _default_slug(client, ta) != _default_slug(client, tb)


# ── The workspace asked for in the URL wins ──────────────────────────────────
# The SPA takes the workspace from the path (/w/<slug>/...) and sends it on every
# request. A ?ws= that does not resolve is an error: falling back silently would show
# a shared link a page from somewhere else instead of saying it is not there.


def test_unknown_workspace_is_404_not_a_fallback(client):
    _register(client, "a@test.com")
    ta = _token(client, "a@test.com")
    client.post("/api/pages", json={"title": "Mine", "content": "x"}, headers=_h(ta))

    r = client.get("/api/pages?ws=no-such-workspace", headers=_h(ta))
    assert r.status_code == 404
    # Without ?ws= the same request still works.
    assert client.get("/api/pages", headers=_h(ta)).status_code == 200


def test_someone_elses_workspace_reads_as_missing(client):
    _register(client, "a@test.com")
    _register(client, "b@test.com")
    ta, tb = _token(client, "a@test.com"), _token(client, "b@test.com")
    a_slug = _default_slug(client, ta)

    r = client.get(f"/api/pages?ws={a_slug}", headers=_h(tb))
    assert r.status_code == 404
    assert client.get("/api/pages?ws=no-such-workspace", headers=_h(tb)).status_code == 404


def test_explicit_workspace_beats_the_cookie(client):
    """Two tabs in different workspaces do not collide: the URL wins."""
    _register(client, "a@test.com")
    ta = _token(client, "a@test.com")
    first = _default_slug(client, ta)
    second = client.post("/api/workspaces", json={"name": "Second"}, headers=_h(ta)).json()["slug"]

    client.post(f"/api/workspaces/{second}/switch", headers=_h(ta))
    client.post("/api/pages", json={"title": "In second", "content": "x"}, headers=_h(ta))

    titles = [p["title"] for p in client.get(f"/api/pages?ws={first}", headers=_h(ta)).json()]
    assert "In second" not in titles
    titles = [p["title"] for p in client.get(f"/api/pages?ws={second}", headers=_h(ta)).json()]
    assert "In second" in titles
