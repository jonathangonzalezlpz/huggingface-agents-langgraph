"""The compiled Studio interface: static files with a fallback to its index."""

from pathlib import Path
from urllib.parse import unquote

from huggingface_agents_langgraph.api.http import (
    BytesResponse,
    Redirect,
    Request,
    Response,
    failure,
)
from huggingface_agents_langgraph.api.router import Router

APP_DIRECTORY = Path(__file__).resolve().parents[2] / "static" / "app"
APP_PREFIX = "/app"
WEB_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".map": "application/json; charset=utf-8",
}
BUNDLE_NOT_BUILT = (
    "<!doctype html><meta charset=utf-8><title>GAIA Agent Studio</title>"
    "<h1>GAIA Agent Studio is not built</h1>"
    "<p>Run <code>scripts/build_frontend.ps1</code> and reload.</p>"
)
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"


def redirect_to_app(request: Request) -> Response:
    return Redirect(APP_PREFIX + "/")


def serve_app(request: Request) -> Response:
    """Serve the compiled application; client routes fall back to the index."""
    root = APP_DIRECTORY.resolve()
    index = root / "index.html"
    if not index.is_file():
        return BytesResponse(404, BUNDLE_NOT_BUILT.encode(), WEB_CONTENT_TYPES[".html"])
    requested = unquote(request.params.get("rest", "")).strip("/")
    target = (root / requested).resolve() if requested else index
    if not target.is_relative_to(root):
        target = index
    if target.is_file():
        asset = target
    elif Path(requested).suffix:
        return failure(404, "Asset not found")
    else:
        asset = index
    return BytesResponse(
        200,
        asset.read_bytes(),
        WEB_CONTENT_TYPES.get(asset.suffix.lower(), "application/octet-stream"),
        {"Cache-Control": "no-cache" if asset == index else IMMUTABLE_CACHE},
    )


def register(router: Router) -> None:
    router.add("GET", "/")(redirect_to_app)
    router.add("GET", APP_PREFIX)(serve_app)
    router.add("GET", APP_PREFIX + "/")(serve_app)
    router.add("GET", APP_PREFIX + "/{rest*}")(serve_app)
