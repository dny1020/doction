"""Las cinco herramientas del contrato con los agentes.

Cuatro de lectura y una de escritura. Las de lectura son capacidad que ya existía,
renombrada y con filtros; `upsert_page_section` es nueva y es la que se lleva la
mayor parte de este archivo, porque escribe.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app import db, meta


def _token(client, email="u@test.com") -> str:
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    r = client.post("/api/token", json={"email": email, "password": "password123"})
    return r.json()["token"]


def _call(client, token: str, tool: str, arguments: dict | None = None) -> dict:
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments or {}},
    }
    r = client.post("/api/mcp", json=msg, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    return r.json()["result"]


def _data(result: dict):
    assert not result.get("isError"), result
    return json.loads(result["content"][0]["text"])


def _error(result: dict) -> str:
    assert result.get("isError"), result
    return result["content"][0]["text"]


def _page(client, token: str, title: str, content: str, parent: str | None = None) -> str:
    body: dict = {"title": title, "content": content}
    if parent:
        body["parent_slug"] = parent
    r = client.post("/api/pages", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    return r.json()["slug"]


RUNBOOK = """---
type: runbook
owner: sre
---

# Renovación TLS

Intro del runbook. #tls

## Certbot

Corre `certbot renew --dry-run` y luego recarga nginx.

## Rollback

Restaura el certificado anterior desde el backup.
"""


# ── search_knowledge ─────────────────────────────────────────────────────────


def test_search_knowledge_returns_hybrid_order_with_provenance(client):
    token = _token(client)
    _page(client, token, "Renovación TLS", RUNBOOK)
    _page(client, token, "Café", "Recetas de café, nada que ver.")

    hits = _data(_call(client, token, "search_knowledge", {"query": "certbot"}))
    assert hits
    assert hits[0]["slug"] == "renovacion-tls"
    # La procedencia viaja con el resultado: qué canal lo encontró y en qué puesto.
    assert hits[0]["via"] in ("fts", "semantic", "both")
    assert "lexical_rank" in hits[0] and "vector_rank" in hits[0]
    assert "parts" not in hits[0], "el troceado del resaltado es de la interfaz"


def test_search_knowledge_filters_by_tag(client):
    token = _token(client)
    _page(client, token, "Con etiqueta", "Certbot y renovación. #tls")
    _page(client, token, "Sin etiqueta", "Certbot y renovación, sin etiquetar.")

    todos = _data(_call(client, token, "search_knowledge", {"query": "certbot"}))
    assert {h["slug"] for h in todos} >= {"con-etiqueta", "sin-etiqueta"}

    filtrados = _data(
        _call(client, token, "search_knowledge", {"query": "certbot", "tags": ["tls"]})
    )
    assert [h["slug"] for h in filtrados] == ["con-etiqueta"]


def test_search_knowledge_with_a_tag_that_matches_nothing_returns_empty(client):
    """Un filtro que no deja nada devuelve nada; no cae de vuelta a la lista sin filtrar."""
    token = _token(client)
    _page(client, token, "Renovación TLS", RUNBOOK)
    hits = _data(
        _call(client, token, "search_knowledge", {"query": "certbot", "tags": ["ninguna"]})
    )
    assert hits == []


# ── get_rag_context ──────────────────────────────────────────────────────────


@pytest.fixture()
def semantic_client(main_module, monkeypatch):
    """Cliente con la semántica encendida y el embedder determinista."""
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    monkeypatch.setenv("EMBED_STUB", "1")
    import app.embeddings as emb

    emb.reset_embedder()

    async def _noop():
        return

    monkeypatch.setattr(emb, "enrichment_worker", _noop)
    with TestClient(main_module.app) as c:
        yield c


def test_get_rag_context_carries_the_hierarchy(semantic_client):
    from app import embeddings

    client = semantic_client
    token = _token(client)
    _page(client, token, "Renovación TLS", RUNBOOK)
    embeddings.drain_pending()

    out = _data(_call(client, token, "get_rag_context", {"query": "certbot"}))
    assert out["mode"] == "semantic"
    assert out["chunks"], out
    chunk = out["chunks"][0]
    assert {"slug", "title", "path", "section", "score", "text"} <= set(chunk)
    # `Workspace > Página > Sección`, que es lo que sitúa un fragmento leído solo.
    assert chunk["path"].startswith("Personal > Renovación TLS")
    assert chunk["section"], "el fragmento viene de una sección con encabezado"
    assert chunk["path"].endswith(chunk["section"])


def test_get_rag_context_without_vectors_returns_sections_not_extracts(client):
    """El canal degradado devuelve la sección entera, no el recorte de doce palabras.

    `ts_headline` elige palabras para enseñarle a una persona por qué coincidió un
    resultado. Un agente que recibía eso recibía trozos de frase.
    """
    token = _token(client)
    _page(client, token, "Renovación TLS", RUNBOOK)

    out = _data(_call(client, token, "get_rag_context", {"query": "certbot"}))
    assert out["mode"] == "fts"
    assert out["chunks"], out
    chunk = out["chunks"][0]
    # La sección de Certbot, entera y literal.
    assert chunk["text"] == "Corre `certbot renew --dry-run` y luego recarga nginx."
    assert chunk["section"] == "Renovación TLS > Certbot"
    assert chunk["path"] == "Personal > Renovación TLS > Renovación TLS > Certbot"
    assert "<mark>" not in chunk["text"]


def test_get_rag_context_quotes_and_never_composes(client):
    """Todo fragmento aparece literalmente en una página guardada."""
    token = _token(client)
    _page(client, token, "Renovación TLS", RUNBOOK)
    page = client.get(
        "/api/pages/renovacion-tls", headers={"Authorization": f"Bearer {token}"}
    ).json()["content"]

    out = _data(_call(client, token, "get_rag_context", {"query": "certbot"}))
    for chunk in out["chunks"]:
        assert chunk["text"] in page, chunk["text"]


def test_get_rag_context_rejects_an_empty_query(client):
    """Pedir contexto sin consulta es un error del llamante, no una respuesta vacía."""
    token = _token(client)
    _page(client, token, "Renovación TLS", RUNBOOK)
    assert "query" in _error(_call(client, token, "get_rag_context", {"query": "   "}))


def test_get_rag_context_with_nothing_to_match_returns_empty(client):
    token = _token(client)
    _page(client, token, "Renovación TLS", RUNBOOK)
    out = _data(_call(client, token, "get_rag_context", {"query": "zzzzinexistente"}))
    assert out["chunks"] == []


# ── get_workspace_tree ───────────────────────────────────────────────────────


def test_get_workspace_tree_nests_subpages(client):
    token = _token(client)
    parent = _page(client, token, "Infra", "raíz")
    child = _page(client, token, "Kamailio", "hija", parent=parent)
    _page(client, token, "Dispatcher", "nieta", parent=child)
    _page(client, token, "Runbooks", "otra raíz")

    tree = _data(_call(client, token, "get_workspace_tree"))
    assert tree["workspace"]["slug"]
    by_slug = {p["slug"]: p for p in tree["pages"]}
    assert "infra" in by_slug and "runbooks" in by_slug
    kamailio = by_slug["infra"]["children"][0]
    assert kamailio["slug"] == "kamailio"
    assert kamailio["children"][0]["slug"] == "dispatcher"
    assert by_slug["runbooks"]["children"] == []


# ── read_page_raw ────────────────────────────────────────────────────────────


def test_read_page_raw_returns_the_bytes_a_write_must_preserve(client):
    token = _token(client)
    _page(client, token, "Renovación TLS", RUNBOOK)

    out = _data(_call(client, token, "read_page_raw", {"slug": "renovacion-tls"}))
    assert out["content"] == RUNBOOK
    assert out["content"].startswith("---\n"), "el frontmatter va en su sitio, sin parsear"
    # Y también parseado, para no obligar a analizarlo dos veces.
    assert out["frontmatter"] == {"type": "runbook", "owner": "sre"}
    assert "tls" in out["tags"]


def test_read_page_raw_on_a_missing_page_errors(client):
    token = _token(client)
    assert (
        "not found" in _error(_call(client, token, "read_page_raw", {"slug": "no-existe"})).lower()
    )


# ── upsert_page_section ──────────────────────────────────────────────────────


def test_upsert_replaces_only_its_own_section(client):
    """El resto del documento queda byte a byte igual."""
    token = _token(client)
    _page(client, token, "Renovación TLS", RUNBOOK)

    _data(
        _call(
            client,
            token,
            "upsert_page_section",
            {"slug": "renovacion-tls", "heading": "Certbot", "body": "Nuevo procedimiento."},
        )
    )
    out = _data(_call(client, token, "read_page_raw", {"slug": "renovacion-tls"}))
    content = out["content"]

    assert "Nuevo procedimiento." in content
    assert "certbot renew --dry-run" not in content
    # Lo que no se tocó sigue exactamente donde estaba.
    assert "## Rollback\n\nRestaura el certificado anterior desde el backup." in content
    assert content.startswith("---\ntype: runbook\nowner: sre\n---")
    assert "Intro del runbook. #tls" in content


def test_upsert_adds_a_missing_section_at_the_end(client):
    token = _token(client)
    _page(client, token, "Renovación TLS", RUNBOOK)

    _data(
        _call(
            client,
            token,
            "upsert_page_section",
            {"slug": "renovacion-tls", "heading": "Monitorización", "body": "Alerta a 15 días."},
        )
    )
    content = _data(_call(client, token, "read_page_raw", {"slug": "renovacion-tls"}))["content"]
    assert content.rstrip().endswith("## Monitorización\n\nAlerta a 15 días.")
    assert content.index("## Rollback") < content.index("## Monitorización")


def test_upsert_can_place_a_new_section_under_a_parent(client):
    token = _token(client)
    _page(client, token, "Renovación TLS", RUNBOOK)

    _data(
        _call(
            client,
            token,
            "upsert_page_section",
            {
                "slug": "renovacion-tls",
                "heading": "Comprobación",
                "body": "openssl s_client.",
                "level": 3,
                "parent": "Certbot",
            },
        )
    )
    content = _data(_call(client, token, "read_page_raw", {"slug": "renovacion-tls"}))["content"]
    assert content.index("## Certbot") < content.index("### Comprobación")
    assert content.index("### Comprobación") < content.index("## Rollback")


def test_upsert_refuses_when_two_headings_collide(client):
    """Elegir por el llamante cuál de dos encabezados iguales quería es adivinar."""
    token = _token(client)
    _page(client, token, "Ambigua", "## Setup\n\nuno\n\n## Otra\n\nx\n\n## Setup\n\ndos")

    message = _error(
        _call(
            client,
            token,
            "upsert_page_section",
            {"slug": "ambigua", "heading": "Setup", "body": "tres"},
        )
    )
    assert "2 headings match" in message
    assert "disambiguate" in message
    # Y la página no cambió.
    content = _data(_call(client, token, "read_page_raw", {"slug": "ambigua"}))["content"]
    assert content.count("## Setup") == 2 and "tres" not in content


def test_upsert_disambiguates_by_level(client):
    """Mismo texto en dos niveles: `level` decide y la operación sale adelante."""
    token = _token(client)
    _page(client, token, "Niveles", "## Setup\n\nsección\n\n### Setup\n\nsubsección")

    message = _error(
        _call(
            client,
            token,
            "upsert_page_section",
            {"slug": "niveles", "heading": "Setup", "body": "x"},
        )
    )
    assert "levels [2, 3]" in message
    content = _data(_call(client, token, "read_page_raw", {"slug": "niveles"}))["content"]
    assert content.count("Setup") == 2


def test_upsert_preserves_a_code_fence_in_a_neighbouring_section(client):
    """La sintaxis del markdown de al lado no se toca: vallas, tablas y todo."""
    token = _token(client)
    doc = (
        "# Doc\n\n## Código\n\n```bash\n## esto no es un encabezado\ncertbot renew\n```\n\n"
        "## Tabla\n\n| a | b |\n|:--|--:|\n| 1 | 2 |\n\n## Notas\n\nviejo\n"
    )
    _page(client, token, "Doc", doc)

    _data(
        _call(
            client,
            token,
            "upsert_page_section",
            {"slug": "doc", "heading": "Notas", "body": "nuevo"},
        )
    )
    content = _data(_call(client, token, "read_page_raw", {"slug": "doc"}))["content"]
    assert "```bash\n## esto no es un encabezado\ncertbot renew\n```" in content
    assert "| a | b |\n|:--|--:|\n| 1 | 2 |" in content
    assert "nuevo" in content and "viejo" not in content


def test_upsert_records_a_version_and_requeues_for_indexing(client):
    """Pasa por el mismo camino que cualquier otra escritura, no por un atajo."""
    token = _token(client)
    _page(client, token, "Renovación TLS", RUNBOOK)
    with db.connect() as conn:
        conn.execute("UPDATE pages SET embed_dirty = 0")
    versions_before = len(
        _data(_call(client, token, "get_page_history", {"slug": "renovacion-tls"}))
    )

    _data(
        _call(
            client,
            token,
            "upsert_page_section",
            {"slug": "renovacion-tls", "heading": "Rollback", "body": "Procedimiento nuevo."},
        )
    )

    # Historial: una versión más.
    versions_after = len(
        _data(_call(client, token, "get_page_history", {"slug": "renovacion-tls"}))
    )
    assert versions_after == versions_before + 1
    # Índice: la página vuelve a la cola, sus fragmentos ya no valen.
    assert [t.id for t in db.pages_to_embed(10)], "la escritura no invalidó el índice"


def test_upsert_fires_the_same_webhook_event_as_any_write(client):
    token = _token(client)
    client.post(
        "/api/webhooks",
        json={"url": "https://nowhere.invalid/hook", "events": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    _page(client, token, "Renovación TLS", RUNBOOK)
    with db.connect() as conn:
        conn.execute("DELETE FROM webhook_deliveries")

    _data(
        _call(
            client,
            token,
            "upsert_page_section",
            {"slug": "renovacion-tls", "heading": "Certbot", "body": "otro"},
        )
    )
    with db.connect() as conn:
        rows = conn.execute("SELECT event FROM webhook_deliveries").fetchall()
    assert [r["event"] for r in rows] == ["page.updated"]


def test_two_agents_editing_different_sections_both_survive(client):
    """El caso que motiva la herramienta: nadie manda el cuerpo entero que leyó."""
    token = _token(client)
    _page(client, token, "Renovación TLS", RUNBOOK)

    for heading, body in (("Certbot", "de A"), ("Rollback", "de B")):
        _data(
            _call(
                client,
                token,
                "upsert_page_section",
                {"slug": "renovacion-tls", "heading": heading, "body": body},
            )
        )

    content = _data(_call(client, token, "read_page_raw", {"slug": "renovacion-tls"}))["content"]
    assert "de A" in content and "de B" in content


def test_upsert_on_a_missing_page_errors(client):
    token = _token(client)
    message = _error(
        _call(
            client, token, "upsert_page_section", {"slug": "no-existe", "heading": "X", "body": "y"}
        )
    )
    assert "not found" in message.lower()


def test_another_workspace_cannot_write_a_section(client):
    token_a = _token(client, "a@test.com")
    _page(client, token_a, "Renovación TLS", RUNBOOK)
    token_b = _token(client, "b@test.com")

    result = _call(
        client,
        token_b,
        "upsert_page_section",
        {"slug": "renovacion-tls", "heading": "X", "body": "y"},
    )
    assert "not found" in _error(result).lower()


# ── La cirugía, aislada del transporte ───────────────────────────────────────


def test_upsert_section_leaves_the_frontmatter_alone():
    doc = "---\ntype: note\n---\n\n## A\n\nviejo\n"
    out = meta.upsert_section(doc, "A", "nuevo")
    assert out.startswith("---\ntype: note\n---\n")
    assert "nuevo" in out and "viejo" not in out


def test_upsert_section_stops_at_the_next_heading_of_the_same_level():
    doc = "## A\n\nuno\n\n### A1\n\nanidado\n\n## B\n\ndos"
    out = meta.upsert_section(doc, "A", "reemplazo")
    # La subsección cuelga de A: se va con ella.
    assert "anidado" not in out
    # B es hermana: se queda.
    assert "## B\n\ndos" in out


def test_find_section_ignores_headings_inside_a_fence():
    doc = "## Real\n\n```\n## Falso\n```\n"
    with pytest.raises(LookupError):
        meta.find_section(doc, "Falso")
    assert meta.find_section(doc, "Real")[0] == 0


# ── Navegación del grafo de conocimiento ─────────────────────────────────────
#
# Lo que se prueba aquí es la pregunta que hace un agente que explora: partiendo
# de esta página, qué hay cerca, en qué dirección y por qué camino. Un salto lo
# responde `list_backlinks`; más de uno solo lo responde el recorrido, y sin él
# el agente paga una ida y vuelta por arista sin saber dónde acaba el vecindario.


def _graph_fixture(client, token):
    """kamailio ←→ rtpengine, kamailio → asterisk → dialplan, y un destino roto."""
    _data(_call(client, token, "create_page", {"title": "Dialplan", "content": "hojas"}))
    _data(
        _call(
            client,
            token,
            "create_page",
            {"title": "Asterisk", "content": "PBX. Consulta [[dialplan]]."},
        )
    )
    _data(
        _call(
            client,
            token,
            "create_page",
            {"title": "Kamailio", "content": "SBC. Ver [[rtpengine]] y [[asterisk]]."},
        )
    )
    _data(
        _call(
            client,
            token,
            "create_page",
            {"title": "rtpengine", "content": "Media. Depende de [[kamailio]] y de [[nunca]]."},
        )
    )


def test_agent_walks_one_hop_in_both_directions(client):
    token = _token(client)
    _graph_fixture(client, token)

    out = _data(_call(client, token, "get_linked_knowledge", {"slug": "kamailio"}))
    assert out["slug"] == "kamailio"
    assert out["depth"] == 1
    reached = {n["slug"]: n for n in out["neighbors"]}
    # Salientes y entrantes en la misma respuesta: rtpengine llega por los dos
    # lados, y basta con que el recorrido lo cuente una vez.
    assert {"rtpengine", "asterisk"} <= set(reached)
    assert all(n["distance"] == 1 for n in out["neighbors"])
    assert reached["rtpengine"]["via"] == "both"  # se citan la una a la otra
    assert reached["asterisk"]["via"] == "outgoing"
    assert reached["asterisk"]["path"] == ["kamailio", "asterisk"]


def test_agent_walks_two_hops_and_gets_the_path(client):
    token = _token(client)
    _graph_fixture(client, token)

    out = _data(_call(client, token, "get_linked_knowledge", {"slug": "kamailio", "depth": 2}))
    reached = {n["slug"]: n for n in out["neighbors"]}
    assert "dialplan" in reached
    assert reached["dialplan"]["distance"] == 2
    # El camino es lo que deja al agente justificar por qué mira esta página.
    assert reached["dialplan"]["path"] == ["kamailio", "asterisk", "dialplan"]


def test_agent_sees_whether_a_target_exists(client):
    token = _token(client)
    _graph_fixture(client, token)

    out = _data(_call(client, token, "get_linked_knowledge", {"slug": "rtpengine"}))
    reached = {n["slug"]: n for n in out["neighbors"]}
    assert reached["kamailio"]["exists"] is True
    # El destino roto se devuelve, no se calla: es la señal de que alguien contaba
    # con una página que no está.
    assert reached["nunca"]["exists"] is False


def test_traversal_terminates_on_a_cycle(client):
    token = _token(client)
    _data(_call(client, token, "create_page", {"title": "Uno", "content": "voy a [[dos]]"}))
    _data(_call(client, token, "create_page", {"title": "Dos", "content": "voy a [[tres]]"}))
    _data(_call(client, token, "create_page", {"title": "Tres", "content": "vuelvo a [[uno]]"}))

    out = _data(_call(client, token, "get_linked_knowledge", {"slug": "uno", "depth": 3}))
    slugs = [n["slug"] for n in out["neighbors"]]
    assert sorted(slugs) == ["dos", "tres"]  # cada una una vez, y "uno" no vuelve
    assert len(slugs) == len(set(slugs))


def test_a_self_link_reaches_nobody(client):
    token = _token(client)
    _data(_call(client, token, "create_page", {"title": "Sola", "content": "me cito: [[sola]]"}))

    out = _data(_call(client, token, "get_linked_knowledge", {"slug": "sola"}))
    assert out["neighbors"] == []


def test_depth_is_capped_and_the_cap_is_declared(client):
    token = _token(client)
    _graph_fixture(client, token)

    out = _data(_call(client, token, "get_linked_knowledge", {"slug": "kamailio", "depth": 99}))
    assert out["depth"] == 3

    listed = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tool = next(t for t in listed.json()["result"]["tools"] if t["name"] == "get_linked_knowledge")
    assert "capped at" in tool["description"]


def test_a_truncated_neighbourhood_says_so(client):
    token = _token(client)
    _graph_fixture(client, token)

    out = _data(_call(client, token, "get_linked_knowledge", {"slug": "kamailio", "limit": 1}))
    assert len(out["neighbors"]) == 1
    assert out["truncated"] is True

    whole = _data(_call(client, token, "get_linked_knowledge", {"slug": "kamailio"}))
    assert whole["truncated"] is False


def test_unknown_page_is_a_tool_error(client):
    token = _token(client)
    result = _call(client, token, "get_linked_knowledge", {"slug": "no-existe"})
    assert result["isError"] is True


def test_the_relational_tools_say_which_relation_they_traverse(client):
    """Un agente elige leyendo solo las descripciones: tags y enlaces responden
    preguntas distintas y no puede tener que probarlas para averiguarlo."""
    listed = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = {t["name"]: t["description"] for t in listed.json()["result"]["tools"]}
    assert "not tags" in tools["list_backlinks"]
    assert "not tags" in tools["get_linked_knowledge"]
    assert "not links" in tools["related_pages"]


def test_backlinks_and_traversal_agree_at_one_hop(client):
    token = _token(client)
    _graph_fixture(client, token)

    back = {p["slug"] for p in _data(_call(client, token, "list_backlinks", {"slug": "kamailio"}))}
    out = _data(_call(client, token, "get_linked_knowledge", {"slug": "kamailio"}))
    # `both` cuenta como entrante: las dos se citan, así que sigue siendo backlink.
    incoming = {n["slug"] for n in out["neighbors"] if n["via"] in ("incoming", "both")}
    assert back == incoming
