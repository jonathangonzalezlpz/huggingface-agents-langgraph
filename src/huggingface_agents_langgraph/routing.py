"""Deterministic routing based on task attachment extensions."""

from pathlib import Path
from typing import TypedDict

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
    """Choose a route from the attachment extension, if it is recognized."""
    extension = Path(state["file_name"]).suffix.lower()
    return {"route": EXTENSION_ROUTES.get(extension, "unimplemented")}
