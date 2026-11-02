"""run_experiment: stopping between questions and reporting progress."""

import pytest

from huggingface_agents_langgraph.adapters import records
from huggingface_agents_langgraph.application import experiment_run
from huggingface_agents_langgraph.domain.experiments import DEFAULT_EXPERIMENT

TASKS = [
    {"task_id": f"t{n}", "question": f"q{n}", "file_name": ""} for n in range(1, 4)
]


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(records, "RUNTIME_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(
        experiment_run, "source_identity", lambda: {"source_sha256": "x"}
    )
    monkeypatch.setattr(
        experiment_run,
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
    record = experiment_run.run_experiment(
        TASKS,
        DEFAULT_EXPERIMENT,
        group_id="g",
        score=False,
        should_stop=lambda: bool(calls) and calls[-1] >= 1,
        on_progress=lambda r: calls.append(len(r["answers"])),
    )
    assert [a["task_id"] for a in record["answers"]] == ["t1"]
    assert record["status"] == "cancelled"
    stored = records.read_record("experiments", record["id"])
    assert stored["status"] == "cancelled"


def test_reports_progress_after_every_write():
    seen = []
    experiment_run.run_experiment(
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
    cancelled = experiment_run.run_experiment(
        TASKS,
        DEFAULT_EXPERIMENT,
        group_id="g",
        score=False,
        should_stop=lambda: True,
    )
    assert cancelled["answers"] == []
    assert cancelled["status"] == "cancelled"
    resumed = experiment_run.run_experiment(
        TASKS,
        DEFAULT_EXPERIMENT,
        group_id="g",
        score=False,
        record=cancelled,
    )
    assert resumed["status"] == "completed"
    assert len(resumed["answers"]) == 3
    assert resumed["id"] == cancelled["id"]


def test_an_answer_carries_the_figures_of_its_run_trace(monkeypatch):
    trace = {
        "calls": [
            {
                "model_load_seconds": 2,
                "response": {
                    "choices": [{"finish_reason": "length"}],
                    "usage": {"completion_tokens": 5},
                },
            },
            {"response": {"choices": [{"finish_reason": "stop"}], "usage": {}}},
        ],
        "steps": [
            {"node": "router", "duration_seconds": 1},
            {"node": "router", "duration_seconds": 2},
            {"node": "review", "duration_seconds": 4},
        ],
        "resources": {"gpu": 1},
    }
    monkeypatch.setattr(
        experiment_run,
        "run_pipeline",
        lambda task: {"submitted_answer": "a", "run_id": "r1", "route": "direct"},
    )
    monkeypatch.setattr(experiment_run, "read_record", lambda *_a: trace)
    record = experiment_run.run_experiment(
        TASKS[:1], DEFAULT_EXPERIMENT, group_id="g", score=False
    )
    answer = record["answers"][0]
    assert answer["llm_calls"] == 2
    assert answer["model_load_seconds"] == 2
    assert answer["truncated_calls"] == 1
    assert answer["completion_tokens"] == 5
    assert answer["stage_seconds"] == {"router": 3, "review": 4}
    assert answer["resources"] == {"gpu": 1}
    assert record["metrics"]["count"] == 1


def test_a_failed_task_is_recorded_as_an_error_answer(monkeypatch):
    def failing(task):
        raise RuntimeError("model down")

    monkeypatch.setattr(experiment_run, "run_pipeline", failing)
    record = experiment_run.run_experiment(
        TASKS[:1], DEFAULT_EXPERIMENT, group_id="g", score=False
    )
    answer = record["answers"][0]
    assert answer["error"] == "model down"
    assert answer["submitted_answer"] == ""
    assert answer["route"] == "error"


def test_a_full_set_is_scored_locally(monkeypatch):
    tasks = [{"task_id": f"t{n}", "question": "q", "file_name": ""} for n in range(20)]
    monkeypatch.setattr(
        experiment_run,
        "evaluate_validation_answers",
        lambda answers: {
            "correct": 1,
            "results": [
                {"task_id": a["task_id"], "correct": a["task_id"] == "t0"}
                for a in answers
            ],
        },
    )
    record = experiment_run.run_experiment(tasks, DEFAULT_EXPERIMENT, group_id="g")
    assert record["evaluation_scope"] == "full"
    assert record["local_score"] == {"correct": 1}
    assert [a["locally_correct"] for a in record["answers"]][:2] == [True, False]


def test_a_scoring_failure_is_kept_without_losing_the_run(monkeypatch):
    tasks = [{"task_id": f"t{n}", "question": "q", "file_name": ""} for n in range(20)]

    def failing(_answers):
        raise RuntimeError("no dataset")

    monkeypatch.setattr(experiment_run, "evaluate_validation_answers", failing)
    record = experiment_run.run_experiment(tasks, DEFAULT_EXPERIMENT, group_id="g")
    assert record["status"] == "completed"
    assert record["evaluation_error"] == "no dataset"


def test_resuming_with_other_inputs_is_refused():
    first = experiment_run.run_experiment(
        TASKS, DEFAULT_EXPERIMENT, group_id="g", score=False, should_stop=lambda: True
    )
    with pytest.raises(ValueError, match="changed"):
        experiment_run.run_experiment(
            TASKS[:2], DEFAULT_EXPERIMENT, group_id="g", score=False, record=first
        )


def test_duplicate_task_ids_are_refused():
    with pytest.raises(ValueError, match="duplicate"):
        experiment_run.run_experiment(
            [TASKS[0], TASKS[0]], DEFAULT_EXPERIMENT, group_id="g", score=False
        )
