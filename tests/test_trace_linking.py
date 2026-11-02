"""Model calls of older records are assigned to their node by duration and order."""

from huggingface_agents_langgraph.domain.trace_linking import infer_links
from huggingface_agents_langgraph.domain.trace_spans import build_trace


def _steps(*items):
    cursor, steps = 0.0, []
    for name, duration in items:
        steps.append({"node": name, "duration_seconds": duration, "start": cursor})
        cursor += duration
    return steps


def _calls(*durations):
    return [{"duration_seconds": duration} for duration in durations]


def _nodes(steps, calls):
    return [
        (steps[link[0]]["node"] if link else None) for link in infer_links(steps, calls)
    ]


def test_a_call_as_long_as_a_step_belongs_to_it():
    steps = _steps(("router", 0.24), ("review", 6.9673), ("reasoning", 30.4459))

    assert _nodes(steps, _calls(0.24, 6.9671, 30.4457)) == [
        "router",
        "review",
        "reasoning",
    ]


def test_a_shorter_call_inside_a_longer_step_is_placed_between_its_neighbours():
    steps = _steps(
        ("router", 0.24),
        ("web_research", 5.2847),
        ("review", 6.9673),
        ("reasoning", 30.4),
    )

    nodes = _nodes(steps, _calls(0.24, 0.5739, 6.9671, 30.3998))

    assert nodes == ["router", "web_research", "review", "reasoning"]


def test_a_slow_step_without_model_calls_is_not_given_the_next_call():
    steps = _steps(("research_action", 8.5), ("review", 2.6))

    assert _nodes(steps, _calls(2.6)) == ["review"]


def test_several_calls_in_one_step_follow_one_another_inside_it():
    steps = _steps(("web_research", 10.0), ("review", 2.0))
    links = infer_links(steps, _calls(3.0, 4.0, 2.0))

    assert [link[0] for link in links] == [0, 0, 1]
    assert links[0][1] == 0.0 and links[1][1] == 3.0


def test_a_call_that_fits_nowhere_is_left_unlinked():
    steps = _steps(("router", 0.2))

    assert infer_links(steps, _calls(50.0)) == [None]


def test_build_trace_places_inferred_calls_under_their_node_at_the_right_time():
    record = {
        "id": "r",
        "status": "completed",
        "duration_seconds": 8,
        "steps": [
            {"node": "router", "duration_seconds": 0.24, "update": {}},
            {"node": "web_research", "duration_seconds": 5.0, "update": {}},
            {"node": "review", "duration_seconds": 2.0, "update": {}},
        ],
        "calls": [
            {"duration_seconds": 0.24, "messages": []},
            {"duration_seconds": 0.5, "messages": []},
            {"duration_seconds": 2.0, "messages": []},
        ],
    }

    spans = build_trace(record)["spans"]
    nodes = {s["name"]: s for s in spans if s["kind"] == "node"}
    calls = [s for s in spans if s["kind"] == "llm"]

    assert [c["parent_id"] for c in calls] == [
        nodes["router"]["span_id"],
        nodes["web_research"]["span_id"],
        nodes["review"]["span_id"],
    ]
    assert all(c["attributes"]["linked_to_node"] is True for c in calls)
    assert all(c["attributes"]["inferred_link"] is True for c in calls)
    assert (
        calls[1]["start_offset_seconds"]
        == nodes["web_research"]["start_offset_seconds"]
    )


def test_calls_with_a_node_name_go_to_the_repetition_that_contains_them():
    record = {
        "id": "r",
        "status": "completed",
        "duration_seconds": 10,
        "steps": [
            {
                "node": "review",
                "duration_seconds": 2.0,
                "started_offset_seconds": 0.0,
                "update": {},
            },
            {
                "node": "review",
                "duration_seconds": 3.0,
                "started_offset_seconds": 5.0,
                "update": {},
            },
        ],
        "calls": [
            {"node": "review", "started_offset_seconds": 5.1, "duration_seconds": 2.9},
        ],
    }

    spans = build_trace(record)["spans"]
    reviews = [s for s in spans if s["kind"] == "node"]
    call = next(s for s in spans if s["kind"] == "llm")

    assert call["parent_id"] == reviews[1]["span_id"]
    assert "inferred_link" not in call["attributes"]
