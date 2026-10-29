from huggingface_agents_langgraph import reasoning
from huggingface_agents_langgraph.config import (
    LLM_REASONING_MAX_TOKENS,
    LLM_REASONING_TEMPERATURE,
)


def test_reasoning_passes_selected_model_to_answer_call(monkeypatch) -> None:
    selected_model = {"provider": "ollama", "model_id": "qwen2-local:latest"}
    captured_kwargs = []

    def chat_completion_mock(_messages, **kwargs):
        captured_kwargs.append(kwargs)
        return "4"

    monkeypatch.setattr(reasoning, "chat_completion", chat_completion_mock)
    state = {
        "task_id": "task-1",
        "question": "What is 2 + 2?",
        "file_name": "",
        "route": "direct",
        "experiment": {"model": selected_model},
    }

    assert reasoning.reasoning(state) == {"draft_answer": "4"}
    assert captured_kwargs[0]["model"] == selected_model


def test_reasoning_accepts_direct_question_without_evidence(monkeypatch) -> None:
    captured_messages = []

    def chat_completion_mock(messages, **kwargs):
        captured_messages.extend(messages)
        assert kwargs == {
            "max_tokens": LLM_REASONING_MAX_TOKENS,
            "temperature": LLM_REASONING_TEMPERATURE,
            "model": None,
        }
        return "right"

    monkeypatch.setattr(reasoning, "chat_completion", chat_completion_mock)
    state = {
        "task_id": "task-1",
        "question": "Write the opposite of left.",
        "file_name": "",
        "route": "direct",
    }

    update = reasoning.reasoning(state)

    assert update == {"draft_answer": "right"}
    assert state["question"] in captured_messages[1]["content"]
    assert "/no_think" not in captured_messages[1]["content"]
    assert "stable general knowledge" in captured_messages[0]["content"]
