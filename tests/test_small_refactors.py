"""Edge cases of functions that were split into helpers without changing behavior."""

import ast

import pytest

from huggingface_agents_langgraph.pipeline import (
    answer_production,
    calculation,
    multimedia_processing,
)


@pytest.mark.parametrize(
    ("question", "answer", "expected"),
    [
        ("Name the items as a comma separated list", "a,,b", 1),
        ("Give a comma separated list alphabetically", "b, a", 1),
        ("Give a comma separated list in ascending order", "2, 1", 1),
        ("Give a comma separated list in ascending order", "x, 1", 1),
        ("Give a comma separated list in ascending order", "1, 2", 0),
        ("What is it?", "", 1),
    ],
)
def test_answer_shape_issues(question, answer, expected):
    assert len(answer_production.validate_answer(question, answer)) == expected


@pytest.mark.parametrize(
    "expression",
    ["_x", "[x async for x in y]", "len(a=1)", "abs.__doc__", "'a'.upper()"],
)
def test_calculation_syntax_still_refused_by_default(expression):
    with pytest.raises(ValueError):
        calculation.validate_expression(expression)


def test_enhanced_calculation_allows_string_method_calls_only():
    calculation.validate_expression("'a'.upper()", enhanced=True)
    with pytest.raises(ValueError, match="whitelisted"):
        calculation.validate_expression("'a'.format", enhanced=True)
    with pytest.raises(ValueError, match="allowed pure function"):
        calculation.validate_expression("'a'.mro()", enhanced=True)
    assert ast.parse("1")


@pytest.mark.parametrize(
    "reply",
    [
        "not json",
        "[]",
        '{"audio": true}',
        '{"audio": false, "vision": false}',
        '{"audio": 1, "vision": true}',
    ],
)
def test_unusable_modality_replies_select_both(monkeypatch, reply):
    from huggingface_agents_langgraph.adapters import llm

    monkeypatch.setattr(llm, "chat_completion", lambda *_a, **_k: reply)
    assert multimedia_processing._choose_modalities("q", None) == {
        "audio": True,
        "vision": True,
    }


def test_a_valid_modality_reply_is_kept(monkeypatch):
    from huggingface_agents_langgraph.adapters import llm

    monkeypatch.setattr(
        llm, "chat_completion", lambda *_a, **_k: '{"audio": false, "vision": true}'
    )
    assert multimedia_processing._choose_modalities("q", None) == {
        "audio": False,
        "vision": True,
    }


def test_attachments_need_a_supported_extension(tmp_path):
    path = tmp_path / "file.xyz"
    path.write_bytes(b"x")
    with pytest.raises(ValueError, match="Unsupported multimedia attachment"):
        multimedia_processing.multimedia_processing(
            {"question": "q", "file_path": path}
        )


def test_without_file_or_url_the_question_must_name_a_video():
    with pytest.raises(ValueError, match="YouTube URL"):
        multimedia_processing.multimedia_processing({"question": "no link here"})
