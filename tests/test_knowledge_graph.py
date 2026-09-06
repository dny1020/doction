"""Tests del grafo de wikilinks: parser, aristas y análisis estructural.

El motor relacional ya existía cuando se abrió el change 006 — `page_links`, el
parser de `meta` y `graph.link_insights` llevaban tiempo funcionando. Lo que no
existía era la prueba de que aguantan los casos que rompen un grafo: código que
parece un enlace, una página borrada que deja huecos, un ciclo, un enlace a sí
misma. Eso es lo que se cubre aquí; renombrado y referencia adelantada ya viven
en test_tree_v2.
"""

from app import graph, meta


def _token(client, email="kg@example.com", password="password123") -> str:
    client.post("/api/auth/register", json={"email": email, "password": password})
    return client.post("/api/tokens", json={"name": "test"}).json()["token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create(client, token, **body) -> dict:
    r = client.post("/api/pages", json=body, headers=_h(token))
    assert r.status_code == 201, r.text
    return r.json()


def _backlinks(client, token, slug) -> list[str]:
    r = client.get(f"/api/pages/{slug}/view", headers=_h(token))
    assert r.status_code == 200, r.text
    return sorted(b["slug"] for b in r.json()["backlinks"])


# ── el parser ────────────────────────────────────────────────────────────────


def test_wikilink_inside_a_fence_is_not_a_link():
    """Documentar la sintaxis no es usarla: una página que explica los wikilinks
    dentro de un bloque de código no debe enlazar a nada."""
    content = "Se escriben así:\n\n```\n[[no-soy-un-enlace]]\n```\n\npero [[si-lo-soy]] sí."
    assert meta.extract_links(content) == ["si-lo-soy"]


def test_wikilink_inside_inline_code_is_not_a_link():
    content = "El literal `[[plantilla]]` no enlaza; [[real]] sí."
    assert meta.extract_links(content) == ["real"]


def test_malformed_wikilinks_are_ignored():
    for content in ("[[sin cerrar", "[[]]", "[[   ]]", "[ [espaciado] ]", "]]invertido[["):
        assert meta.extract_links(content) == [], content


def test_repeated_target_yields_one_edge():
    """El grafo tiene aristas, no menciones: enlazar tres veces a la misma página
    es una sola relación. El conteo de menciones es otra pregunta."""
    content = "[[destino]] y otra vez [[destino]] y [[destino|con texto]]."
    assert meta.extract_links(content) == ["destino"]


def test_target_is_trimmed_and_label_discarded():
    assert meta.extract_links("[[  espacios  |  etiqueta  ]]") == ["espacios"]


# ── las aristas ──────────────────────────────────────────────────────────────


def test_saving_replaces_edges_instead_of_accumulating(client):
    token = _token(client)
    _create(client, token, title="A", content="soy A")
    _create(client, token, title="B", content="soy B")
    origen = _create(client, token, title="Origen", content="voy a [[a]]")

    assert _backlinks(client, token, "a") == ["origen"]

    client.put(
        f"/api/pages/{origen['slug']}", json={"content": "ahora voy a [[b]]"}, headers=_h(token)
    )
    assert _backlinks(client, token, "a") == []
    assert _backlinks(client, token, "b") == ["origen"]


def test_deleting_a_page_drops_its_outgoing_edges(client):
    token = _token(client)
    _create(client, token, title="Destino", content="soy el destino")
    origen = _create(client, token, title="Origen", content="apunto a [[destino]]")

    assert _backlinks(client, token, "destino") == ["origen"]
    client.delete(f"/api/pages/{origen['slug']}", headers=_h(token))
    assert _backlinks(client, token, "destino") == []


def test_deleting_a_target_leaves_the_link_broken_not_dangling(client):
    """Borrar el destino no borra el enlace de quien apuntaba: el enlace roto es
    lo único que dice que alguien contaba con esa página."""
    token = _token(client)
    destino = _create(client, token, title="Destino", content="soy el destino")
    _create(client, token, title="Origen", content="apunto a [[destino]]")

    client.delete(f"/api/pages/{destino['slug']}", headers=_h(token))

    r = client.get("/api/insights", headers=_h(token))
    assert r.status_code == 200
    broken = r.json()["broken_links"]
    assert any(b["target"] == "destino" for b in broken), broken


def test_restoring_a_target_resolves_the_link_again(client):
    token = _token(client)
    destino = _create(client, token, title="Destino", content="soy el destino")
    _create(client, token, title="Origen", content="apunto a [[destino]]")

    client.delete(f"/api/pages/{destino['slug']}", headers=_h(token))
    client.post(f"/api/trash/{destino['slug']}/restore", headers=_h(token))

    assert _backlinks(client, token, "destino") == ["origen"]


# ── el análisis ──────────────────────────────────────────────────────────────


def test_link_insights_terminates_on_a_cycle(client, main_module):
    """PageRank sobre un ciclo converge; lo que se prueba es que ninguna de las
    tres páginas se pierde y que el análisis devuelve algo utilizable."""
    token = _token(client)
    _create(client, token, title="Uno", content="voy a [[dos]]")
    _create(client, token, title="Dos", content="voy a [[tres]]")
    _create(client, token, title="Tres", content="vuelvo a [[uno]]")

    wid = int(main_module.db.list_workspaces(1)[0].id)
    out = graph.link_insights(wid)
    central = {p["slug"] for p in out["central"]}
    assert {"uno", "dos", "tres"} <= central
    # El registro siembra páginas de ejemplo, así que hay más huérfanas; lo que
    # importa es que ninguna del ciclo lo sea.
    orphans = {p["slug"] for p in out["orphans"]}
    assert orphans.isdisjoint({"uno", "dos", "tres"})


def test_a_self_link_is_not_a_relation(client, main_module):
    """Una página que se enlaza a sí misma no deja de estar sola."""
    token = _token(client)
    _create(client, token, title="Sola", content="me cito a mí misma: [[sola]]")

    wid = int(main_module.db.list_workspaces(1)[0].id)
    out = graph.link_insights(wid)
    assert any(p["slug"] == "sola" for p in out["orphans"]), out["orphans"]


def test_broken_link_names_who_points_at_it(client, main_module):
    token = _token(client)
    _create(client, token, title="Origen", content="apunto a [[nunca-escrita]]")

    wid = int(main_module.db.list_workspaces(1)[0].id)
    out = graph.link_insights(wid)
    broken = {b["target"]: b for b in out["broken_links"]}
    assert "nunca-escrita" in broken
    assert "origen" in broken["nunca-escrita"]["sources"]


# ── los índices ──────────────────────────────────────────────────────────────


def test_both_directions_of_the_graph_are_indexed(client, main_module):
    """Las dos preguntas del grafo — quién me enlaza, a quién enlazo — se
    responden por índice. Sin esto, cada vista de lectura escanea la tabla."""
    token = _token(client)
    _create(client, token, title="Destino", content="soy el destino")
    _create(client, token, title="Origen", content="apunto a [[destino]]")

    with main_module.db.connect() as conn:
        idx = {
            r["indexname"]
            for r in conn.execute(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'page_links'"
            ).fetchall()
        }
    assert "page_links_src_idx" in idx  # a quién enlazo
    assert "page_links_dst_idx" in idx  # quién me enlaza (por slug, aún sin resolver)
    assert "page_links_dst_page_idx" in idx  # quién me enlaza (ya resuelto)


# ── el contexto de una mención ───────────────────────────────────────────────


def test_mention_context_is_the_sentence_around_the_link(client):
    token = _token(client)
    _create(client, token, title="Failover", content="soy el destino")
    _create(
        client,
        token,
        title="Runbook",
        content=(
            "Intro que no viene al caso. El fallback usa [[failover|el procedimiento]] "
            "cuando cae el SBC. Y una frase posterior."
        ),
    )

    r = client.get("/api/pages/failover/view", headers=_h(token))
    mention = next(b for b in r.json()["backlinks"] if b["slug"] == "runbook")
    text = "".join(part["text"] for part in mention["context"])
    assert "El fallback usa" in text
    assert "cuando cae el SBC" in text
    assert "Intro que no viene al caso" not in text
    # Lo marcado es la etiqueta que el lector ve, no `[[failover]]`.
    assert [p["text"] for p in mention["context"] if p["match"]] == ["el procedimiento"]


def test_mention_context_carries_no_markup(client):
    """El contexto son tramos de texto: lo que se cita de otra página no puede
    meter elementos en el renderizado de esta."""
    token = _token(client)
    _create(client, token, title="Failover", content="soy el destino")
    _create(
        client,
        token,
        title="Hostil",
        content="<img src=x onerror=alert(1)> mira [[failover]] ahora.",
    )

    r = client.get("/api/pages/failover/view", headers=_h(token))
    mention = next(b for b in r.json()["backlinks"] if b["slug"] == "hostil")
    assert all(isinstance(part["text"], str) for part in mention["context"])
    assert all(set(part) == {"text", "match"} for part in mention["context"])


def test_a_mention_without_a_findable_sentence_still_lists(client):
    """Si el enlace se escribió contra un slug anterior, la mención sigue siendo
    cierta; lo único que falta es la frase."""
    token = _token(client)
    destino = _create(client, token, title="Destino", content="soy el destino")
    _create(client, token, title="Origen", content=f"apunto a [[{destino['slug']}]]")
    client.post(
        f"/api/pages/{destino['slug']}/rename", json={"slug": "destino-nuevo"}, headers=_h(token)
    )

    r = client.get("/api/pages/destino-nuevo/view", headers=_h(token))
    mention = next(b for b in r.json()["backlinks"] if b["slug"] == "origen")
    assert mention["title"] == "Origen"


# ── el endpoint del grafo ────────────────────────────────────────────────────


def test_graph_returns_nodes_and_edges(client):
    token = _token(client)
    _create(client, token, title="Destino", content="soy el destino")
    _create(client, token, title="Origen", content="apunto a [[destino]]")

    g = client.get("/api/graph", headers=_h(token)).json()
    slugs = {n["slug"] for n in g["nodes"]}
    assert {"origen", "destino"} <= slugs
    assert {"source": "origen", "target": "destino", "broken": False} in g["edges"]

    destino = next(n for n in g["nodes"] if n["slug"] == "destino")
    assert destino["incoming"] == 1 and destino["outgoing"] == 0
    assert destino["orphan"] is False


def test_graph_keeps_a_broken_edge_with_its_target(client):
    """La arista rota se devuelve entera. Descartarla dejaría la vista diciendo
    que todo está conectado."""
    token = _token(client)
    _create(client, token, title="Origen", content="apunto a [[nunca-escrita]]")

    g = client.get("/api/graph", headers=_h(token)).json()
    assert {"source": "origen", "target": "nunca-escrita", "broken": True} in g["edges"]
    assert "nunca-escrita" not in {n["slug"] for n in g["nodes"]}


def test_graph_marks_orphans(client):
    token = _token(client)
    _create(client, token, title="Sola", content="no enlazo ni me enlazan")

    g = client.get("/api/graph", headers=_h(token)).json()
    sola = next(n for n in g["nodes"] if n["slug"] == "sola")
    assert sola["orphan"] is True


def test_graph_truncates_by_centrality(client, main_module):
    token = _token(client)
    _create(client, token, title="Centro", content="soy el centro")
    for i in range(6):
        _create(client, token, title=f"Hoja {i}", content="apunto a [[centro]]")

    wid = int(main_module.db.list_workspaces(1)[0].id)
    small = main_module.graph.workspace_graph(wid, limit=3)
    assert len(small["nodes"]) == 3
    assert small["truncated"] is True
    assert small["pages"] > 3
    # La más enlazada no se cae del recorte: para eso se recorta por PageRank.
    assert "centro" in {n["slug"] for n in small["nodes"]}


def test_graph_needs_authentication(client):
    assert client.get("/api/graph").status_code == 401
