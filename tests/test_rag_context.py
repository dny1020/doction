"""El contexto ensamblado: acotado por presupuesto y sin repetir pasajes.

Antes esto devolvía seis fragmentos fijos, que no es una cota de nada: seis secciones
cortas caben en cualquier sitio y seis largas se comen la ventana del modelo que las
va a leer. Y nadie comparaba un fragmento con otro, así que dos trozos de una misma
sección gastaban el contexto dos veces en la misma frase.

Los dos canales —vectorial y léxico— pasan por el mismo empaquetado: un contrato, dos
fuentes.
"""

import pytest
from fastapi.testclient import TestClient

from app import embeddings


def _token(client, email="u@test.com") -> str:
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    r = client.post("/api/token", json={"email": email, "password": "password123"})
    return r.json()["token"]


def _page(client, token: str, title: str, content: str) -> str:
    r = client.post(
        "/api/pages",
        json={"title": title, "content": content},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["slug"]


@pytest.fixture()
def semantic_client(main_module, monkeypatch):
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    monkeypatch.setenv("EMBED_STUB", "1")
    embeddings.reset_embedder()

    async def _noop():
        return

    monkeypatch.setattr(embeddings, "enrichment_worker", _noop)
    with TestClient(main_module.app) as c:
        yield c


def _long_page(sections: int, filler: int = 400) -> str:
    body = ["# Runbook TLS", "", "Apertura del runbook sobre certbot.", ""]
    for i in range(sections):
        body += [
            f"## Sección {i}",
            "",
            f"Certbot renovación paso {i}. " + ("relleno " * filler),
            "",
        ]
    return "\n".join(body)


# ── Presupuesto ──────────────────────────────────────────────────────────────


def test_budget_bounds_the_context_not_a_fragment_count(semantic_client):
    client = semantic_client
    token = _token(client)
    _page(client, token, "Runbook TLS", _long_page(sections=8))
    embeddings.drain_pending()

    out = embeddings.rag_context(1, "certbot renovación", budget=4000)
    total = sum(len(c["text"]) for c in out["chunks"])
    assert total <= 4000
    assert out["chunks"], out
    # Y con más presupuesto entra más contexto: la cota es el presupuesto, no un seis.
    grande = embeddings.rag_context(1, "certbot renovación", budget=12000)
    assert sum(len(c["text"]) for c in grande["chunks"]) > total


def test_a_fragment_that_does_not_fit_is_left_out_whole(semantic_client):
    """Cortarlo por la mitad devolvería un texto que la página no dice."""
    client = semantic_client
    token = _token(client)
    _page(client, token, "Runbook TLS", _long_page(sections=6))
    embeddings.drain_pending()

    out = embeddings.rag_context(1, "certbot renovación", budget=2500)
    assert out["truncated"] is True
    for chunk in out["chunks"]:
        # Cada fragmento contra SU página: el workspace trae las páginas de ejemplo
        # del registro, así que no todos vienen de la que sembró este test.
        page = client.get(
            "/api/pages/" + chunk["slug"], headers={"Authorization": f"Bearer {token}"}
        ).json()["content"]
        assert chunk["text"] in page, "el fragmento no está literal en su página"


def test_truncated_is_false_when_everything_fits(semantic_client):
    client = semantic_client
    token = _token(client)
    _page(client, token, "Corta", "# Corta\n\nCertbot y poco más.")
    embeddings.drain_pending()

    out = embeddings.rag_context(1, "certbot", budget=100000)
    assert out["truncated"] is False


def test_limit_still_caps_the_pieces_for_whoever_wants_fewer(semantic_client):
    client = semantic_client
    token = _token(client)
    _page(client, token, "Runbook TLS", _long_page(sections=8))
    embeddings.drain_pending()

    out = embeddings.rag_context(1, "certbot renovación", budget=100000, limit=2)
    assert len(out["chunks"]) == 2
    assert out["truncated"] is True


# ── Deduplicación ────────────────────────────────────────────────────────────


def test_two_pieces_of_one_section_collapse(semantic_client):
    """Una sección más larga que el techo sale en varios fragmentos: cuenta una vez."""
    client = semantic_client
    token = _token(client)
    largo = "Certbot renovación. " + ("detalle del procedimiento " * 200)
    _page(client, token, "Runbook TLS", f"# Runbook TLS\n\n## Certbot\n\n{largo}\n")
    embeddings.drain_pending()

    out = embeddings.rag_context(1, "certbot renovación", budget=100000)
    secciones = [(c["slug"], c["section"]) for c in out["chunks"]]
    assert len(secciones) == len(set(secciones)), secciones


def test_distinct_sections_of_one_page_both_survive(semantic_client):
    """El error contrario: colapsar dos secciones que responden a cosas distintas."""
    client = semantic_client
    token = _token(client)
    _page(
        client,
        token,
        "Runbook TLS",
        "# Runbook TLS\n\n## Certbot\n\nRenovar con certbot renew y recargar nginx.\n\n"
        "## Rollback\n\nRestaurar el certificado anterior desde el backup diario.\n",
    )
    embeddings.drain_pending()

    out = embeddings.rag_context(1, "certbot rollback certificado", budget=100000)
    secciones = {c["section"] for c in out["chunks"]}
    assert len(secciones) >= 2, out["chunks"]


def test_says_the_same_recognises_the_three_shapes():
    """La regla, aislada: misma sección, contención literal, o casi las mismas palabras."""
    a = {"slug": "p", "section": "S", "text": "uno dos tres"}
    b = {"slug": "p", "section": "S", "text": "cuatro cinco seis"}
    assert embeddings._says_the_same(a, b), "misma sección de la misma página"

    corto = {"slug": "p", "section": "A", "text": "certbot renew"}
    largo = {"slug": "q", "section": "B", "text": "antes certbot renew después"}
    assert embeddings._says_the_same(corto, largo), "contención literal"

    palabras = " ".join(f"palabra{i}" for i in range(30))
    uno = {"slug": "p", "section": "A", "text": palabras}
    otro = {"slug": "q", "section": "B", "text": palabras + " extra distinta"}
    assert embeddings._says_the_same(uno, otro), "casi las mismas palabras"


def test_says_the_same_does_not_collapse_short_unrelated_fragments():
    """Dos frases cortas del mismo tema comparten casi todo: ahí el solape no vale."""
    uno = {"slug": "p", "section": "A", "text": "renovar el certificado con certbot"}
    otro = {"slug": "q", "section": "B", "text": "borrar el certificado con openssl"}
    assert not embeddings._says_the_same(uno, otro)


# ── El mismo contrato en el canal léxico ─────────────────────────────────────


def test_the_lexical_channel_honours_the_budget(client):
    token = _token(client)
    for i in range(5):
        _page(client, token, f"Certbot {i}", _long_page(sections=2))

    out = embeddings.rag_context(1, "certbot", budget=1500)
    assert out["mode"] == "fts"
    assert sum(len(c["text"]) for c in out["chunks"]) <= 1500


def test_the_lexical_channel_deduplicates_too(client):
    token = _token(client)
    cuerpo = "# Doc\n\n## Certbot\n\nRenovar con certbot renew y recargar nginx después.\n"
    _page(client, token, "Uno", cuerpo)
    _page(client, token, "Dos", cuerpo)

    out = embeddings.rag_context(1, "certbot", budget=100000)
    textos = [c["text"] for c in out["chunks"]]
    assert len(textos) == len(set(textos)), textos


def test_the_lexical_channel_reports_no_score_rather_than_inventing_one(client):
    token = _token(client)
    _page(client, token, "Doc", "# Doc\n\n## Certbot\n\nRenovar con certbot renew.\n")

    out = embeddings.rag_context(1, "certbot", budget=100000)
    assert all(c["score"] is None for c in out["chunks"])


def test_search_keeps_its_highlighted_extracts(client):
    """La búsqueda de la interfaz no cambia: el resaltado es lo que pinta la barra."""
    token = _token(client)
    _page(client, token, "Doc", "# Doc\n\n## Certbot\n\nRenovar con certbot renew.\n")

    hits = client.get("/api/search?q=certbot", headers={"Authorization": f"Bearer {token}"}).json()
    assert hits
    assert any(part["match"] for part in hits[0]["parts"]), "el extracto sigue resaltando"
