"""Produce the final benchmark answer from a candidate answer."""

from typing import TypedDict

from huggingface_agents_langgraph.llm import ChatMessage, chat_completion
from huggingface_agents_langgraph.state import AgentState


class AnswerProductionUpdate(TypedDict):
    """State fields produced by the answer-production node."""

    submitted_answer: str


def answer_production(state: AgentState) -> AnswerProductionUpdate:
    """Format the candidate as the concise answer required by GAIA."""
    answer_candidate = state.get("answer_candidate")
    if not answer_candidate:
        raise ValueError("answer_candidate is required to produce the final answer")

    messages: list[ChatMessage] = [
        {
            "role": "system",
            "content": (
                "Format the answer for a benchmark that uses exact matching. "
                "Return only the requested answer, with no explanation, greeting, "
                "label, or surrounding quotation marks. Preserve required units "
                "and numeric formatting from the question."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question:\n{state['question']}\n\n"
                f"Answer candidate:\n{answer_candidate}"
            ),
        },
    ]
    return {"submitted_answer": chat_completion(messages).strip()}
