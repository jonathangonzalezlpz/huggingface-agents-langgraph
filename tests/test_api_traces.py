"""The trace endpoints: structured, exported and on-demand views of a run."""

import json
from unittest.mock import patch

from huggingface_agents_langgraph.api.http import Request
from huggingface_agents_langgraph.api.routes import build_router

RECORD = {
    "id": "11111111-2222-3333-4444-555555555555",
    "created_at": "2026-11-02T10:00:00+00:00",
    "status": "completed",
    "duration_seconds": 1.0,
    "task": {"question": "q", "task_id": "t"},
    "result": {"submitted_answer": "a"},
    "steps": [
        {
            "node": "search",
            "update": {"k": 1},
            "duration_seconds": 1.0,
            "started_offset_seconds": 0.0,
        }
    ],
    "calls": [],
}
EXPERIMENT = {
    "id": "e1",
    "answers": [{"task_id": "t1", "submitted_answer": "a", "route": "web"}],
}


def _get(path):
    router = build_router()
    found = router.match("GET", path)
    assert found, path
    handler, params = found
    return handler(Request("GET", path, params, {}, None))


def _patched():
    def read(kind, record_id):
        if kind == "runs" and record_id == RECORD["id"]:
            return RECORD
        if kind == "experiments" and record_id == "e1":
            return EXPERIMENT
        raise FileNotFoundError(record_id)

    return patch("huggingface_agents_langgraph.api.handlers.traces.read_record", read)


def test_trace_endpoint_returns_the_light_span_tree():
    with _patched():
        response = _get(f"/api/runs/{RECORD['id']}/trace")

    assert response.status == 200
    assert response.payload["spans"][0]["kind"] == "run"
    assert '"k": 1' not in json.dumps(response.payload)


def test_exports_have_the_right_content_types():
    with _patched():
        jsonl = _get(f"/api/runs/{RECORD['id']}/trace.jsonl")
        markdown = _get(f"/api/runs/{RECORD['id']}/report.md")
        csv_ = _get("/api/experiments/e1/trace.csv")
        otlp = _get(f"/api/runs/{RECORD['id']}/trace.otlp.json")

    assert jsonl.content_type.startswith("application/x-ndjson")
    assert markdown.content_type.startswith("text/markdown")
    assert csv_.content_type.startswith("text/csv")
    assert "resourceSpans" in otlp.payload
    assert b"search" in jsonl.body and markdown.body.startswith(b"# ")


def test_span_payload_is_loaded_on_demand_and_unknown_span_is_404():
    with _patched():
        span = _get(f"/api/runs/{RECORD['id']}/trace").payload["spans"][1]
        payload = _get(f"/api/runs/{RECORD['id']}/spans/{span['span_id']}")
        missing = _get(f"/api/runs/{RECORD['id']}/spans/nope")

    assert payload.payload == {"update": {"k": 1}}
    assert missing.status == 404


def test_unknown_run_or_experiment_is_404():
    with _patched():
        assert _get("/api/runs/zzz/trace").status == 404
        assert _get("/api/experiments/zzz/trace.csv").status == 404


def test_the_plain_run_route_still_works():
    with patch(
        "huggingface_agents_langgraph.api.handlers.runs.read_record",
        return_value=RECORD,
    ):
        assert _get(f"/api/runs/{RECORD['id']}").payload["id"] == RECORD["id"]


def test_insights_endpoint_aggregates_a_battery():
    with _patched():
        response = _get("/api/experiments/e1/insights")
        missing = _get("/api/experiments/zzz/insights")

    assert response.payload["totals"]["answered"] == 1
    assert missing.status == 404
