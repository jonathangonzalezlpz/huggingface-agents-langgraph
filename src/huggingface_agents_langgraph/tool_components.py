"""Components that gather evidence with the vetted tools.

They add to the evidence already in the state instead of replacing it, so several of
them can be chained before reasoning. Failures are reported by the caller as notes
(these components are registered with error recovery), never swallowed here.
"""

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from huggingface_agents_langgraph.evidence_selection import select_relevant_evidence
from huggingface_agents_langgraph.llm import chat_completion
from huggingface_agents_langgraph.multimedia_processing import (
    _inspect_image,
    _transcribe,
)
from huggingface_agents_langgraph.state import AgentState, Evidence
from huggingface_agents_langgraph.tool_library import TOOLS, run_tool

Handler = Any
_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def _accumulate(state: AgentState, found: list[Evidence], label: str) -> dict[str, Any]:
    """Add ``found`` to the gathered evidence, moving page links to ``source_links``."""
    links = list(state.get("source_links", []))
    items: list[Evidence] = []
    for item in found:
        item = dict(item)  # type: ignore[assignment]
        links.extend(item.pop("links", []))  # type: ignore[misc]
        items.append(item)  # type: ignore[arg-type]
    update: dict[str, Any] = {"source_links": list(dict.fromkeys(links))[-80:]}
    if not items:
        update["research_notes"] = [
            *state.get("research_notes", []),
            f"{label} returned no evidence.",
        ]
        return update
    combined = [*state.get("evidence", []), *items]
    update["evidence"] = select_relevant_evidence(state["question"], combined)
    return update


def _tool_input(state: AgentState, source: str, text: str) -> str:
    if source == "question":
        return state["question"]
    if source == "draft_answer":
        value = state.get("draft_answer", "")
        if not value.strip():
            raise ValueError("The draft_answer is empty; nothing to feed the tool")
        return value
    if not text.strip():
        raise ValueError("input_from is 'text' but the text parameter is empty")
    return text


def build_tool_node(params: Mapping[str, Any]) -> Handler:
    """Run one registered tool on the question, the draft answer or a fixed text."""
    tool, source, text = params["tool"], params["input_from"], params["text"]
    if tool not in TOOLS:
        raise ValueError(f"Unknown tool '{tool}'")

    def tool_node(state: AgentState) -> dict[str, Any]:
        found = run_tool(tool, _tool_input(state, source, text))
        return _accumulate(state, found, tool)

    return tool_node


def _named_search(tool: str, params: Mapping[str, Any]) -> Handler:
    query = params["query"]

    def search(state: AgentState) -> dict[str, Any]:
        found = run_tool(tool, query.strip() or state["question"])
        return _accumulate(state, found, tool)

    return search


def build_web_search(params: Mapping[str, Any]) -> Handler:
    """Web search on the question, or on a fixed query."""
    return _named_search("web_search", params)


def build_wikipedia_search(params: Mapping[str, Any]) -> Handler:
    """Wikipedia search on the question, or on a fixed query."""
    return _named_search("wikipedia", params)


def build_calculator(params: Mapping[str, Any]) -> Handler:
    """Ask the model for one expression, then evaluate it with the safe calculator."""
    max_tokens = params["max_tokens"]

    def calculator(state: AgentState) -> dict[str, Any]:
        reply = chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "Write one pure Python arithmetic expression that computes "
                        "what the task asks. Return only the expression, no prose. "
                        "/no_think"
                    ),
                },
                {"role": "user", "content": f"Task:\n{state['question']}"},
            ],
            max_tokens=max_tokens,
            model=state.get("experiment", {}).get("model"),
            thinking=False,
        )
        expression = _FENCE.sub("", reply.strip()).strip()
        if not expression:
            raise ValueError("The model returned no expression to calculate")
        return _accumulate(state, run_tool("calculate", expression), "calculate")

    return calculator


def _existing_file(state: AgentState) -> Path:
    file_path = state.get("file_path")
    if file_path is None:
        raise ValueError("file_path is required: this task has no attachment")
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Attachment does not exist: {path}")
    return path


def transcribe_audio(state: AgentState) -> dict[str, Any]:
    """Transcribe the attached audio file."""
    path = _existing_file(state)
    transcript = _transcribe(path)
    if not transcript.strip():
        raise ValueError("The audio produced no transcript")
    found: list[Evidence] = [
        {
            "content": f"Audio transcription:\n{transcript}",
            "source": str(path),
            "source_type": "audio_transcription",
        }
    ]
    return _accumulate(state, found, "transcribe_audio")


def describe_image(state: AgentState) -> dict[str, Any]:
    """Describe the attached image with the vision model, guided by the question."""
    path = _existing_file(state)
    found = [_inspect_image(path, state["question"], str(path))]
    if not found[0]["content"].strip():
        raise ValueError("The vision model returned no description")
    return _accumulate(state, found, "describe_image")
