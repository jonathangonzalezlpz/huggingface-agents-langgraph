"""HTTP endpoints for the component catalog and node layouts."""

import json
from dataclasses import replace
from io import BytesIO

import pytest

from huggingface_agents_langgraph import run_tracking
from huggingface_agents_langgraph.architecture_store import BUILTIN_V31_ID
from huggingface_agents_langgraph.graph_definition.definitions import (
    create_gaia_v31_definition,
)
from huggingface_agents_langgraph.web_app import WebAppHandler


@pytest.fixture(autouse=True)
def runtime_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))


def _call(method: str, path: str, payload=None):
    body = json.dumps(payload).encode() if payload is not None else b""
    handler = WebAppHandler.__new__(WebAppHandler)
    handler.path = path
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    responses = []
    handler._send_json = lambda status, data: responses.append((status, data))
    getattr(handler, f"do_{method}")()
    return responses[-1]


def test_catalog_lists_components_strategies_and_state():
    status, body = _call("GET", "/api/catalog")
    assert status == 200
    assert len(body["nodes"]) == 16
    assert {s["identifier"] for s in body["routing_strategies"]} == {
        "route_after_preprocessing",
        "route_after_review",
        "route_after_router",
        "route_on_verdict",
    }
    assert "question" in body["state"]["fields"]
    assert body["categories"][0] == "input"


class TestLayoutEndpoints:
    def _saved(self):
        definition = replace(create_gaia_v31_definition(), architecture_id="custom")
        _, record = _call("POST", "/api/architectures", definition.to_dict())
        return record["id"]

    def test_empty_layout_for_a_new_version(self):
        status, body = _call("GET", f"/api/architectures/{self._saved()}/layout")
        assert status == 200
        assert body["layout"] == {"nodes": {}}

    def test_put_then_get(self):
        version_id = self._saved()
        layout = {"nodes": {"router": {"x": 12, "y": 34}}}
        status, saved = _call("PUT", f"/api/architectures/{version_id}/layout", layout)
        assert status == 200
        assert saved["layout"] == layout
        _, again = _call("GET", f"/api/architectures/{version_id}/layout")
        assert again["layout"] == layout

    def test_builtin_pipeline_accepts_a_layout(self):
        layout = {"nodes": {"router": {"x": 1, "y": 2}}}
        status, _ = _call("PUT", f"/api/architectures/{BUILTIN_V31_ID}/layout", layout)
        assert status == 200

    def test_unknown_version_is_not_found(self):
        assert _call("GET", "/api/architectures/nope/layout")[0] == 404
        assert _call("PUT", "/api/architectures/nope/layout", {"nodes": {}})[0] == 404

    @pytest.mark.parametrize(
        "layout", [{"nodes": {"ghost": {"x": 1, "y": 2}}}, {"nodes": []}, {}]
    )
    def test_invalid_layout_is_a_bad_request(self, layout):
        status, body = _call(
            "PUT", f"/api/architectures/{self._saved()}/layout", layout
        )
        assert status == 400
        assert "layout" in body["error"]

    def test_layout_changes_do_not_create_versions(self):
        version_id = self._saved()
        _call(
            "PUT",
            f"/api/architectures/{version_id}/layout",
            {"nodes": {"router": {"x": 1, "y": 2}}},
        )
        _, listing = _call("GET", "/api/architectures")
        assert [
            a["version"] for a in listing["architectures"] if not a["read_only"]
        ] == [1]


class TestEncodedIdentifiers:
    """Browsers percent-encode the colon of the built-in identifier."""

    def test_detail_accepts_a_percent_encoded_identifier(self):
        status, body = _call("GET", "/api/architectures/builtin%3Agaia_v31")
        assert status == 200
        assert body["id"] == BUILTIN_V31_ID
        assert body["validation"]["is_valid"] is True

    def test_layout_accepts_a_percent_encoded_identifier(self):
        layout = {"nodes": {"router": {"x": 1, "y": 2}}}
        status, _ = _call("PUT", "/api/architectures/builtin%3Agaia_v31/layout", layout)
        assert status == 200
        status, body = _call("GET", "/api/architectures/builtin%3Agaia_v31/layout")
        assert status == 200
        assert body["layout"] == layout
