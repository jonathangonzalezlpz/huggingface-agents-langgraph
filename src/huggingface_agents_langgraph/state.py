"""Typed state definitions for the LangGraph workflow."""

from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from huggingface_agents_langgraph.experiments import ExperimentConfig

Route = Literal[
    "code",
    "spreadsheet",
    "document",
    "multimedia",
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
    links: NotRequired[list[str]]
    source_id: NotRequired[str]


class AgentState(TypedDict):
    """Data passed between the workflow's nodes."""

    task_id: str
    question: str
    file_name: str
    file_path: NotRequired[Path | None]
    route: NotRequired[Route]
    evidence: NotRequired[list[Evidence]]
    submitted_answer: NotRequired[str]
    experiment: NotRequired[ExperimentConfig]
    draft_answer: NotRequired[str]
    research_action: NotRequired[dict]
    research_steps: NotRequired[int]
    action_history: NotRequired[list[str]]
    research_notes: NotRequired[list[str]]
    answer_warnings: NotRequired[list[str]]
    reasoning_warnings: NotRequired[list[str]]
    video_path: NotRequired[Path]
    run_id: NotRequired[str]
    source_links: NotRequired[list[str]]
    # Fields written by the optional LLM-role components (llm_roles.py); the V3.1
    # graph never reads or writes them.
    plan: NotRequired[list[str]]
    verdict: NotRequired[dict]
    candidates: NotRequired[list[str]]
    revision_count: NotRequired[int]
