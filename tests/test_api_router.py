"""The route table and the request primitives the handlers rely on."""

import io
import json

import pytest

from huggingface_agents_langgraph.api.http import (
    MAX_REQUEST_BYTES,
    Request,
    failure,
    ok,
)
from huggingface_agents_langgraph.api.router import Router
from huggingface_agents_langgraph.api.routes import build_router


def _handler(request):
    return ok(dict(request.params))


class TestRouter:
    def _router(self):
        router = Router()
        router.add("GET", "/things")(_handler)
        router.add("GET", "/things/{id}")(_handler)
        router.add("GET", "/things/{id}/part")(_handler)
        router.add("GET", "/files/{name*}")(_handler)
        router.add("POST", "/things")(_handler)
        return router

    def test_a_static_path_matches_exactly(self):
        assert self._router().match("GET", "/things")[1] == {}
        assert self._router().match("GET", "/things/") is None

    def test_a_parameter_matches_one_segment(self):
        handler, params = self._router().match("GET", "/things/abc")
        assert params == {"id": "abc"}
        assert self._router().match("GET", "/things/a/b") is None

    def test_a_starred_parameter_matches_the_rest_of_the_path(self):
        _, params = self._router().match("GET", "/files/a/b/c.txt")
        assert params == {"name": "a/b/c.txt"}

    def test_the_method_is_part_of_the_route(self):
        router = self._router()
        assert router.match("POST", "/things") is not None
        assert router.match("DELETE", "/things") is None
        assert router.match("POST", "/things/abc") is None

    def test_the_first_matching_route_wins(self):
        router = Router()
        router.add("GET", "/x/special")(lambda request: ok("special"))
        router.add("GET", "/x/{any}")(lambda request: ok("general"))
        handler, _ = router.match("GET", "/x/special")
        assert handler(None).payload == "special"

    def test_unknown_paths_do_not_match(self):
        assert self._router().match("GET", "/nothing") is None

    def test_percent_encoding_is_left_for_the_handler(self):
        _, params = self._router().match("GET", "/things/builtin%3Agaia_v31")
        assert params == {"id": "builtin%3Agaia_v31"}


class TestRoutes:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/"),
            ("GET", "/app"),
            ("GET", "/app/builder/draft/x"),
            ("GET", "/api/status"),
            ("GET", "/api/models"),
            ("GET", "/api/catalog"),
            ("GET", "/api/architectures"),
            ("GET", "/api/architectures/builtin%3Agaia_v31"),
            ("GET", "/api/architectures/x/layout"),
            ("PUT", "/api/architectures/x/layout"),
            ("POST", "/api/architectures"),
            ("POST", "/api/architectures/validate"),
            ("GET", "/api/experiments"),
            ("POST", "/api/experiments"),
            ("POST", "/api/experiments/compare"),
            ("POST", "/api/experiments/abc/evaluate"),
            ("DELETE", "/api/experiments/abc"),
            ("GET", "/api/batteries/current"),
            ("POST", "/api/batteries"),
            ("POST", "/api/batteries/stop"),
            ("POST", "/api/run"),
            ("GET", "/api/runs/abc"),
            ("POST", "/api/evaluate"),
            ("POST", "/api/score"),
            ("GET", "/api/questions"),
            ("GET", "/api/random-question"),
            ("GET", "/api/files/task-1"),
        ],
    )
    def test_every_endpoint_of_the_api_is_routed(self, method, path):
        assert build_router().match(method, path) is not None

    @pytest.mark.parametrize(
        ("method", "path"),
        [("GET", "/api/unknown"), ("POST", "/api/status"), ("DELETE", "/api/runs/x")],
    )
    def test_anything_else_is_not_routed(self, method, path):
        assert build_router().match(method, path) is None


class TestRequest:
    def _request(self, body: bytes, length: int | None = None):
        headers = {"Content-Length": str(len(body) if length is None else length)}
        return Request("POST", "/x", {}, headers, io.BytesIO(body))

    def test_reads_a_json_object(self):
        assert self._request(b'{"a": 1}').json_object() == {"a": 1}

    def test_refuses_a_body_that_is_not_an_object(self):
        with pytest.raises(ValueError, match="JSON object"):
            self._request(b"[1, 2]").json_object()
        assert self._request(b"[1, 2]").json_value() == [1, 2]

    def test_refuses_an_empty_or_oversized_body(self):
        with pytest.raises(ValueError, match="empty or too large"):
            self._request(b"").json_object()
        with pytest.raises(ValueError, match="empty or too large"):
            self._request(b"{}", length=MAX_REQUEST_BYTES + 1).json_object()

    def test_invalid_json_is_a_value_error(self):
        with pytest.raises(ValueError):
            self._request(b"{nope").json_object()

    def test_helpers_build_the_usual_responses(self):
        assert ok({"a": 1}).status == 200
        assert failure(404, "gone").payload == {"error": "gone"}
        assert json.dumps(ok([]).payload) == "[]"
