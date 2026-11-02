"""Serving of the compiled Studio application under /app."""

import pytest

from huggingface_agents_langgraph import web_app
from huggingface_agents_langgraph.web_app import WebAppHandler


@pytest.fixture
def bundle(monkeypatch, tmp_path):
    root = tmp_path / "app"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>studio</html>", encoding="utf-8")
    (root / "assets" / "main-abc123.js").write_text("export {}", encoding="utf-8")
    (root / "assets" / "main-abc123.css").write_text("body{}", encoding="utf-8")
    (root / "assets" / "font.woff2").write_bytes(b"\x00\x01")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    monkeypatch.setattr(web_app, "APP_DIRECTORY", root)
    return root


def _get(path: str):
    handler = WebAppHandler.__new__(WebAppHandler)
    handler.path = path
    sent = []
    handler._send_bytes = lambda status, body, content_type, headers=None: sent.append(
        (status, body, content_type, headers or {})
    )
    handler._send_json = lambda status, payload: sent.append(
        (status, payload, "application/json", {})
    )
    handler.do_GET()
    return sent[-1]


@pytest.mark.parametrize("path", ["/app", "/app/", "/app/builder", "/app/runs/abc"])
def test_application_routes_serve_the_index(bundle, path):
    status, body, content_type, headers = _get(path)
    assert status == 200
    assert body == b"<html>studio</html>"
    assert content_type.startswith("text/html")
    assert headers["Cache-Control"] == "no-cache"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("main-abc123.js", "text/javascript"),
        ("main-abc123.css", "text/css"),
        ("font.woff2", "font/woff2"),
    ],
)
def test_assets_have_explicit_types_and_long_caching(bundle, name, expected):
    status, _body, content_type, headers = _get(f"/app/assets/{name}")
    assert status == 200
    assert content_type.startswith(expected)
    assert "immutable" in headers["Cache-Control"]


def test_missing_asset_is_not_replaced_by_the_index(bundle):
    assert _get("/app/assets/missing.js")[0] == 404


@pytest.mark.parametrize(
    "path",
    [
        "/app/../secret.txt",
        "/app/%2e%2e/secret.txt",
        "/app/..%2fsecret.txt",
        "/app/assets/../../secret.txt",
        "/app/%2e%2e%2fsecret.txt",
    ],
)
def test_paths_outside_the_bundle_are_never_served(bundle, path):
    status, body, _type, _headers = _get(path)
    assert b"secret" not in (body if isinstance(body, bytes) else str(body).encode())
    assert status in {200, 404}
    if status == 200:
        assert body == b"<html>studio</html>"


def test_missing_bundle_explains_how_to_build_it(monkeypatch, tmp_path):
    monkeypatch.setattr(web_app, "APP_DIRECTORY", tmp_path / "absent")
    status, body, content_type, _headers = _get("/app")
    assert status == 404
    assert content_type.startswith("text/html")
    assert b"build_frontend" in body


def _get_with_redirect(path: str):
    handler = WebAppHandler.__new__(WebAppHandler)
    handler.path = path
    sent = []
    handler._redirect = lambda location: sent.append(("redirect", location))
    handler._send_json = lambda status, payload: sent.append((status, payload))
    handler._send_bytes = lambda *args, **kwargs: sent.append(("bytes", args))
    handler.do_GET()
    return sent[-1]


def test_the_root_leads_to_the_studio():
    assert _get_with_redirect("/") == ("redirect", "/app/")


@pytest.mark.parametrize("path", ["/assets/app.js", "/assets/styles.css"])
def test_the_previous_interface_assets_are_gone(path):
    status, _payload = _get_with_redirect(path)
    assert status == 404
