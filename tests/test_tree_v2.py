"""Tests del modelo v2: mover, renombrar con alias, captura y feed.

Cubre lo que SPEC.md especifica: el árbol ya existía, así que lo que se prueba
aquí es que mover sea seguro (ciclos), que renombrar no rompa los [[wikilinks]]
y que la captura rápida no colapse ni la nomenclatura ni la barra lateral.
"""


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


# ── mover ────────────────────────────────────────────────────────────────────


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
    """parent_id no tiene restricción contra bucles y el DFS del árbol colgaría."""
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


# ── renombrar ────────────────────────────────────────────────────────────────


def test_rename_keeps_old_slug_resolving(client):
    """El alias es lo que evita reescribir el markdown de terceros."""
    token = _token(client)
    page = _create(client, token, title="Kamailio", content="notas de SIP")

    r = client.post(
        f"/api/pages/{page['slug']}/rename", json={"slug": "kamailio-sbc"}, headers=_h(token)
    )
    assert r.status_code == 200, r.text
    assert r.json()["slug"] == "kamailio-sbc"

    # El slug nuevo responde...
    assert client.get("/api/pages/kamailio-sbc", headers=_h(token)).status_code == 200
    # ...y el anterior sigue resolviendo a la misma página.
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

    # "uno" quedó como alias: una página nueva no puede quedarse con ese slug.
    otra = _create(client, token, title="Otra", content="y", slug="uno")
    assert otra["slug"] != "uno"


def test_forward_reference_resolves_when_target_is_created(client):
    """Un enlace escrito antes que su destino no puede quedar roto para siempre."""
    token = _token(client)
    _create(client, token, title="Adelantada", content="apunto a [[futura]]")

    # Al crearla, create_page rellena el dst_page_id pendiente.
    _create(client, token, title="Futura", content="ya existo", slug="futura")

    r = client.get("/api/pages/futura/view", headers=_h(token))
    assert r.status_code == 200
    assert any(b["slug"] == "adelantada" for b in r.json()["backlinks"])


# ── captura ──────────────────────────────────────────────────────────────────


def test_capture_without_title_derives_one(client):
    token = _token(client)
    created = _create(client, token, content="Descubri que ntfy tiene cliente iOS")
    assert created["title"] == "Descubri que ntfy tiene cliente iOS"


def test_capture_without_title_does_not_collide(client):
    """Sin esto, cien capturas darian untitled-2 … untitled-101."""
    token = _token(client)
    slugs = {_create(client, token, content="")["slug"] for _ in range(5)}
    assert len(slugs) == 5
    assert not any(s.startswith("untitled") for s in slugs)


# ── feed y árbol ─────────────────────────────────────────────────────────────


def test_memos_are_in_the_feed_and_out_of_the_tree(client):
    token = _token(client)
    _create(client, token, title="Doc normal", content="soy documentacion")
    _create(client, token, content="---\ntype: memo\n---\nsoy una captura")

    feed = client.get("/api/notes", headers=_h(token)).json()
    assert len(feed) == 1
    assert feed[0]["excerpt"]

    # El registro siembra páginas de ejemplo, así que se comprueba la ausencia
    # del memo, no el tamaño del árbol.
    tree = client.get("/api/pages", headers=_h(token)).json()
    slugs = {p["slug"] for p in tree}
    assert "doc-normal" in slugs
    assert feed[0]["slug"] not in slugs


def test_feed_paginates_by_cursor(client):
    token = _token(client)
    for i in range(3):
        _create(client, token, content=f"---\ntype: memo\n---\nnota {i}")

    page1 = client.get("/api/notes?limit=2", headers=_h(token)).json()
    assert len(page1) == 2
    # Orden descendente por fecha de creación.
    assert page1[0]["created_at"] >= page1[1]["created_at"]

    page2 = client.get(
        f"/api/notes?limit=2&before={page1[-1]['created_at']}", headers=_h(token)
    ).json()
    assert all(n["slug"] not in {p["slug"] for p in page1} for n in page2)


# ── children ─────────────────────────────────────────────────────────────────


def test_children_lists_direct_descendants_only(client):
    token = _token(client)
    raiz = _create(client, token, title="Raiz", content="x")
    hijo = _create(client, token, title="Hijo3", content="y", parent_slug=raiz["slug"])
    _create(client, token, title="Nieto", content="z", parent_slug=hijo["slug"])

    kids = client.get(f"/api/pages/{raiz['slug']}/children", headers=_h(token)).json()
    assert [k["slug"] for k in kids] == [hijo["slug"]]
