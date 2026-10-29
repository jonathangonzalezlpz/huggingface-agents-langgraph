import pytest

from huggingface_agents_langgraph.local_evaluation import score_answers


def _answers() -> list[dict[str, str]]:
    return [
        {"task_id": f"task-{index}", "submitted_answer": f"answer {index}"}
        for index in range(20)
    ]


def test_score_answers_returns_exact_match_results_without_labels() -> None:
    answers = _answers()
    expected = {answer["task_id"]: answer["submitted_answer"] for answer in answers}
    answers[0]["submitted_answer"] = "  ANSWER 0  "
    answers[1]["submitted_answer"] = "wrong"

    result = score_answers(answers, expected)

    assert result["score"] == 95
    assert result["correct_count"] == 19
    assert result["results"][0] == {"task_id": "task-0", "correct": True}
    assert "expected_answer" not in result["results"][0]


def test_score_answers_rejects_incomplete_or_duplicate_runs() -> None:
    answers = _answers()
    with pytest.raises(ValueError, match="Exactly 20"):
        score_answers(answers[:-1], {})

    answers[1]["task_id"] = answers[0]["task_id"]
    with pytest.raises(ValueError, match="Duplicate"):
        score_answers(answers, {})


def test_score_answers_rejects_unknown_task_ids() -> None:
    with pytest.raises(ValueError, match="not present"):
        score_answers(_answers(), {})
