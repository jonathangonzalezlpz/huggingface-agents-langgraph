"""Scoring a stored experiment on the server, so the client never rewrites it."""

import pytest

from huggingface_agents_langgraph import run_tracking
from huggingface_agents_langgraph.experiment_scoring import (
    evaluate_experiment,
    official_answers,
    record_official_score,
)

EXPERIMENT_ID = "55555555-5555-4555-8555-555555555555"


@pytest.fixture(autouse=True)
def runtime_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))


def store(count=20, **extra):
    record = {
        "id": EXPERIMENT_ID,
        "config": {"name": "x"},
        "answers": [
            {"task_id": f"t{n}", "submitted_answer": f"a{n}", "route": "direct"}
            for n in range(count)
        ],
        **extra,
    }
    run_tracking.write_record("experiments", record)
    return record


def fake_evaluator(answers):
    results = [
        {"task_id": a["task_id"], "correct": a["submitted_answer"] in {"a0", "a1"}}
        for a in answers
    ]
    correct = sum(r["correct"] for r in results)
    return {
        "score": correct * 5.0,
        "correct_count": correct,
        "total_attempted": len(results),
        "results": results,
    }


def test_local_evaluation_marks_each_answer_and_stores_the_totals():
    store()
    score = evaluate_experiment(EXPERIMENT_ID, evaluator=fake_evaluator)
    assert score == {"score": 10.0, "correct_count": 2, "total_attempted": 20}
    saved = run_tracking.read_record("experiments", EXPERIMENT_ID)
    assert saved["local_score"] == score
    assert [a["locally_correct"] for a in saved["answers"]][:3] == [True, True, False]


def test_the_evaluator_only_sees_task_ids_and_answers():
    store()
    seen = []

    def spy(answers):
        seen.extend(answers)
        return fake_evaluator(answers)

    evaluate_experiment(EXPERIMENT_ID, evaluator=spy)
    assert set(seen[0]) == {"task_id", "submitted_answer"}


def test_refuses_to_score_an_incomplete_experiment():
    store(count=5)
    with pytest.raises(ValueError, match="20"):
        evaluate_experiment(EXPERIMENT_ID, evaluator=fake_evaluator)
    assert "local_score" not in run_tracking.read_record("experiments", EXPERIMENT_ID)


def test_a_missing_experiment_is_not_found():
    with pytest.raises(FileNotFoundError):
        evaluate_experiment(EXPERIMENT_ID, evaluator=fake_evaluator)


def test_an_evaluator_failure_leaves_the_record_untouched():
    store()

    def broken(_answers):
        raise RuntimeError("dataset unavailable")

    with pytest.raises(RuntimeError):
        evaluate_experiment(EXPERIMENT_ID, evaluator=broken)
    assert "local_score" not in run_tracking.read_record("experiments", EXPERIMENT_ID)


def test_official_answers_come_from_the_stored_record():
    store()
    answers = official_answers(EXPERIMENT_ID)
    assert len(answers) == 20
    assert answers[0] == {"task_id": "t0", "submitted_answer": "a0"}


def test_official_answers_need_a_complete_experiment():
    store(count=19)
    with pytest.raises(ValueError):
        official_answers(EXPERIMENT_ID)


def test_the_official_result_keeps_only_known_fields():
    store()
    kept = record_official_score(
        EXPERIMENT_ID,
        {
            "score": 45.0,
            "correct_count": 9,
            "total_attempted": 20,
            "message": "ok",
            "username": "someone",
            "agent_code": "https://x",
        },
    )
    assert kept == {
        "score": 45.0,
        "correct_count": 9,
        "total_attempted": 20,
        "message": "ok",
    }
    assert run_tracking.read_record("experiments", EXPERIMENT_ID)["score"] == kept
