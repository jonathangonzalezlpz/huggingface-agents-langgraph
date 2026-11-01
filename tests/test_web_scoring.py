"""HTTP endpoints that score a stored experiment."""

import json
from io import BytesIO

import pytest

from huggingface_agents_langgraph import run_tracking, web_app

EXPERIMENT_ID = "66666666-6666-4666-8666-666666666666"


@pytest.fixture(autouse=True)
def runtime_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))


def store(count=20):
    run_tracking.write_record(
        "experiments",
        {
            "id": EXPERIMENT_ID,
            "config": {"name": "x"},
            "answers": [
                {"task_id": f"t{n}", "submitted_answer": f"a{n}"} for n in range(count)
            ],
        },
    )


def post(path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else b""
    handler = web_app.WebAppHandler.__new__(web_app.WebAppHandler)
    handler.path = path
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    responses = []
    handler._send_json = lambda status, data: responses.append((status, data))
    handler.do_POST()
    return responses[-1]


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


def test_local_evaluation_of_a_stored_experiment(monkeypatch):
    store()
    monkeypatch.setattr(
        web_app,
        "evaluate_experiment",
        lambda experiment_id: {"score": 50, "correct_count": 10, "total_attempted": 20},
    )
    status, body = post(f"/api/experiments/{EXPERIMENT_ID}/evaluate")
    assert (status, body["correct_count"]) == (200, 10)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (FileNotFoundError("gone"), 404),
        (ValueError("Exactly 20 answers are required"), 400),
        (RuntimeError("dataset unavailable"), 503),
    ],
)
def test_local_evaluation_failures(monkeypatch, error, expected):
    def fail(_id):
        raise error

    monkeypatch.setattr(web_app, "evaluate_experiment", fail)
    status, body = post(f"/api/experiments/{EXPERIMENT_ID}/evaluate")
    assert status == expected
    assert body["error"]


def test_official_score_sends_the_stored_answers_and_keeps_the_result(monkeypatch):
    store()
    sent = []

    def fake_urlopen(request, timeout):
        sent.append(json.loads(request.data))
        return FakeResponse(
            {"score": 45.0, "correct_count": 9, "total_attempted": 20, "message": "ok"}
        )

    monkeypatch.setattr(web_app, "urlopen", fake_urlopen)
    status, body = post(
        "/api/score",
        {
            "username": "someone",
            "agent_code": "https://code",
            "experiment_id": EXPERIMENT_ID,
        },
    )
    assert status == 200
    assert body["correct_count"] == 9
    assert body["saved"] is True
    assert [a["task_id"] for a in sent[0]["answers"]] == [f"t{n}" for n in range(20)]
    stored = run_tracking.read_record("experiments", EXPERIMENT_ID)
    assert stored["score"]["score"] == 45.0


def test_the_client_cannot_override_the_stored_answers(monkeypatch):
    store()
    sent = []
    monkeypatch.setattr(
        web_app,
        "urlopen",
        lambda request, timeout: (
            sent.append(json.loads(request.data))
            or FakeResponse({"score": 0, "correct_count": 0, "total_attempted": 20})
        ),
    )
    post(
        "/api/score",
        {
            "username": "u",
            "agent_code": "c",
            "experiment_id": EXPERIMENT_ID,
            "answers": [{"task_id": "forged", "submitted_answer": "x"}] * 20,
        },
    )
    assert sent[0]["answers"][0]["task_id"] == "t0"


def test_official_score_needs_a_complete_experiment_and_never_calls_out(monkeypatch):
    store(count=5)
    calls = []
    monkeypatch.setattr(web_app, "urlopen", lambda *a, **k: calls.append(a))
    status, _ = post(
        "/api/score",
        {"username": "u", "agent_code": "c", "experiment_id": EXPERIMENT_ID},
    )
    assert status == 400
    assert calls == []


def test_the_result_is_still_returned_if_it_cannot_be_saved(monkeypatch):
    store()
    monkeypatch.setattr(
        web_app,
        "urlopen",
        lambda request, timeout: FakeResponse(
            {"score": 5, "correct_count": 1, "total_attempted": 20}
        ),
    )

    def broken(_id, _result):
        raise ValueError("immutable")

    monkeypatch.setattr(web_app, "record_official_score", broken)
    status, body = post(
        "/api/score",
        {"username": "u", "agent_code": "c", "experiment_id": EXPERIMENT_ID},
    )
    assert status == 200
    assert body["saved"] is False
    assert body["correct_count"] == 1
