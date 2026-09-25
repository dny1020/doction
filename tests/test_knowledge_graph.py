"""Wikilink graph: the parser, the edges and the structural analysis.

The cases covered are the ones that break a graph: code that looks like a link, a deleted
page leaving holes, a cycle, a self-link. Renames and forward references live in
test_tree_v2.
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


# ── the parser ───────────────────────────────────────────────────────────────


def test_wikilink_inside_a_fence_is_not_a_link():
    """Documenting the syntax is not using it: wikilinks inside a code block link nothing."""
    content = "Se escriben así:\n\n```\n[[no-soy-un-enlace]]\n```\n\npero [[si-lo-soy]] sí."
    assert meta.extract_links(content) == ["si-lo-soy"]


def test_wikilink_inside_inline_code_is_not_a_link():
    content = "El literal `[[plantilla]]` no enlaza; [[real]] sí."
    assert meta.extract_links(content) == ["real"]


def test_malformed_wikilinks_are_ignored():
    for content in ("[[sin cerrar", "[[]]", "[[   ]]", "[ [espaciado] ]", "]]invertido[["):
        assert meta.extract_links(content) == [], content


def test_repeated_target_yields_one_edge():
    """The graph has edges, not mentions: linking three times is one relation."""
    content = "[[destino]] y otra vez [[destino]] y [[destino|con texto]]."
    assert meta.extract_links(content) == ["destino"]


def test_target_is_trimmed_and_label_discarded():
    assert meta.extract_links("[[  espacios  |  etiqueta  ]]") == ["espacios"]


# ── edges ────────────────────────────────────────────────────────────────────


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
    """Deleting the target keeps the link: a broken link is the only sign someone
    expected that page to exist."""
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


# ── The analysis ─────────────────────────────────────────────────────────────


def test_link_insights_terminates_on_a_cycle(client, main_module):
    """PageRank converges on a cycle, keeping all three pages and returning something usable."""
    token = _token(client)
    _create(client, token, title="Uno", content="voy a [[dos]]")
    _create(client, token, title="Dos", content="voy a [[tres]]")
    _create(client, token, title="Tres", content="vuelvo a [[uno]]")

    wid = int(main_module.db.list_workspaces(1)[0].id)
    out = graph.link_insights(wid)
    central = {p["slug"] for p in out["central"]}
    assert {"uno", "dos", "tres"} <= central
    # Registration seeds example pages, so there are other orphans; what matters is
    # that none of the cycle's pages is one.
    orphans = {p["slug"] for p in out["orphans"]}
    assert orphans.isdisjoint({"uno", "dos", "tres"})


def test_a_self_link_is_not_a_relation(client, main_module):
    """A page that links to itself is still alone."""
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


# ── The indexes ──────────────────────────────────────────────────────────────


def test_both_directions_of_the_graph_are_indexed(client, main_module):
    """Both graph questions are answered by index; without these, every read scans the table."""
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
    assert "page_links_src_idx" in idx  # what I link to
    assert "page_links_dst_idx" in idx  # what links to me, by slug, still unresolved
    assert "page_links_dst_page_idx" in idx  # what links to me, resolved


# ── A mention's context ──────────────────────────────────────────────────────


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
    # The marked text is the label the reader sees, not `[[failover]]`.
    assert [p["text"] for p in mention["context"] if p["match"]] == ["el procedimiento"]


def test_mention_context_carries_no_markup(client):
    """Context travels as text spans, so a quoted page cannot inject elements into this one."""
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
    """A link written against an older slug is still a true mention; only the sentence is lost."""
    token = _token(client)
    destino = _create(client, token, title="Destino", content="soy el destino")
    _create(client, token, title="Origen", content=f"apunto a [[{destino['slug']}]]")
    client.post(
        f"/api/pages/{destino['slug']}/rename", json={"slug": "destino-nuevo"}, headers=_h(token)
    )

    r = client.get("/api/pages/destino-nuevo/view", headers=_h(token))
    mention = next(b for b in r.json()["backlinks"] if b["slug"] == "origen")
    assert mention["title"] == "Origen"


# ── the graph endpoint ───────────────────────────────────────────────────────


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
    """The broken edge is returned whole; dropping it would show everything as connected."""
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
    # The most-linked page survives the trim: that is what trimming by PageRank is for.
    assert "centro" in {n["slug"] for n in small["nodes"]}


def test_graph_needs_authentication(client):
    assert client.get("/api/graph").status_code == 401
