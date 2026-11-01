"""Choosing between the runtime graph and a compiled stored architecture."""

from dataclasses import replace

import pytest

from huggingface_agents_langgraph import graph as runtime_graph
from huggingface_agents_langgraph import run_tracking
from huggingface_agents_langgraph.architecture_store import (
    BUILTIN_V31_ID,
    content_sha256,
    save_architecture,
)
from huggingface_agents_langgraph.graph_definition import GraphCompilationError
from huggingface_agents_langgraph.graph_definition.definitions import (
    create_gaia_v31_definition,
)
from huggingface_agents_langgraph.graph_selection import select_graph


@pytest.fixture(autouse=True)
def runtime_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))


def _nodes(graph):
    return set(graph.get_graph().nodes)


def test_without_architecture_the_runtime_graph_is_used():
    graph, info = select_graph({})
    assert info == {"engine": "graph.py"}
    assert _nodes(graph) == _nodes(runtime_graph.build_state_graph())


def test_builtin_architecture_is_compiled():
    graph, info = select_graph({"architecture": BUILTIN_V31_ID})
    assert info == {
        "engine": "compiled",
        "id": BUILTIN_V31_ID,
        "architecture_id": "gaia_v31",
        "version": None,
        "content_sha256": content_sha256(create_gaia_v31_definition()),
    }
    assert _nodes(graph) == _nodes(runtime_graph.build_state_graph())


def test_saved_version_is_compiled_and_identified():
    definition = replace(create_gaia_v31_definition(), architecture_id="custom")
    saved = save_architecture(definition)
    _graph, info = select_graph({"architecture": saved["id"]})
    assert info["engine"] == "compiled"
    assert (info["id"], info["version"]) == (saved["id"], 1)
    assert info["content_sha256"] == saved["content_sha256"]


@pytest.mark.parametrize("identifier", ["00000000-0000-0000-0000-000000000000", "nope"])
def test_unknown_architecture_is_a_value_error(identifier):
    with pytest.raises(ValueError, match="Unknown architecture"):
        select_graph({"architecture": identifier})


def test_invalid_stored_draft_cannot_be_executed():
    draft = replace(create_gaia_v31_definition(), architecture_id="draft", edges=())
    saved = save_architecture(draft)
    with pytest.raises(GraphCompilationError):
        select_graph({"architecture": saved["id"]})
