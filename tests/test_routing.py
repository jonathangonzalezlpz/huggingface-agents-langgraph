import pytest

from huggingface_agents_langgraph import routing


@pytest.mark.parametrize("route", ["direct", "web", "wikipedia"])
def test_router_classifies_questions_without_attachments(
    monkeypatch: pytest.MonkeyPatch,
    route: str,
) -> None:
    monkeypatch.setattr(routing, "chat_completion", lambda _messages: route)
    state = {"task_id": "task-1", "question": "Question?", "file_name": ""}

    assert routing.router(state) == {"route": route}


def test_router_uses_attachment_extension_without_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_call(_messages):
        raise AssertionError("file routes should not call the LLM classifier")

    monkeypatch.setattr(routing, "chat_completion", unexpected_call)
    state = {"task_id": "task-1", "question": "Question?", "file_name": "book.PDF"}

    assert routing.router(state) == {"route": "document"}


def test_router_rejects_invalid_llm_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routing, "chat_completion", lambda _messages: "other")
    state = {"task_id": "task-1", "question": "Question?", "file_name": ""}

    with pytest.raises(ValueError, match="unsupported question route"):
        routing.router(state)
