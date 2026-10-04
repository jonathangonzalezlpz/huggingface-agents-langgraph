"""Code processing node for tasks with Python attachments."""

from typing import TypedDict

from huggingface_agents_langgraph.state import AgentState, Evidence


class CodeProcessingUpdate(TypedDict):
    """State fields produced by the code processing node."""

    evidence: list[Evidence]


def code_processing(state: AgentState) -> CodeProcessingUpdate:
    """Process a Python attachment and return evidence for the task."""
    raise NotImplementedError
