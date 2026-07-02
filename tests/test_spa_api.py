"""Tests de los endpoints JSON que alimentan la SPA de React (Fase 1)."""

from __future__ import annotations


def _register(client, email="user@example.com", password="password123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def test_me_requires_session(client):
    assert client.get("/api/me").status_code == 401


def test_register_then_me(client):
    r = _register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "user@example.com"
    assert body["active_workspace"]["slug"] == "personal"
    assert len(body["workspaces"]) == 1

    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"


def test_register_validation(client):
    assert _register(client, password="short").status_code == 400
    assert _register(client, email="not-an-email").status_code == 400
    _register(client)
    assert _register(client).status_code == 409  # duplicado


def test_logout_clears_session(client):
    _register(client)
    assert client.get("/api/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/me").status_code == 401


def test_login_roundtrip(client):
    _register(client)
    client.post("/api/auth/logout")
    ok = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert ok.status_code == 200
    assert ok.json()["email"] == "user@example.com"
    assert client.get("/api/me").status_code == 200


def test_login_wrong_password(client):
    _register(client)
    client.post("/api/auth/logout")
    bad = client.post("/api/auth/login", json={"email": "user@example.com", "password": "nope"})
    assert bad.status_code == 401


def test_switch_workspace(client):
    _register(client)
    client.post("/api/workspaces", json={"name": "Work"})
    me = client.get("/api/me").json()
    other = [w for w in me["workspaces"] if w["slug"] != "personal"][0]
    r = client.post(f"/api/workspaces/{other['slug']}/switch")
    assert r.status_code == 200
    assert r.json()["slug"] == other["slug"]
    assert client.post("/api/workspaces/does-not-exist/switch").status_code == 404


def test_page_view(client):
    _register(client)  # siembra páginas de ejemplo
    r = client.get("/api/pages/welcome-to-doction/view")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "welcome-to-doction"
    assert "content" in body
    for key in ("breadcrumbs", "children", "backlinks", "related"):
        assert isinstance(body[key], list)
    assert client.get("/api/pages/nope/view").status_code == 404


# ── Fase 2: settings, papelera, historial/restaurar, workspaces ──────────────

def test_update_profile(client):
    _register(client)
    r = client.post(
        "/api/settings/profile",
        json={"display_name": "Ada", "avatar_color": "#4a7fc0"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "Ada"
    assert body["avatar_color"] == "#4a7fc0"
    # Un color fuera de la paleta se ignora (queda en automático).
    r2 = client.post("/api/settings/profile", json={"display_name": "Ada", "avatar_color": "#000"})
    assert r2.json()["avatar_color"] is None


def test_update_password(client):
    _register(client)
    # Contraseña actual incorrecta.
    bad = client.post(
        "/api/settings/password",
        json={
            "current_password": "nope",
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        },
    )
    assert bad.status_code == 400
    # Confirmación que no coincide.
    mism = client.post(
        "/api/settings/password",
        json={
            "current_password": "password123",
            "new_password": "newpass123",
            "confirm_password": "other",
        },
    )
    assert mism.status_code == 400
    # Cambio correcto y login con la nueva contraseña.
    ok = client.post(
        "/api/settings/password",
        json={
            "current_password": "password123",
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        },
    )
    assert ok.status_code == 200
    client.post("/api/auth/logout")
    relogin = client.post(
        "/api/auth/login", json={"email": "user@example.com", "password": "newpass123"}
    )
    assert relogin.status_code == 200


def test_trash_restore_and_purge(client):
    _register(client)  # siembra páginas
    slug = "welcome-to-doction"
    assert client.delete(f"/api/pages/{slug}").status_code == 204
    trash = client.get("/api/trash").json()
    assert any(p["slug"] == slug for p in trash)
    # Restaurar la saca de la papelera y la vuelve visible.
    assert client.post(f"/api/trash/{slug}/restore").status_code == 200
    assert all(p["slug"] != slug for p in client.get("/api/trash").json())
    assert client.get(f"/api/pages/{slug}/view").status_code == 200
    # Borrar de nuevo y purgar definitivamente.
    client.delete(f"/api/pages/{slug}")
    assert client.post(f"/api/trash/{slug}/purge").status_code == 204
    assert all(p["slug"] != slug for p in client.get("/api/trash").json())


def test_restore_version(client):
    _register(client)
    created = client.post("/api/pages", json={"title": "Notes", "content": "version one"})
    slug = created.json()["slug"]
    client.put(f"/api/pages/{slug}", json={"content": "version two"})
    history = client.get(f"/api/pages/{slug}/history").json()
    assert len(history) >= 2
    old_sha = history[-1]["sha"]  # el commit más antiguo = "version one"
    assert client.post(f"/api/pages/{slug}/restore/{old_sha}").status_code == 200
    assert "version one" in client.get(f"/api/pages/{slug}").json()["content"]


def test_workspace_rename_and_delete(client):
    _register(client)
    client.post("/api/workspaces", json={"name": "Work"})
    me = client.get("/api/me").json()
    work = [w for w in me["workspaces"] if w["slug"] != "personal"][0]
    # Renombrar.
    r = client.put(f"/api/workspaces/{work['slug']}", json={"name": "Job"})
    assert r.status_code == 200
    assert any(w["name"] == "Job" for w in client.get("/api/me").json()["workspaces"])
    # Borrar.
    assert client.delete(f"/api/workspaces/{work['slug']}").status_code == 200
    assert all(w["slug"] != work["slug"] for w in client.get("/api/me").json()["workspaces"])
    # No se puede borrar el último workspace que queda.
    last = client.get("/api/me").json()["workspaces"][0]
    assert client.delete(f"/api/workspaces/{last['slug']}").status_code == 400


def test_i18n_catalog_default_english(client):
    r = client.get("/api/i18n")  # público: no requiere sesión
    assert r.status_code == 200
    body = r.json()
    assert body["lang"] == "en"
    assert "es" in body["langs"]
    assert body["t"]["settings"] == "Settings"


def test_set_language_switches_catalog(client):
    assert client.post("/api/lang/es").status_code == 200
    body = client.get("/api/i18n").json()
    assert body["lang"] == "es"
    assert body["t"]["settings"] == "Configuración"
    # Un idioma no soportado se rechaza.
    assert client.post("/api/lang/zz").status_code == 400
