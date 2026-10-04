"""Typed state definitions for the LangGraph workflow."""

from pathlib import Path
from typing import Literal, NotRequired, TypedDict

Route = Literal[
    "code",
    "spreadsheet",
    "document",
    "web",
    "wikipedia",
    "direct",
    "unimplemented",
]


class Evidence(TypedDict):
    """Information relevant to answering a task, with its provenance."""

    content: str
    source: str
    source_type: str


class AgentState(TypedDict):
    """Data passed between the workflow's nodes."""

    task_id: str
    question: str
    file_name: str
    file_path: NotRequired[Path | None]
    route: NotRequired[Route]
    evidence: NotRequired[list[Evidence]]
    answer_candidate: NotRequired[str]
    submitted_answer: NotRequired[str]
