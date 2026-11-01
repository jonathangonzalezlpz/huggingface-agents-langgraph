"""HTTP endpoints for validating, saving and reading agent architectures."""

import json
from dataclasses import replace
from io import BytesIO

import pytest

from huggingface_agents_langgraph import run_tracking
from huggingface_agents_langgraph.architecture_store import BUILTIN_V31_ID
from huggingface_agents_langgraph.graph_definition.definitions import (
    create_gaia_v31_definition,
)
from huggingface_agents_langgraph.web_app import MAX_REQUEST_BYTES, WebAppHandler


@pytest.fixture(autouse=True)
def runtime_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))


def _call(method: str, path: str, body: bytes | None = None):
    handler = WebAppHandler.__new__(WebAppHandler)
    handler.path = path
    handler.headers = {"Content-Length": str(len(body or b""))}
    handler.rfile = BytesIO(body or b"")
    responses = []
    handler._send_json = lambda status, payload: responses.append((status, payload))
    getattr(handler, f"do_{method}")()
    return responses[-1]


def _post(path: str, payload) -> tuple[int, dict]:
    return _call("POST", path, json.dumps(payload).encode())


def _custom_definition() -> dict:
    return replace(create_gaia_v31_definition(), architecture_id="custom").to_dict()


class TestValidateEndpoint:
    def test_valid_definition(self):
        status, body = _post(
            "/api/architectures/validate", create_gaia_v31_definition().to_dict()
        )
        assert status == 200
        assert body["is_valid"] is True

    def test_unconstructible_definition_returns_a_finding(self):
        status, body = _post("/api/architectures/validate", {"schema_version": "4.0"})
        assert status == 200
        assert body["diagnostics"][0]["code"] == "INVALID_DEFINITION"

    def test_validation_does_not_persist(self, tmp_path):
        _post("/api/architectures/validate", _custom_definition())
        assert not (tmp_path / "architectures").exists()

    @pytest.mark.parametrize("kind", ["empty", "not_json", "array", "too_large"])
    def test_malformed_requests_are_rejected(self, kind):
        bodies = {
            "empty": b"",
            "not_json": b"not json",
            "array": b"[1]",
            "too_large": b"x" * (MAX_REQUEST_BYTES + 1),
        }
        status, payload = _call("POST", "/api/architectures/validate", bodies[kind])
        assert status == 400
        assert "error" in payload


class TestSaveEndpoint:
    def test_saves_and_reads_back(self):
        status, saved = _post("/api/architectures", _custom_definition())
        assert status == 200
        assert saved["version"] == 1
        status, detail = _call("GET", f"/api/architectures/{saved['id']}")
        assert status == 200
        assert detail["definition"] == _custom_definition()
        assert detail["validation"]["is_valid"] is True

    def test_saving_twice_returns_the_same_version(self):
        _, first = _post("/api/architectures", _custom_definition())
        _, second = _post("/api/architectures", _custom_definition())
        assert second["id"] == first["id"]

    def test_unconstructible_definition_is_a_bad_request(self):
        status, body = _post("/api/architectures", {"schema_version": "4.0"})
        assert status == 400
        assert "error" in body

    def test_reserved_architecture_id_is_a_bad_request(self):
        status, body = _post(
            "/api/architectures", create_gaia_v31_definition().to_dict()
        )
        assert status == 400
        assert "reserved" in body["error"]


class TestReadEndpoints:
    def test_listing_includes_the_builtin_pipeline(self):
        status, body = _call("GET", "/api/architectures")
        assert status == 200
        assert [a["id"] for a in body["architectures"]] == [BUILTIN_V31_ID]
        assert "definition" not in body["architectures"][0]

    def test_listing_includes_saved_versions(self):
        _post("/api/architectures", _custom_definition())
        _, body = _call("GET", "/api/architectures")
        assert [a["read_only"] for a in body["architectures"]] == [True, False]

    def test_builtin_detail_is_valid(self):
        status, body = _call("GET", f"/api/architectures/{BUILTIN_V31_ID}")
        assert status == 200
        assert body["validation"]["is_valid"] is True

    @pytest.mark.parametrize(
        "identifier", ["00000000-0000-0000-0000-000000000000", "nope"]
    )
    def test_unknown_architecture_is_not_found(self, identifier):
        status, body = _call("GET", f"/api/architectures/{identifier}")
        assert status == 404
        assert "error" in body

    def test_versions_cannot_be_deleted(self):
        _, saved = _post("/api/architectures", _custom_definition())
        status, _body = _call("DELETE", f"/api/architectures/{saved['id']}")
        assert status == 404
        assert _call("GET", f"/api/architectures/{saved['id']}")[0] == 200
