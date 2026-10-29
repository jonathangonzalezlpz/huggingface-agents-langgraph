import pytest

from huggingface_agents_langgraph import routing
from huggingface_agents_langgraph.experiments import normalize_experiment


@pytest.mark.parametrize("route", ["direct", "web", "wikipedia"])
def test_router_classifies_questions_without_attachments(
    monkeypatch: pytest.MonkeyPatch,
    route: str,
) -> None:
    captured = []

    def chat_completion_mock(messages, **kwargs):
        captured.append((messages, kwargs))
        return route

    monkeypatch.setattr(routing, "chat_completion", chat_completion_mock)
    state = {"task_id": "task-1", "question": "Question?", "file_name": ""}

    assert routing.router(state) == {"route": route}
    assert captured[0][1] == {"max_tokens": 32, "model": None}
    assert captured[0][0][0]["content"].endswith("/no_think")


def test_router_uses_attachment_extension_without_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_call(_messages, **_kwargs):
        raise AssertionError("file routes should not call the LLM classifier")

    monkeypatch.setattr(routing, "chat_completion", unexpected_call)
    state = {"task_id": "task-1", "question": "Question?", "file_name": "book.PDF"}

    assert routing.router(state) == {"route": "document"}


@pytest.mark.parametrize(
    "file_name",
    ["voice.mp3", "chart.PNG", "clip.mp4", "recording.wav"],
)
def test_router_sends_multimedia_attachments_to_multimedia(
    monkeypatch: pytest.MonkeyPatch,
    file_name: str,
) -> None:
    monkeypatch.setattr(
        routing,
        "chat_completion",
        lambda _messages, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected LLM call")
        ),
    )
    state = {"task_id": "task-1", "question": "Question?", "file_name": file_name}

    assert routing.router(state) == {"route": "multimedia"}


def test_router_sends_youtube_questions_to_multimedia() -> None:
    state = {
        "task_id": "task-1",
        "question": "Count the birds in https://www.youtube.com/watch?v=abc123",
        "file_name": "",
    }

    assert routing.router(state) == {"route": "multimedia"}


def test_router_rejects_invalid_llm_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        routing, "chat_completion", lambda _messages, **_kwargs: "other"
    )
    state = {"task_id": "task-1", "question": "Question?", "file_name": ""}

    with pytest.raises(ValueError, match="unsupported question route"):
        routing.router(state)


def test_router_passes_selected_model_to_question_classifier(monkeypatch) -> None:
    selected_model = {"provider": "ollama", "model_id": "qwen2-local:latest"}
    captured_models = []

    def classify(_question, model=None):
        captured_models.append(model)
        return "direct"

    monkeypatch.setattr(routing, "_classify_question", classify)
    state = {
        "task_id": "task-1",
        "question": "What is 2 + 2?",
        "file_name": "",
        "experiment": normalize_experiment({"model": selected_model}),
    }

    assert routing.router(state) == {"route": "direct"}
    assert captured_models == [selected_model]
