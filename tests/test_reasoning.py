from huggingface_agents_langgraph import reasoning


def test_reasoning_accepts_direct_question_without_evidence(monkeypatch) -> None:
    captured_messages = []

    def chat_completion_mock(messages, **kwargs):
        captured_messages.extend(messages)
        assert kwargs == {"max_tokens": 512, "frequency_penalty": 0.3, "model": None}
        return "right"

    monkeypatch.setattr(reasoning, "chat_completion", chat_completion_mock)
    state = {
        "task_id": "task-1",
        "question": "Write the opposite of left.",
        "file_name": "",
        "route": "direct",
    }

    update = reasoning.reasoning(state)

    assert update == {"submitted_answer": "right"}
    assert captured_messages[1]["content"] == f"{state['question']}\n/no_think"
    assert "Do not search" in captured_messages[0]["content"]
    assert "exact-match benchmark" in captured_messages[0]["content"]


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

    assert reasoning.reasoning(state) == {"submitted_answer": "4"}
    assert captured_kwargs[0]["model"] == selected_model
