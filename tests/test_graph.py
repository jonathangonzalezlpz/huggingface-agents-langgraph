import pytest

from huggingface_agents_langgraph import graph as graph_module
from huggingface_agents_langgraph.graph import _route_after_router, build_state_graph


@pytest.mark.parametrize(
    ("route", "expected"),
    [
        ("direct", "direct"),
        ("web", "web"),
        ("wikipedia", "web"),
        ("multimedia", "multimedia"),
        ("unimplemented", "finish"),
    ],
)
def test_graph_dispatches_no_attachment_routes(route: str, expected: str) -> None:
    state = {
        "task_id": "task-1",
        "question": "Question?",
        "file_name": "",
        "route": route,
    }

    assert _route_after_router(state) == expected


def test_direct_route_reaches_reasoning_without_external_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reasoning_states = []

    def reasoning_mock(state):
        reasoning_states.append(state)
        return {"submitted_answer": "right"}

    monkeypatch.setattr(graph_module, "router", lambda _state: {"route": "direct"})
    monkeypatch.setattr(graph_module, "reasoning", reasoning_mock)
    graph = build_state_graph()
    input_state = {
        "task_id": "task-1",
        "question": "Write the opposite of left.",
        "file_name": "",
    }

    result = graph.invoke(input_state)

    assert result["submitted_answer"] == "right"
    assert "evidence" not in reasoning_states[0]
