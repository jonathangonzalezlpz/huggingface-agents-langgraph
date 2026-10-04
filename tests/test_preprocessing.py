"""Tests for the preprocessing function."""

import pytest

from huggingface_agents_langgraph.preprocessing import preprocessing


def test_preprocessing_trims_question() -> None:
    """Trim surrounding whitespace from the question."""
    state = {
        "task_id": "f918266a-b3e0-4914-865d-4faa564f1aef",
        "question": (
            "    What is the final numeric output from the attached Python code?    "
        ),
        "file_name": "f918266a-b3e0-4914-865d-4faa564f1aef.py",
    }

    update = preprocessing(state)

    assert update == {
        "question": "What is the final numeric output from the attached Python code?"
    }


def test_preprocessing_empthy_question() -> None:
    """Reject a question that contains only whitespace."""

    state = {
        "task_id": "f918266a-b3e0-4914-865d-4faa564f1aef",
        "question": "    ",
        "file_name": "f918266a-b3e0-4914-865d-4faa564f1aef.py",
    }

    with pytest.raises(ValueError, match="question must not be empty"):
        preprocessing(state)
