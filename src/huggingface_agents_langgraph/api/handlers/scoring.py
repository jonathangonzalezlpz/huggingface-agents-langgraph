"""Scoring: local evaluation of 20 answers, and the official submission."""

import json
from urllib.error import HTTPError, URLError

from huggingface_agents_langgraph.api import course_service
from huggingface_agents_langgraph.api.http import Request, Response, failure, ok
from huggingface_agents_langgraph.api.router import Router
from huggingface_agents_langgraph.application.experiment_scoring import (
    official_answers,
    record_official_score,
)
from huggingface_agents_langgraph.domain.local_evaluation import (
    evaluate_validation_answers,
)

ANSWER_COUNT = 20


def check_answers(answers: object) -> list[dict]:
    """The answers, if there are exactly 20 and each names its task and its text."""
    if not isinstance(answers, list) or len(answers) != ANSWER_COUNT:
        raise ValueError("Exactly 20 answers are required")
    for answer in answers:
        if (
            not isinstance(answer, dict)
            or not isinstance(answer.get("task_id"), str)
            or not isinstance(answer.get("submitted_answer"), str)
        ):
            raise ValueError("Each answer needs task_id and submitted_answer")
    return answers


def evaluate_answers(request: Request) -> Response:
    """Score 20 submitted answers locally, without touching the leaderboard."""
    try:
        payload = request.json_value()
        answers = payload.get("answers") if isinstance(payload, dict) else None
        return ok(evaluate_validation_answers(check_answers(answers)))
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return failure(400, str(error))
    except RuntimeError as error:
        return failure(503, str(error))


def _required_text(payload: dict, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _answers_to_send(payload: dict) -> tuple[list[dict], str | None]:
    """The answers and, if they come from a stored experiment, its id.

    A stored experiment is the only source of its answers: whatever the client
    sends alongside its id is ignored.
    """
    experiment_id = payload.get("experiment_id")
    if experiment_id is None:
        return check_answers(payload.get("answers")), None
    if not isinstance(experiment_id, str):
        raise ValueError("experiment_id must be a string")
    return check_answers(official_answers(experiment_id)), experiment_id


def _remember_verdict(experiment_id: str, result: object) -> object:
    """Keep the verdict on the experiment; say whether that worked."""
    if not isinstance(result, dict):
        return result
    try:
        record_official_score(experiment_id, result)
    except (ValueError, OSError):
        return {**result, "saved": False}
    return {**result, "saved": True}


def submit_score(request: Request) -> Response:
    """Send the answers to the official evaluator. This publishes to a leaderboard."""
    try:
        payload = request.json_value()
        if not isinstance(payload, dict):
            raise ValueError("Score request must be a JSON object")
        username = _required_text(payload, "username")
        agent_code = _required_text(payload, "agent_code")
        answers, experiment_id = _answers_to_send(payload)
        result = course_service.submit_answers(username, agent_code, answers)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return failure(400, str(error))
    except FileNotFoundError:
        return failure(404, "Experiment not found")
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        return failure(502, f"Official scoring failed: {error}")
    if experiment_id is not None:
        result = _remember_verdict(experiment_id, result)
    return ok(result)


def register(router: Router) -> None:
    router.add("POST", "/api/evaluate")(evaluate_answers)
    router.add("POST", "/api/score")(submit_score)
