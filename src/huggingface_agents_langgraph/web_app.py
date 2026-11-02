"""Serve the local Studio and its API on 127.0.0.1."""

import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from huggingface_agents_langgraph.api.http import (
    BytesResponse,
    JsonResponse,
    Redirect,
    Request,
    Response,
    failure,
)
from huggingface_agents_langgraph.api.routes import build_router

HOST = "127.0.0.1"
PORT = 7860
BODY_METHODS = {"POST", "PUT"}
ROUTER = build_router()


class WebAppHandler(BaseHTTPRequestHandler):
    """Translate HTTP into a ``Request``, route it, and write the ``Response``."""

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PUT(self) -> None:
        self._dispatch("PUT")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        path = urlsplit(self.path).path
        matched = ROUTER.match(method, path)
        if matched is None:
            self._write(failure(404, "Not found"))
            return
        handler, params = matched
        self._write(handler(self._request(method, path, params)))

    def _request(self, method: str, path: str, params: dict[str, str]) -> Request:
        """Only requests that carry a body get access to the socket."""
        if method in BODY_METHODS:
            return Request(method, path, params, self.headers, self.rfile)
        return Request(method, path, params, {}, io.BytesIO())

    def _write(self, response: Response) -> None:
        if isinstance(response, JsonResponse):
            self._send_json(response.status, response.payload)
        elif isinstance(response, BytesResponse):
            self._send_bytes(
                response.status, response.body, response.content_type, response.headers
            )
        elif isinstance(response, Redirect):
            self._redirect(response.location)

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    """Start the local server."""
    server = ThreadingHTTPServer((HOST, PORT), WebAppHandler)
    print(f"GAIA workbench available at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
