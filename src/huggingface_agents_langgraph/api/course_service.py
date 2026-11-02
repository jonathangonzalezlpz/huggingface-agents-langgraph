"""Outbound calls to the course's scoring service (questions and official score)."""

import json
from urllib.request import Request, urlopen

SCORING_API_URL = "https://agents-course-unit4-scoring.hf.space"
QUESTIONS_TIMEOUT_SECONDS = 30
SUBMIT_TIMEOUT_SECONDS = 60


def fetch_questions(endpoint: str) -> bytes:
    """The raw JSON of ``/questions`` or ``/random-question``."""
    with urlopen(
        f"{SCORING_API_URL}{endpoint}", timeout=QUESTIONS_TIMEOUT_SECONDS
    ) as response:
        return response.read()


def submit_answers(username: str, agent_code: str, answers: list[dict]) -> object:
    """Send the answers to the official evaluator; this publishes to its leaderboard."""
    body = json.dumps(
        {"username": username, "agent_code": agent_code, "answers": answers}
    ).encode("utf-8")
    request = Request(
        f"{SCORING_API_URL}/submit",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=SUBMIT_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))
