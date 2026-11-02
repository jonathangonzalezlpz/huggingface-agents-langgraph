"""HTTP endpoints that start, observe and stop a background battery."""

import json
from io import BytesIO

import pytest

from huggingface_agents_langgraph import run_tracking, web_app
from huggingface_agents_langgraph.batteries import (
    BatteryBusyError,
    BatteryUnavailableError,
)


@pytest.fixture(autouse=True)
def runtime_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))


class FakeManager:
    def __init__(self):
        self.started = []
        self.raises = None
        self.state = {"state": "idle"}

    def start(self, experiment, *, limit=20, resume_id=None):
        if self.raises:
            raise self.raises
        self.started.append((experiment, limit, resume_id))
        self.state = {"state": "running", "total": limit}
        return self.state

    def status(self):
        return self.state

    def stop(self):
        self.state = {"state": "stopping"}
        return self.state


@pytest.fixture
def manager(monkeypatch):
    fake = FakeManager()
    monkeypatch.setattr(web_app, "BATTERIES", fake)
    return fake


def _call(method: str, path: str, payload=None):
    body = json.dumps(payload).encode() if payload is not None else b""
    handler = web_app.WebAppHandler.__new__(web_app.WebAppHandler)
    handler.path = path
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    responses = []
    handler._send_json = lambda status, data: responses.append((status, data))
    getattr(handler, f"do_{method}")()
    return responses[-1]


def test_starts_a_battery_with_the_experiment_and_limit(manager):
    status, body = _call(
        "POST", "/api/batteries", {"experiment": {"name": "x"}, "limit": 5}
    )
    assert status == 202
    assert body["state"] == "running"
    assert manager.started == [({"name": "x"}, 5, None)]


def test_resume_needs_only_the_experiment_id(manager):
    status, _ = _call("POST", "/api/batteries", {"resume_id": "abc"})
    assert status == 202
    assert manager.started == [(None, 20, "abc")]


def test_rejects_a_non_integer_limit(manager):
    status, body = _call("POST", "/api/batteries", {"experiment": {}, "limit": "all"})
    assert status == 400
    assert "limit" in body["error"]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (BatteryBusyError("busy"), 409),
        (BatteryUnavailableError("no reference"), 503),
        (ValueError("bad config"), 400),
        (FileNotFoundError("gone"), 404),
    ],
)
def test_maps_failures_to_status_codes(manager, error, expected):
    manager.raises = error
    status, body = _call("POST", "/api/batteries", {"experiment": {}})
    assert status == expected
    assert body["error"]


def test_reports_the_current_battery(manager):
    manager.state = {"state": "running", "completed": 3, "total": 20}
    assert _call("GET", "/api/batteries/current") == (200, manager.state)


def test_stop_asks_the_battery_to_finish(manager):
    status, body = _call("POST", "/api/batteries/stop")
    assert (status, body["state"]) == (200, "stopping")
