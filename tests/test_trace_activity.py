"""What each node did in one line, and figures the evidence does not back."""

from huggingface_agents_langgraph.domain.trace_activity import (
    node_activity,
    unsupported_figures,
)
from huggingface_agents_langgraph.domain.trace_spans import build_trace


def test_a_review_decision_names_the_action_its_target_and_reason():
    update = {
        "research_action": {
            "action": "fetch",
            "url": "https://example.org/page",
            "reason": "need the page",
        },
        "research_notes": [],
    }

    assert node_activity(update) == "fetch https://example.org/page — need the page"


def test_search_calculate_and_finish_decisions_use_their_own_target():
    search = {
        "research_action": {"action": "search", "query": "roy white", "reason": "r"}
    }
    calculate = {"research_action": {"action": "calculate", "expression": "2+2"}}
    finish = {"research_action": {"action": "finish", "reason": "enough"}}

    assert node_activity(search) == "search roy white — r"
    assert node_activity(calculate) == "calculate 2+2"
    assert node_activity(finish) == "finish — enough"


def test_a_long_reason_is_clipped():
    update = {"research_action": {"action": "finish", "reason": "x" * 1000}}

    assert len(node_activity(update) or "") < 220


def test_acquisition_reports_the_last_note_and_the_evidence_count():
    update = {
        "research_notes": ["older", "fetch failed: HTTP Error 403: Forbidden"],
        "evidence": [{"content": "a"}, {"content": "b"}, {"content": "c"}],
        "research_steps": 1,
    }

    assert (
        node_activity(update) == "fetch failed: HTTP Error 403: Forbidden · evidence: 3"
    )


def test_route_draft_and_answer_are_summarised():
    assert node_activity({"route": "direct"}) == "route: direct"
    assert node_activity({"draft_answer": "x" * 500}) == "draft: 500 chars"
    assert node_activity({"submitted_answer": "Paris", "answer_warnings": []}) == (
        "answer: Paris"
    )
    assert node_activity(
        {"submitted_answer": "Paris", "answer_warnings": ["a", "b"]}
    ) == ("answer: Paris · warnings: 2")


def test_an_update_with_nothing_to_say_has_no_activity():
    assert node_activity({}) is None
    assert node_activity({"question": "q"}) is None
    assert node_activity(None) is None


def test_figures_without_support_are_those_in_neither_evidence_nor_question():
    figures = unsupported_figures(
        "He had 568 at-bats, 75 walks and played in 1977.",
        question="How many at bats in the 1977 season?",
        evidence=["Roy White had 75 walks"],
    )

    assert figures == ["568"]


def test_figures_ignore_separators_single_digits_and_repeats():
    figures = unsupported_figures(
        "6,650 and 6650 and 7 and 7,001 and 7001",
        question="",
        evidence=["career: 6,650 at bats"],
    )

    assert figures == ["7001"]


def test_build_trace_flags_a_review_that_cites_a_figure_missing_from_the_evidence():
    record = {
        "id": "r",
        "status": "completed",
        "duration_seconds": 3,
        "task": {"question": "How many at bats in 1977?"},
        "result": {"evidence": [{"content": "75 walks"}]},
        "steps": [
            {
                "node": "review",
                "update": {
                    "research_action": {
                        "action": "finish",
                        "reason": "he had 568 at bats",
                    }
                },
                "duration_seconds": 1.0,
                "started_offset_seconds": 0.0,
            }
        ],
        "calls": [],
    }

    node = next(s for s in build_trace(record)["spans"] if s["kind"] == "node")

    assert node["attributes"]["unsupported_figures"] == ["568"]
    assert node["attributes"]["activity"].startswith("finish")
    assert build_trace(record)["summary"]["unsupported_figures"] == ["568"]


def test_only_notes_added_by_this_step_are_reported():
    update = {"research_notes": ["old failure", "new failure"], "evidence": [{}]}

    assert node_activity(update, known_notes=1) == "new failure · evidence: 1"
    assert node_activity(update, known_notes=2) == "evidence: 1"


def test_a_figure_quoted_from_an_acquisition_note_is_supported():
    record = {
        "id": "r",
        "status": "completed",
        "duration_seconds": 3,
        "task": {"question": "q"},
        "result": {"evidence": []},
        "steps": [
            {
                "node": "research_action",
                "update": {"research_notes": ["fetch failed: HTTP Error 403"]},
                "duration_seconds": 1.0,
                "started_offset_seconds": 0.0,
            },
            {
                "node": "review",
                "update": {
                    "research_action": {"action": "search", "reason": "the 403 error"}
                },
                "duration_seconds": 1.0,
                "started_offset_seconds": 1.0,
            },
        ],
        "calls": [],
    }

    assert build_trace(record)["summary"]["unsupported_figures"] == []
