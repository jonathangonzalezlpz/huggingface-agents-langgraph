"""The vetted tools an architecture may use, as LangChain tools.

Every tool here is code of this project: nothing is loaded from a name, a URL or a
hub at run time. Each one takes a single text input and returns ``Evidence``, the
common currency the rest of the pipeline already understands. The ``network`` and
``filesystem`` flags say what a tool can reach, so the editor can show it.
"""

from collections.abc import Callable
from dataclasses import dataclass

from langchain_core.tools import BaseTool, StructuredTool

from huggingface_agents_langgraph.calculation import calculate
from huggingface_agents_langgraph.state import Evidence
from huggingface_agents_langgraph.web_research import (
    _search_web,
    _search_wikipedia,
    fetch_source,
)


@dataclass(frozen=True)
class ToolSpec:
    """A tool's identity, what it is for, what it can reach, and how to run it."""

    id: str
    description: str
    network: bool
    filesystem: bool
    run: Callable[[str], list[Evidence]]


def _calculation(expression: str) -> list[Evidence]:
    return [
        {
            "content": calculate(expression),
            "source": expression,
            "source_type": "calculation",
        }
    ]


# The calls go through the module globals so each can be replaced in tests.
TOOLS: dict[str, ToolSpec] = {
    spec.id: spec
    for spec in (
        ToolSpec(
            "web_search",
            "Search the web for the given query and read the best pages.",
            network=True,
            filesystem=False,
            run=lambda text: _search_web(text),
        ),
        ToolSpec(
            "wikipedia",
            "Search Wikipedia for the given query and read the matching articles.",
            network=True,
            filesystem=False,
            run=lambda text: _search_wikipedia(text),
        ),
        ToolSpec(
            "fetch_url",
            "Read the web page or PDF at the given http(s) address.",
            network=True,
            filesystem=False,
            run=lambda text: fetch_source(text),
        ),
        ToolSpec(
            "calculate",
            "Evaluate one pure Python expression in an isolated, timed process.",
            network=False,
            filesystem=False,
            run=_calculation,
        ),
    )
}


def as_langchain_tool(spec: ToolSpec) -> BaseTool:
    """The tool in the LangChain interface, with one text argument named ``query``."""
    return StructuredTool.from_function(
        func=lambda query: spec.run(query),
        name=spec.id,
        description=spec.description,
    )


def run_tool(tool_id: str, text: str) -> list[Evidence]:
    """Run a registered tool through its LangChain interface."""
    spec = TOOLS[tool_id]
    return as_langchain_tool(spec).invoke({"query": text})
