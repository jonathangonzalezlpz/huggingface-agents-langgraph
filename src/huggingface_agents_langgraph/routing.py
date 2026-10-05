"""Deterministic routing based on task attachment extensions."""

from pathlib import Path
from typing import TypedDict

from huggingface_agents_langgraph.llm import ChatMessage, chat_completion
from huggingface_agents_langgraph.state import AgentState, Route

EXTENSION_ROUTES: dict[str, Route] = {
    ".py": "code",
    ".xlsx": "spreadsheet",
    ".pdf": "document",
}


class RouterUpdate(TypedDict):
    """State fields produced by the router node."""

    route: Route


def router(state: AgentState) -> RouterUpdate:
    """Route known attachments by type and classify questions without files."""
    file_name = state["file_name"].strip()
    if file_name:
        extension = Path(file_name).suffix.lower()
        return {"route": EXTENSION_ROUTES.get(extension, "unimplemented")}

    return {"route": _classify_question(state["question"])}


def _classify_question(question: str) -> Route:
    """Use the LLM to choose the required capability for a no-file task."""
    messages: list[ChatMessage] = [
        {
            "role": "system",
            "content": (
                "Classify the task into exactly one route and return only its name: "
                "direct, web, or wikipedia. Use direct when the answer can be "
                "derived from the question using language understanding, reasoning, "
                "or calculation, without external facts. Use wikipedia when the "
                "question explicitly requests Wikipedia or an encyclopedia source. "
                "Otherwise use web when external research or current/source-specific "
                "facts are needed."
            ),
        },
        {"role": "user", "content": question},
    ]
    route = chat_completion(messages).strip().lower().strip("\"'` .")
    if route == "direct":
        return "direct"
    if route == "web":
        return "web"
    if route == "wikipedia":
        return "wikipedia"
    raise ValueError(f"LLM returned an unsupported question route: {route!r}")
