"""Deterministic routing based on task attachment extensions."""

import json
import re
from pathlib import Path
from typing import NotRequired, TypedDict

from huggingface_agents_langgraph.experiments import (
    DEFAULT_EXPERIMENT,
    ModelSelection,
    is_capability_enabled,
)
from huggingface_agents_langgraph.llm import ChatMessage, chat_completion
from huggingface_agents_langgraph.state import AgentState, Route

EXTENSION_ROUTES: dict[str, Route] = {
    ".py": "code",
    ".xlsx": "spreadsheet",
    ".pdf": "document",
    ".mp3": "multimedia",
    ".wav": "multimedia",
    ".m4a": "multimedia",
    ".flac": "multimedia",
    ".ogg": "multimedia",
    ".aac": "multimedia",
    ".mp4": "multimedia",
    ".mov": "multimedia",
    ".mkv": "multimedia",
    ".webm": "multimedia",
    ".avi": "multimedia",
    ".png": "multimedia",
    ".jpg": "multimedia",
    ".jpeg": "multimedia",
    ".webp": "multimedia",
    ".bmp": "multimedia",
}
VIDEO_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?v=[\w-]+|youtu\.be/[\w-]+)",
    re.IGNORECASE,
)
ROUTE_CAPABILITIES = {
    "code": "code",
    "spreadsheet": "spreadsheet",
    "document": "document",
    "multimedia": "multimedia",
}


def capability_for_attachment(file_name: str) -> str | None:
    """Return the graph capability associated with an attachment filename."""
    route = EXTENSION_ROUTES.get(Path(file_name).suffix.lower())
    return ROUTE_CAPABILITIES.get(route or "")


class RouterUpdate(TypedDict):
    """State fields produced by the router node."""

    route: Route
    research_notes: NotRequired[list[str]]


def router(state: AgentState) -> RouterUpdate:
    """Route known attachments by type and classify questions without files."""
    experiment = state.get("experiment", DEFAULT_EXPERIMENT)
    if experiment["force_direct"]:
        return {"route": "direct"}

    file_name = state["file_name"].strip()
    if file_name:
        extension = Path(file_name).suffix.lower()
        route = EXTENSION_ROUTES.get(extension, "unimplemented")
        capability = ROUTE_CAPABILITIES.get(route)
        if capability and not is_capability_enabled(experiment, capability):
            return {"route": "direct"}
        return {"route": route}

    if VIDEO_URL_PATTERN.search(state["question"]):
        return {"route": "multimedia"}

    try:
        route = _classify_question(state["question"], experiment.get("model"))
    except ValueError as error:
        return {"route": "direct", "research_notes": [f"Router fallback: {error}"]}
    if route in {"web", "wikipedia"} and not is_capability_enabled(experiment, "web"):
        return {"route": "direct"}
    return {"route": route}


def _classify_question(question: str, model: ModelSelection | None = None) -> Route:
    """Use the LLM to choose the required capability for a no-file task."""
    messages: list[ChatMessage] = [
        {
            "role": "system",
            "content": (
                "Classify the task into exactly one route and return only its name: "
                "direct, web, or wikipedia. Use direct when the answer can be "
                "derived from the question using language understanding, reasoning, "
                "or calculation and stable general knowledge. Use wikipedia when the "
                "question explicitly requests Wikipedia or an encyclopedia source. "
                "Otherwise use web when external research or current/source-specific "
                "facts are needed. /no_think"
            ),
        },
        {"role": "user", "content": question},
    ]
    for _ in range(2):
        route = (
            chat_completion(messages, max_tokens=32, model=model)
            .strip()
            .lower()
            .strip("\"'` .")
        )
        if route in {"direct", "web", "wikipedia"}:
            return route
        try:
            parsed = json.loads(route)
            if isinstance(parsed, dict) and parsed.get("route") in {
                "direct",
                "web",
                "wikipedia",
            }:
                return parsed["route"]
        except ValueError:
            pass
        messages.append(
            {
                "role": "user",
                "content": (
                    "Invalid route. Return exactly direct, web, or wikipedia. "
                    "Do not answer the question. /no_think"
                ),
            }
        )
    raise ValueError("Classifier returned invalid routes twice")
