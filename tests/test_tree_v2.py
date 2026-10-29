"""Move (cycle-safe), rename with aliases, untitled pages and children."""


def _token(client, email="v2@example.com", password="password123") -> str:
    client.post("/api/auth/register", json={"email": email, "password": password})
    r = client.post("/api/tokens", json={"name": "test"})
    return r.json()["token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create(client, token, **body) -> dict:
    r = client.post("/api/pages", json=body, headers=_h(token))
    assert r.status_code == 201, r.text
    return r.json()


# ── move ─────────────────────────────────────────────────────────────────────


def test_move_reparents_and_keeps_slug(client):
    token = _token(client)
    parent = _create(client, token, title="Homelab", content="raiz")
    child = _create(client, token, title="MikroTik", content="notas")

    r = client.post(
        f"/api/pages/{child['slug']}/move",
        json={"parent_slug": parent["slug"]},
        headers=_h(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["slug"] == child["slug"]

    page = client.get(f"/api/pages/{child['slug']}", headers=_h(token)).json()
    assert page["parent_slug"] == parent["slug"]


def test_move_to_root_with_null_parent(client):
    token = _token(client)
    parent = _create(client, token, title="Padre", content="x")
    child = _create(client, token, title="Hijo", content="y", parent_slug=parent["slug"])

    r = client.post(f"/api/pages/{child['slug']}/move", json={}, headers=_h(token))
    assert r.status_code == 200
    assert (
        client.get(f"/api/pages/{child['slug']}", headers=_h(token)).json()["parent_slug"] is None
    )


def test_move_rejects_cycle(client):
    """parent_id has no constraint against cycles, and the tree's DFS would hang."""
    token = _token(client)
    abuelo = _create(client, token, title="Abuelo", content="x")
    padre = _create(client, token, title="Padre2", content="y", parent_slug=abuelo["slug"])

    r = client.post(
        f"/api/pages/{abuelo['slug']}/move",
        json={"parent_slug": padre["slug"]},
        headers=_h(token),
    )
    assert r.status_code == 400
    assert "descendant" in r.json()["detail"]


def test_move_rejects_self(client):
    token = _token(client)
    page = _create(client, token, title="Sola", content="x")
    r = client.post(
        f"/api/pages/{page['slug']}/move",
        json={"parent_slug": page["slug"]},
        headers=_h(token),
    )
    assert r.status_code == 400


def test_move_unknown_parent_is_400(client):
    token = _token(client)
    page = _create(client, token, title="Suelta", content="x")
    r = client.post(
        f"/api/pages/{page['slug']}/move",
        json={"parent_slug": "no-existe"},
        headers=_h(token),
    )
    assert r.status_code == 400


# ── rename ───────────────────────────────────────────────────────────────────


def test_rename_keeps_old_slug_resolving(client):
    """The alias is what avoids rewriting other pages' markdown."""
    token = _token(client)
    page = _create(client, token, title="Kamailio", content="notas de SIP")

    r = client.post(
        f"/api/pages/{page['slug']}/rename", json={"slug": "kamailio-sbc"}, headers=_h(token)
    )
    assert r.status_code == 200, r.text
    assert r.json()["slug"] == "kamailio-sbc"

    # The new slug answers...
    assert client.get("/api/pages/kamailio-sbc", headers=_h(token)).status_code == 200
    # ...and the old one still resolves to the same page.
    old = client.get(f"/api/pages/{page['slug']}", headers=_h(token))
    assert old.status_code == 200
    assert old.json()["slug"] == "kamailio-sbc"


def test_rename_preserves_backlinks(client):
    token = _token(client)
    destino = _create(client, token, title="Destino", content="soy el destino")
    _create(client, token, title="Origen", content=f"enlazo a [[{destino['slug']}]]")

    client.post(
        f"/api/pages/{destino['slug']}/rename", json={"slug": "destino-nuevo"}, headers=_h(token)
    )

    r = client.get("/api/pages/destino-nuevo/view", headers=_h(token))
    assert r.status_code == 200
    assert any(b["slug"] == "origen" for b in r.json()["backlinks"])


def test_rename_cannot_steal_an_alias(client):
    token = _token(client)
    page = _create(client, token, title="Uno", content="x")
    client.post(f"/api/pages/{page['slug']}/rename", json={"slug": "dos"}, headers=_h(token))

    # "uno" is now an alias, so a new page cannot take that slug.
    otra = _create(client, token, title="Otra", content="y", slug="uno")
    assert otra["slug"] != "uno"


def test_forward_reference_resolves_when_target_is_created(client):
    """A link written before its target must not stay broken forever."""
    token = _token(client)
    _create(client, token, title="Adelantada", content="apunto a [[futura]]")

    # Creating it fills the pending dst_page_id.
    _create(client, token, title="Futura", content="ya existo", slug="futura")

    r = client.get("/api/pages/futura/view", headers=_h(token))
    assert r.status_code == 200
    assert any(b["slug"] == "adelantada" for b in r.json()["backlinks"])


# ── untitled pages ───────────────────────────────────────────────────────────


def test_capture_without_title_derives_one(client):
    token = _token(client)
    created = _create(client, token, content="Descubri que ntfy tiene cliente iOS")
    assert created["title"] == "Descubri que ntfy tiene cliente iOS"


def test_capture_without_title_does_not_collide(client):
    """Without this, a hundred captures would be untitled-2 … untitled-101."""
    token = _token(client)
    slugs = {_create(client, token, content="")["slug"] for _ in range(5)}
    assert len(slugs) == 5
    assert not any(s.startswith("untitled") for s in slugs)


# ── tree ─────────────────────────────────────────────────────────────────────


def test_a_memo_page_is_an_ordinary_page_in_the_tree(client):
    """Captures made before the inbox was removed still carry `type: memo`; they must
    show up in the tree rather than vanish."""
    token = _token(client)
    memo = _create(client, token, content="---\ntype: memo\n---\nrevisar el router")

    tree = client.get("/api/pages", headers=_h(token)).json()
    assert memo["slug"] in {p["slug"] for p in tree}


# ── children ─────────────────────────────────────────────────────────────────


def test_children_lists_direct_descendants_only(client):
    token = _token(client)
    raiz = _create(client, token, title="Raiz", content="x")
    hijo = _create(client, token, title="Hijo3", content="y", parent_slug=raiz["slug"])
    _create(client, token, title="Nieto", content="z", parent_slug=hijo["slug"])

    kids = client.get(f"/api/pages/{raiz['slug']}/children", headers=_h(token)).json()
    assert [k["slug"] for k in kids] == [hijo["slug"]]
