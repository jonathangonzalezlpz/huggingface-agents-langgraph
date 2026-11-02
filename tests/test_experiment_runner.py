"""run_experiment: stopping between questions and reporting progress."""

import pytest

from huggingface_agents_langgraph import experiment_runner, run_tracking
from huggingface_agents_langgraph.experiments import DEFAULT_EXPERIMENT

TASKS = [
    {"task_id": f"t{n}", "question": f"q{n}", "file_name": ""} for n in range(1, 4)
]


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(
        experiment_runner, "source_identity", lambda: {"source_sha256": "x"}
    )
    monkeypatch.setattr(
        experiment_runner,
        "run_pipeline",
        lambda task: {
            "submitted_answer": "a",
            "error": None,
            "route": "direct",
            "run_id": None,
            "llm_duration_seconds": 0.1,
        },
    )


def test_stops_before_the_next_question_and_marks_the_record_cancelled():
    calls = []
    record = experiment_runner.run_experiment(
        TASKS,
        DEFAULT_EXPERIMENT,
        group_id="g",
        score=False,
        should_stop=lambda: bool(calls) and calls[-1] >= 1,
        on_progress=lambda r: calls.append(len(r["answers"])),
    )
    assert [a["task_id"] for a in record["answers"]] == ["t1"]
    assert record["status"] == "cancelled"
    stored = run_tracking.read_record("experiments", record["id"])
    assert stored["status"] == "cancelled"


def test_reports_progress_after_every_write():
    seen = []
    experiment_runner.run_experiment(
        TASKS,
        DEFAULT_EXPERIMENT,
        group_id="g",
        score=False,
        on_progress=lambda r: seen.append((r["status"], len(r["answers"]))),
    )
    assert seen[0] == ("running", 0)
    assert [count for _, count in seen[1:4]] == [1, 2, 3]
    assert seen[-1] == ("completed", 3)


def test_a_cancelled_record_can_be_resumed_to_completion():
    cancelled = experiment_runner.run_experiment(
        TASKS,
        DEFAULT_EXPERIMENT,
        group_id="g",
        score=False,
        should_stop=lambda: True,
    )
    assert cancelled["answers"] == []
    assert cancelled["status"] == "cancelled"
    resumed = experiment_runner.run_experiment(
        TASKS,
        DEFAULT_EXPERIMENT,
        group_id="g",
        score=False,
        record=cancelled,
    )
    assert resumed["status"] == "completed"
    assert len(resumed["answers"]) == 3
    assert resumed["id"] == cancelled["id"]
