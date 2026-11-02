"""Characterization of ``research.review``: its prompt and the actions it accepts."""

import json

import pytest

from huggingface_agents_langgraph.domain.experiments import normalize_experiment
from huggingface_agents_langgraph.pipeline import research


def _reply(monkeypatch, *replies):
    """Make the model answer with ``replies`` in order; return the captured calls."""
    calls: list[list[dict]] = []
    queue = iter(replies)

    def fake(messages, **_kwargs):
        calls.append([dict(m) for m in messages])
        return next(queue)

    monkeypatch.setattr(research, "chat_completion", fake)
    return calls


def _state(**extra):
    return {"question": "Q?", **extra}


@pytest.mark.parametrize(
    "action",
    [
        {"action": "search", "query": "x"},
        {"action": "fetch", "url": "https://example.org"},
        {"action": "calculate", "expression": "1+1"},
        {"action": "finish", "reason": "enough"},
    ],
)
def test_a_valid_action_is_returned_unchanged(monkeypatch, action):
    _reply(monkeypatch, json.dumps(action))
    assert research.review(_state()) == {
        "research_action": action,
        "research_notes": [],
    }


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        "[]",
        '{"action":"teleport"}',
        '{"action":"search"}',
        '{"action":"search","query":"  "}',
        '{"action":"fetch","url":3}',
        '{"action":"calculate","expression":""}',
    ],
)
def test_an_invalid_action_is_retried_with_feedback(monkeypatch, bad):
    calls = _reply(monkeypatch, bad, '{"action":"finish"}')
    result = research.review(_state())
    assert result["research_action"] == {"action": "finish"}
    assert result["research_notes"] == []
    retry = calls[1]
    assert retry[-2] == {"role": "assistant", "content": bad}
    assert retry[-1]["content"].startswith("Invalid action: ")
    assert retry[-1]["content"].endswith("Return a valid JSON object.")


def test_two_invalid_actions_finish_with_a_note(monkeypatch):
    _reply(monkeypatch, "nope", "still nope")
    result = research.review(_state())
    assert result["research_action"] == {"action": "finish"}
    assert result["research_notes"] == [
        "Review produced invalid actions twice; continued with available evidence."
    ]


def _video_state():
    experiment = normalize_experiment({"enabled_capabilities": ["multimedia"]})
    return _state(experiment=experiment, video_path="clip.mp4")


@pytest.mark.parametrize(
    ("timestamps", "valid"),
    [
        ([1, 2.5], True),
        ([0], True),
        ([86400], True),
        ([], False),
        (list(range(9)), False),
        ([-1], False),
        ([86401], False),
        ([True], False),
        (["3"], False),
        ("3", False),
    ],
)
def test_video_timestamps_are_checked(monkeypatch, timestamps, valid):
    action = {"action": "video", "timestamps": timestamps}
    _reply(monkeypatch, json.dumps(action), '{"action":"finish"}')
    result = research.review(_video_state())
    assert (result["research_action"] == action) is valid


def test_video_alone_is_not_enough_to_ask_the_model(monkeypatch):
    experiment = normalize_experiment({"enabled_capabilities": ["multimedia"]})
    calls = _reply(monkeypatch)
    result = research.review(_state(experiment=experiment))
    assert result == {"research_action": {"action": "finish"}}
    assert calls == []


@pytest.mark.parametrize(
    ("extra", "valid"),
    [
        ({"source_id": "s1"}, True),
        ({"source_id": "s1", "query": "x", "start": 10}, True),
        ({}, False),
        ({"source_id": 1}, False),
        ({"source_id": "s1", "query": 5}, False),
        ({"source_id": "s1", "start": -1}, False),
        ({"source_id": "s1", "start": 1.5}, False),
        ({"source_id": "s1", "start": True}, False),
    ],
)
def test_read_source_arguments_are_checked(monkeypatch, extra, valid):
    monkeypatch.setattr(research, "source_catalog", lambda: [{"source_id": "s1"}])
    experiment = normalize_experiment(
        {"pipeline_version": "3.1", "improvements": ["web_sources"]}
    )
    action = {"action": "read_source", **extra}
    calls = _reply(monkeypatch, json.dumps(action), '{"action":"finish"}')
    result = research.review(_state(experiment=experiment))
    assert (result["research_action"] == action) is valid
    system = calls[0][0]["content"]
    assert "read_source requires source_id" in system
    assert json.loads(calls[0][1]["content"])["available_sources"] == [
        {"source_id": "s1"}
    ]


def test_the_reason_does_not_make_an_action_new(monkeypatch):
    done = json.dumps({"action": "search", "query": "x"}, sort_keys=True)
    _reply(monkeypatch, '{"action":"search","query":"x","reason":"again"}')
    result = research.review(_state(action_history=[done]))
    assert result["research_action"] == {"action": "finish"}
    assert result["research_notes"] == [
        "Review repeated a completed action; stopped acquisition."
    ]


def test_the_prompt_describes_the_question_and_progress(monkeypatch):
    calls = _reply(monkeypatch, '{"action":"finish"}')
    research.review(
        _state(
            evidence=[{"content": "c"}],
            action_history=["h"],
            research_notes=["n"],
            source_links=["https://a"],
        )
    )
    system, user = calls[0]
    assert system["role"] == "system"
    assert system["content"].endswith("/no_think")
    assert "Allowed actions: finish, search, fetch, calculate." in system["content"]
    assert "read_source requires" not in system["content"]
    assert json.loads(user["content"]) == {
        "question": "Q?",
        "evidence": [{"content": "c"}],
        "completed_actions": ["h"],
        "notes": ["n"],
        "available_links": ["https://a"],
    }


def test_calculation_hint_follows_the_improvement(monkeypatch):
    with_hint = normalize_experiment(
        {"pipeline_version": "3.1", "improvements": ["calculation_tools"]}
    )
    calls = _reply(monkeypatch, '{"action":"finish"}', '{"action":"finish"}')
    research.review(_state(experiment=with_hint))
    research.review(_state())
    assert "String operations join" in calls[0][0]["content"]
    assert "String operations join" not in calls[1][0]["content"]


def test_the_notes_of_earlier_steps_are_kept(monkeypatch):
    _reply(monkeypatch, "bad", "bad")
    result = research.review(_state(research_notes=["before"]))
    assert result["research_notes"][0] == "before"
    assert len(result["research_notes"]) == 2
