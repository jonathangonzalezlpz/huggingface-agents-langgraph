"""Input preprocessing for the LangGraph workflow."""

from typing import TypedDict

from huggingface_agents_langgraph.state import AgentState


class PreprocessingUpdate(TypedDict):
    """Fields updated by the preprocessing node."""

    question: str


def preprocessing(state: AgentState) -> PreprocessingUpdate:
    """Validate required input fields and trim surrounding question whitespace."""
    task_id = state["task_id"]
    question = state["question"]

    if not task_id.strip():
        raise ValueError("task_id must not be empty")
    if not question.strip():
        raise ValueError("question must not be empty")

    return {"question": question.strip()}
