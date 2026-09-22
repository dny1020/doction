"""The pages every new user is given.

Seed content is the first thing anyone reads, so it is the easiest documentation to leave
behind: nothing fails when it goes stale. These assert the claims the pages make about the
deployment are still the deployment's claims, and that the runbook demonstrates the
features it is there to show.
"""

from app import db, graph, meta, seed

RUNBOOK_SLUG = "runbook-deploy-doction"


def _register(client, email="seed@example.com"):
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 201, r.text


def _workspace_id(main_module) -> int:
    return int(main_module.db.list_workspaces(1)[0].id)


def test_runbook_describes_the_current_deployment(client, main_module):
    """The runbook once described a Gitea runner and SQLite, neither of which exists."""
    _register(client)
    page = main_module.db.get_page(RUNBOOK_SLUG, _workspace_id(main_module))
    assert page is not None

    assert "Gitea" not in page.content
    assert "SQLite" not in page.content
    assert "GitHub Actions" in page.content
    assert "docker compose" in page.content


def test_runbook_carries_its_frontmatter(client, main_module):
    """It is the page that shows what frontmatter is for, so it has to have some."""
    _register(client)
    page_meta = main_module.db.get_page_meta(_workspace_id(main_module), RUNBOOK_SLUG)
    assert page_meta is not None
    assert page_meta.type == "runbook"
    assert "deploy" in page_meta.tags


def test_seeded_wikilink_resolves(client, main_module):
    """It is written before its target exists, so it exercises the forward-reference backfill."""
    _register(client)
    wid = _workspace_id(main_module)

    targets = {edge.dst_slug for edge in main_module.db.workspace_links(wid)}
    assert "markdown-cheatsheet" in targets

    insights = graph.link_insights(wid)
    assert insights["broken_links"] == [], insights["broken_links"]


def test_every_seeded_page_parses(client, main_module):
    """A seeded page that the parsers choke on would ship broken to every new user."""
    for title, content in seed.SEED_PAGES:
        assert title.strip()
        assert content.strip()
        meta.parse_frontmatter(content)
        assert meta.chunk_markdown(content), f"{title} produced no chunks"
        assert len(content.encode()) < db.MAX_CONTENT_BYTES
