"""Score stored experiments on the server.

The answers are read from the stored record, never taken from the client, so the
score always describes what the agent actually produced.
"""

from collections.abc import Callable
from typing import Any

from huggingface_agents_langgraph.local_evaluation import evaluate_validation_answers
from huggingface_agents_langgraph.run_tracking import read_record, write_record

QUESTION_COUNT = 20
_OFFICIAL_FIELDS = ("score", "correct_count", "total_attempted", "message")


def _complete_answers(record: dict) -> list[dict]:
    answers = record.get("answers")
    if not isinstance(answers, list) or len(answers) != QUESTION_COUNT:
        raise ValueError(f"Exactly {QUESTION_COUNT} answers are required")
    return [
        {
            "task_id": answer["task_id"],
            "submitted_answer": answer.get("submitted_answer") or "",
        }
        for answer in answers
    ]


def evaluate_experiment(
    experiment_id: str,
    evaluator: Callable[[list[dict]], Any] = evaluate_validation_answers,
) -> dict:
    """Mark every answer of a completed experiment and store its local score."""
    record = read_record("experiments", experiment_id)
    result = evaluator(_complete_answers(record))
    correct = {item["task_id"]: item["correct"] for item in result["results"]}
    for answer in record["answers"]:
        answer["locally_correct"] = correct.get(answer["task_id"])
    record["local_score"] = {
        key: value for key, value in result.items() if key != "results"
    }
    write_record("experiments", record)
    return record["local_score"]


def official_answers(experiment_id: str) -> list[dict]:
    """The answers to send to the official evaluator, taken from the record."""
    return _complete_answers(read_record("experiments", experiment_id))


def record_official_score(experiment_id: str, result: dict) -> dict:
    """Keep the official evaluator's verdict on the experiment."""
    record = read_record("experiments", experiment_id)
    kept = {key: result[key] for key in _OFFICIAL_FIELDS if key in result}
    record["score"] = kept
    write_record("experiments", record)
    return kept
