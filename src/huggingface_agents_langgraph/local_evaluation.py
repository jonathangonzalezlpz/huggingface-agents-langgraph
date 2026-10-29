"""Score local experiment outputs against the GAIA validation answers."""

import os
from functools import lru_cache
from typing import TypedDict

from datasets import load_dataset


class SubmittedAnswer(TypedDict):
    """One task answer supplied by a local experiment."""

    task_id: str
    submitted_answer: str


class LocalAnswerScore(TypedDict):
    """Per-task exact-match result without exposing its reference answer."""

    task_id: str
    correct: bool


class LocalEvaluationResult(TypedDict):
    """Aggregate and per-task local evaluation results."""

    score: float
    correct_count: int
    total_attempted: int
    results: list[LocalAnswerScore]


def evaluate_validation_answers(
    answers: list[SubmittedAnswer],
) -> LocalEvaluationResult:
    """Compare a complete course run with the gated GAIA validation split."""
    expected_answers = _load_validation_answers()
    return score_answers(answers, expected_answers)


def score_answers(
    answers: list[SubmittedAnswer], expected_answers: dict[str, str]
) -> LocalEvaluationResult:
    """Apply the Unit 4 evaluator's case-insensitive, whitespace-trimmed match."""
    if len(answers) != 20:
        raise ValueError("Exactly 20 answers are required for local evaluation")

    task_ids: set[str] = set()
    for answer in answers:
        task_id = answer["task_id"]
        if task_id in task_ids:
            raise ValueError(f"Duplicate task_id in local evaluation: {task_id}")
        task_ids.add(task_id)

    missing_ids = task_ids - expected_answers.keys()
    if missing_ids:
        raise ValueError("Some task IDs are not present in GAIA validation")

    results = [
        {
            "task_id": answer["task_id"],
            "correct": answer["submitted_answer"].strip().casefold()
            == expected_answers[answer["task_id"]].strip().lower(),
        }
        for answer in answers
    ]
    correct_count = sum(result["correct"] for result in results)
    return {
        "score": round(correct_count / len(answers) * 100, 2),
        "correct_count": correct_count,
        "total_attempted": len(answers),
        "results": results,
    }


@lru_cache(maxsize=1)
def _load_validation_answers() -> dict[str, str]:
    """Load validation labels once per process; never write them into the repo."""
    token = os.environ.get("HF_TOKEN") or None
    try:
        dataset = load_dataset(
            "gaia-benchmark/GAIA",
            "2023_level1",
            split="validation",
            token=token,
        )
    except Exception as error:
        raise RuntimeError(
            "Could not load GAIA validation answers. Check HF_TOKEN and dataset access."
        ) from error

    answers: dict[str, str] = {}
    for row in dataset:
        task_id = row.get("task_id")
        final_answer = row.get("Final answer")
        if task_id is not None and final_answer is not None:
            answers[str(task_id)] = str(final_answer)
    if not answers:
        raise RuntimeError("GAIA validation did not contain answer labels")
    return answers
