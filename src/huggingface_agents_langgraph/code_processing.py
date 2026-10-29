"""Code processing node for tasks with Python attachments."""

import subprocess
import sys
from pathlib import Path
from typing import TypedDict

from huggingface_agents_langgraph.config import (
    CODE_EXECUTION_TIMEOUT_SECONDS,
)
from huggingface_agents_langgraph.llm import ChatMessage, chat_completion
from huggingface_agents_langgraph.state import AgentState, Evidence


class CodeProcessingUpdate(TypedDict):
    """State fields produced by the code processing node."""

    evidence: list[Evidence]


def code_processing(state: AgentState) -> CodeProcessingUpdate:
    """Use the task intent to choose between inspecting and running Python code."""
    file_path = state.get("file_path")
    if file_path is None:
        raise ValueError("file_path is required to process a Python attachment")

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Python attachment does not exist: {path}")

    source = path.read_text(encoding="utf-8")
    action = _choose_code_action(state["question"], source)
    if action == "inspect":
        evidence: Evidence = {
            "content": source,
            "source": str(path),
            "source_type": "python_source",
        }
        return {"evidence": [evidence]}

    return _execute_python(path, source)


def _choose_code_action(question: str, source: str) -> str:
    """Ask the configured chat model whether the task requires code execution."""
    messages: list[ChatMessage] = [
        {
            "role": "system",
            "content": (
                "Decide how to process a Python attachment for the user's task. "
                "Return exactly one word: execute if answering requires the "
                "program's runtime output; otherwise return inspect. Questions "
                "asking to explain, review, or identify something in the source "
                "should use inspect. /no_think"
            ),
        },
        {
            "role": "user",
            "content": f"Task question:\n{question}\n\nPython source:\n{source}",
        },
    ]
    action = chat_completion(messages, max_tokens=32).lower()

    if action not in {"execute", "inspect"}:
        raise ValueError(
            f"LLM returned an unsupported code-processing action: {action!r}"
        )
    return action


def _execute_python(path: Path, source: str) -> CodeProcessingUpdate:
    """Run the attachment and return its standard output as evidence."""
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-c", source],
            capture_output=True,
            check=False,
            cwd=path.parent,
            text=True,
            timeout=CODE_EXECUTION_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise TimeoutError(
            f"Python attachment exceeded {CODE_EXECUTION_TIMEOUT_SECONDS} seconds"
        ) from error

    if result.returncode != 0:
        raise RuntimeError(
            f"Python attachment exited with status {result.returncode}: "
            f"{result.stderr.strip()}"
        )

    output = result.stdout.strip()
    if not output:
        raise ValueError("Python attachment produced no output")

    evidence: Evidence = {
        "content": output,
        "source": str(path),
        "source_type": "python_execution",
    }
    return {"evidence": [evidence]}
