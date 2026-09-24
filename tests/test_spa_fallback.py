"""A browser address outside the application is routed into it; API clients keep the JSON 404."""

HTML = {"accept": "text/html,application/xhtml+xml,*/*;q=0.8"}


def test_a_browser_path_without_the_prefix_is_redirected_into_the_app(client):
    r = client.get("/settings", headers=HTML, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/app/settings"


def test_the_query_string_survives_the_redirect(client):
    r = client.get("/w/demo/graph?focus=a", headers=HTML, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/app/w/demo/graph?focus=a"


def test_an_unknown_api_path_keeps_the_json_404_even_for_a_browser(client):
    r = client.get("/api/nope", headers=HTML, follow_redirects=False)
    assert r.status_code == 404
    assert r.json() == {"detail": "Not Found"}


def test_a_client_that_does_not_ask_for_html_keeps_the_json_404(client):
    r = client.get("/nope", headers={"accept": "application/json"}, follow_redirects=False)
    assert r.status_code == 404
    assert r.json() == {"detail": "Not Found"}


def test_only_a_get_is_redirected(client):
    r = client.post("/nope", headers=HTML, follow_redirects=False)
    assert r.status_code in (404, 405)
    assert "location" not in r.headers


def test_a_missing_static_asset_stays_a_404(client):
    r = client.get("/static/nope.css", headers=HTML, follow_redirects=False)
    assert r.status_code == 404


def test_an_api_404_raised_by_a_handler_is_unchanged(client):
    r = client.get("/api/pages/does-not-exist", headers=HTML, follow_redirects=False)
    assert r.status_code in (401, 404)
    assert "location" not in r.headers
