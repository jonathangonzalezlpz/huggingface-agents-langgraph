"""GAIA questions (from the course service) and their attachments."""

import mimetypes
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote

from huggingface_agents_langgraph.api import course_service
from huggingface_agents_langgraph.api.http import (
    BytesResponse,
    Request,
    Response,
    failure,
)
from huggingface_agents_langgraph.api.router import Router
from huggingface_agents_langgraph.attachments import get_attachment_path


def _questions(endpoint: str) -> Response:
    try:
        body = course_service.fetch_questions(endpoint)
    except (HTTPError, URLError, TimeoutError) as error:
        return failure(502, f"Could not fetch questions: {error}")
    return BytesResponse(200, body, "application/json; charset=utf-8")


def list_questions(request: Request) -> Response:
    return _questions("/questions")


def random_question(request: Request) -> Response:
    return _questions("/random-question")


def get_attachment(request: Request) -> Response:
    """Download the file a question comes with, by task id."""
    task_id = unquote(request.params["task_id"])
    if not task_id or "/" in task_id or "\\" in task_id:
        return failure(400, "Invalid task ID")
    try:
        attachment_path = get_attachment_path(task_id)
    except Exception as error:
        return failure(502, f"Could not retrieve attachment: {error}")
    if attachment_path is None:
        return failure(404, "This question has no attachment")
    content_type = mimetypes.guess_type(attachment_path.name)[0]
    disposition = "attachment; filename*=UTF-8''" + quote(attachment_path.name)
    return BytesResponse(
        200,
        attachment_path.read_bytes(),
        content_type or "application/octet-stream",
        {"Content-Disposition": disposition},
    )


def register(router: Router) -> None:
    router.add("GET", "/api/questions")(list_questions)
    router.add("GET", "/api/random-question")(random_question)
    router.add("GET", "/api/files/{task_id*}")(get_attachment)
