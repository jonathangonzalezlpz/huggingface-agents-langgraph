import hashlib
import json
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest

from huggingface_agents_langgraph import baseline_archive, graph, run_tracking
from huggingface_agents_langgraph.pipeline_versions import (
    V2_REFERENCE_ID,
    V2_REFERENCE_NAME,
    experiment_presentation,
)
from huggingface_agents_langgraph.web_app import WebAppHandler


def test_reference_label_preserves_original_configuration():
    original = {"id": V2_REFERENCE_ID, "config": {"name": "Completo"}}
    presented = experiment_presentation(original)
    assert presented["display_name"] == V2_REFERENCE_NAME
    presented["config"]["name"] = "Changed"
    assert original == {"id": V2_REFERENCE_ID, "config": {"name": "Completo"}}


def test_reference_cannot_be_overwritten_or_deleted(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))
    record = {"id": V2_REFERENCE_ID, "answers": [{"submitted_answer": "original"}]}
    run_tracking.write_record("experiments", record)
    original_bytes = (tmp_path / "experiments" / f"{V2_REFERENCE_ID}.json").read_bytes()
    run_tracking.write_record("experiments", experiment_presentation(record))
    with pytest.raises(ValueError, match="immutable"):
        run_tracking.write_record("experiments", record | {"answers": []})
    with pytest.raises(ValueError, match="cannot be deleted"):
        run_tracking.delete_record("experiments", V2_REFERENCE_ID)
    assert (
        tmp_path / "experiments" / f"{V2_REFERENCE_ID}.json"
    ).read_bytes() == original_bytes


def test_failed_run_returns_version_and_trace_in_http_response(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))

    def fail(_state):
        raise ValueError("Invalid route")

    monkeypatch.setattr(graph, "router", fail)
    handler = WebAppHandler.__new__(WebAppHandler)
    payload = json.dumps(
        {"task_id": "test", "question": "A question", "file_name": ""}
    ).encode()
    handler.path = "/api/run"
    handler.headers = {"Content-Length": str(len(payload))}
    handler.rfile = BytesIO(payload)
    responses = []
    handler._send_json = lambda status, body: responses.append((status, body))
    handler.do_POST()
    status, body = responses[-1]
    assert status == 400
    assert body["pipeline_version"] == "2"
    assert body["llm_duration_seconds"] == 0
    assert run_tracking.read_record("runs", body["run_id"])["status"] == "error"


def test_reference_archive_retains_exact_records_and_detects_changes(
    monkeypatch, tmp_path
):
    runtime = tmp_path / ".runtime"
    (runtime / "experiments").mkdir(parents=True)
    (runtime / "runs").mkdir()
    answers = []
    for index in range(20):
        run_id = str(uuid4())
        task_id = f"task-{index}"
        answers.append({"task_id": task_id, "run_id": run_id})
        (runtime / "runs" / f"{run_id}.json").write_text(
            json.dumps(
                {"id": run_id, "pipeline_version": "2", "task": {"task_id": task_id}}
            ),
            encoding="utf-8",
        )
    original = json.dumps(
        {"id": V2_REFERENCE_ID, "answers": answers, "config": {"name": "Completo"}}
    ).encode()
    (runtime / "experiments" / f"{V2_REFERENCE_ID}.json").write_bytes(original)
    monkeypatch.setattr(
        baseline_archive.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(stdout=b"source archive"),
    )
    directory = baseline_archive.archive_reference(tmp_path, runtime)
    assert (
        directory / "experiments" / f"{V2_REFERENCE_ID}.json"
    ).read_bytes() == original
    manifest = baseline_archive.verify_archive(directory)
    assert len(manifest["sha256"]) == 22
    assert (
        manifest["sha256"]["source.zip"]
        == hashlib.sha256(b"source archive").hexdigest()
    )
    assert baseline_archive.archive_reference(tmp_path, runtime) == directory
    (directory / "source.zip").write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        baseline_archive.archive_reference(tmp_path, runtime)


def test_archive_verifier_rejects_external_paths(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"sha256": {"../outside": "digest"}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="outside"):
        baseline_archive.verify_archive(tmp_path)
