import importlib
from pathlib import Path

import pytest

from huggingface_agents_langgraph import graph as runtime_graph
from huggingface_agents_langgraph import llm
from huggingface_agents_langgraph.graph_definition.registry import (
    AUTHORIZED_CALLABLES,
)


@pytest.fixture(autouse=True)
def prevent_live_model_calls(monkeypatch):
    """Normal tests must supply mocks instead of calling a running model."""

    def unexpected(*_args, **_kwargs):
        raise AssertionError("Live model calls are not allowed in unit tests")

    monkeypatch.setattr(llm, "urlopen", unexpected)


def _evidence(source_type):
    return [{"content": "c", "source": "s", "source_type": source_type}]


def _stub(name, behavior):
    def run(state):
        return behavior(state)

    run.__name__ = name
    return run


def _route(state):
    if state["file_name"].endswith(".py"):
        return {"route": "code"}
    if "web" in state["question"]:
        return {"route": "web"}
    return {"route": "direct"}


def _review(state):
    steps = state.get("research_steps", 0)
    action = "finish" if steps >= 2 else "search"
    return {"research_action": {"action": action}}


def _research_action(state):
    steps = state.get("research_steps", 0) + 1
    return {
        "research_steps": steps,
        "action_history": [*state.get("action_history", []), f"search-{steps}"],
        "evidence": [*state.get("evidence", []), *_evidence("web")],
        "research_notes": state.get("research_notes", []),
    }


def _web(state):
    if "FAIL" in state["question"]:
        raise ValueError("search unavailable")
    return {"evidence": _evidence("web")}


STUBS = {
    "preprocessing": lambda state: {"question": state["question"].strip()},
    "attachment_resolver": lambda state: {"file_path": Path(state["file_name"])},
    "router": _route,
    "code_processing": lambda state: {"evidence": _evidence("code")},
    "spreadsheet_processing": lambda state: {"evidence": _evidence("spreadsheet")},
    "document_processing": lambda state: {"evidence": _evidence("document")},
    "multimedia_processing": lambda state: {"evidence": _evidence("multimedia")},
    "web_research": _web,
    "review": _review,
    "research_action": _research_action,
    "reasoning": lambda state: {"draft_answer": "draft"},
    "answer_production": lambda state: {
        "submitted_answer": "answer",
        "answer_warnings": [],
    },
}


@pytest.fixture
def stubbed_nodes(monkeypatch):
    """Replace every node in its source module and in ``graph.py``."""
    modules = dict(AUTHORIZED_CALLABLES)
    assert set(STUBS) == {name for _, name in AUTHORIZED_CALLABLES}
    for module_name, name in AUTHORIZED_CALLABLES:
        stub = _stub(name, STUBS[name])
        monkeypatch.setattr(importlib.import_module(module_name), name, stub)
        monkeypatch.setattr(runtime_graph, name, stub)
    return modules
