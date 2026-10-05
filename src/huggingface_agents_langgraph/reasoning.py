"""Reasoning node that answers a task from acquired evidence."""

import json
from typing import TypedDict

from huggingface_agents_langgraph.llm import ChatMessage, chat_completion
from huggingface_agents_langgraph.state import AgentState


class ReasoningUpdate(TypedDict):
    """State fields produced by the reasoning node."""

    answer_candidate: str


def reasoning(state: AgentState) -> ReasoningUpdate:
    """Derive an answer candidate from the question and its evidence."""
    evidence = state.get("evidence", [])
    if not evidence:
        raise ValueError("evidence is required to reason about the task")

    messages: list[ChatMessage] = [
        {
            "role": "system",
            "content": (
                "Answer the user's question using only the supplied evidence. "
                "If the evidence contains program output, use that output. "
                "Return only the answer candidate, without explanation or formatting."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question:\n{state['question']}\n\nEvidence:\n"
                f"{json.dumps(evidence, ensure_ascii=False)}"
            ),
        },
    ]
    return {"answer_candidate": chat_completion(messages)}
