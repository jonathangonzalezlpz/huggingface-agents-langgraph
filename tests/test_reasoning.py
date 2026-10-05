from huggingface_agents_langgraph import reasoning


def test_reasoning_accepts_direct_question_without_evidence(monkeypatch) -> None:
    captured_messages = []

    def chat_completion_mock(messages):
        captured_messages.extend(messages)
        return "right"

    monkeypatch.setattr(reasoning, "chat_completion", chat_completion_mock)
    state = {
        "task_id": "task-1",
        "question": "Write the opposite of left.",
        "file_name": "",
        "route": "direct",
    }

    update = reasoning.reasoning(state)

    assert update == {"answer_candidate": "right"}
    assert captured_messages[1]["content"] == state["question"]
    assert "Do not search" in captured_messages[0]["content"]
