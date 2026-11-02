"""HTTP endpoint for comparing persisted experiments."""

import json
from io import BytesIO
from uuid import uuid4

import pytest

from huggingface_agents_langgraph import run_tracking
from huggingface_agents_langgraph.web_app import WebAppHandler


@pytest.fixture(autouse=True)
def runtime_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))


def _post(payload) -> tuple[int, dict]:
    body = json.dumps(payload).encode()
    handler = WebAppHandler.__new__(WebAppHandler)
    handler.path = "/api/experiments/compare"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    responses = []
    handler._send_json = lambda status, data: responses.append((status, data))
    handler.do_POST()
    return responses[-1]


def _store(seed: int, answer_text: str = "PRIVATE-ANSWER") -> str:
    record_id = str(uuid4())
    run_tracking.write_record(
        "experiments",
        {
            "id": record_id,
            "created_at": "2026-11-01T00:00:00+00:00",
            "config": {"name": f"run {seed}", "seed": seed},
            "status": "completed",
            "total_questions": 1,
            "answers": [
                {
                    "task_id": "t1",
                    "locally_correct": seed == 1,
                    "duration_seconds": 5.0,
                    "route": "web",
                    "submitted_answer": answer_text,
                }
            ],
        },
    )
    return record_id


def test_compares_stored_experiments_without_exposing_answers():
    first, second = _store(1), _store(2)
    status, body = _post({"ids": [first, second]})
    assert status == 200
    assert [e["id"] for e in body["experiments"]] == [first, second]
    assert body["comparability"]["config_differences"]["seed"] == {
        first: 1,
        second: 2,
    }
    assert "PRIVATE-ANSWER" not in json.dumps(body)


def test_explicit_base_is_honoured():
    first, second = _store(1), _store(2)
    status, body = _post({"ids": [first, second], "base": second})
    assert status == 200
    base_group = next(g for g in body["groups"] if second in g["experiment_ids"])
    assert body["base_group"] == base_group["key"]


def test_unknown_experiment_is_not_found():
    status, body = _post({"ids": [_store(1), str(uuid4())]})
    assert status == 404
    assert "not found" in body["error"].lower()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"ids": "x"},
        {"ids": ["only-one"]},
        {"ids": ["not-a-uuid", "also-not"]},
        {"ids": [str(uuid4())] * 2},
        {"ids": [str(uuid4()) for _ in range(21)]},
        {"ids": [1, 2]},
    ],
)
def test_invalid_requests_are_rejected(payload):
    status, body = _post(payload)
    assert status == 400
    assert "error" in body


def test_unknown_base_is_a_bad_request():
    status, body = _post({"ids": [_store(1), _store(2)], "base": str(uuid4())})
    assert status == 400
    assert "base" in body["error"]
