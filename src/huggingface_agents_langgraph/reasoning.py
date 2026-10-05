"""Reasoning node that answers a task from acquired evidence."""

import json
from typing import TypedDict

from huggingface_agents_langgraph.llm import ChatMessage, chat_completion
from huggingface_agents_langgraph.state import AgentState


class ReasoningUpdate(TypedDict):
    """State fields produced by the reasoning node."""

    answer_candidate: str


def reasoning(state: AgentState) -> ReasoningUpdate:
    """Derive an answer candidate from evidence or a self-contained question."""
    evidence = state.get("evidence", [])
    if evidence:
        system_instruction = (
            "Answer the user's question using only the supplied evidence. "
            "If the evidence contains program output, use that output. "
            "Return only the answer candidate, without explanation or formatting."
        )
        task_content = (
            f"Question:\n{state['question']}\n\nEvidence:\n"
            f"{json.dumps(evidence, ensure_ascii=False)}"
        )
    else:
        system_instruction = (
            "Answer using only information in the question and reasoning that can "
            "be derived from it. Do not search for or introduce external facts. "
            "Return only the answer candidate, without explanation or formatting."
        )
        task_content = state["question"]

    messages: list[ChatMessage] = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": task_content},
    ]
    return {"answer_candidate": chat_completion(messages)}
