import json
from io import BytesIO

from huggingface_agents_langgraph import llm


class FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        self.close()


def test_chat_completion_uses_optional_token_limit(monkeypatch) -> None:
    requests = []

    def urlopen_mock(request, timeout: int):
        requests.append((request, timeout))
        return FakeResponse(
            json.dumps({"choices": [{"message": {"content": "direct"}}]}).encode()
        )

    monkeypatch.setattr(llm, "urlopen", urlopen_mock)

    answer = llm.chat_completion(
        [{"role": "user", "content": "Classify this task."}], max_tokens=32
    )

    request, timeout = requests[0]
    payload = json.loads(request.data)
    assert answer == "direct"
    assert payload["max_tokens"] == 32
    assert timeout == llm.LLM_TIMEOUT_SECONDS


def test_chat_completion_omits_token_limit_by_default(monkeypatch) -> None:
    requests = []

    def urlopen_mock(request, *, timeout: int):
        requests.append(request)
        return FakeResponse(
            json.dumps({"choices": [{"message": {"content": "answer"}}]}).encode()
        )

    monkeypatch.setattr(llm, "urlopen", urlopen_mock)
    llm.chat_completion([{"role": "user", "content": "Answer."}])

    assert "max_tokens" not in json.loads(requests[0].data)


def test_chat_completion_uses_selected_ollama_model(monkeypatch) -> None:
    requests = []

    def urlopen_mock(request, timeout: int):
        requests.append((request, timeout))
        return FakeResponse(
            json.dumps({"choices": [{"message": {"content": "right"}}]}).encode()
        )

    monkeypatch.setattr(llm, "urlopen", urlopen_mock)
    answer = llm.chat_completion(
        [{"role": "user", "content": "Question?"}],
        model={"provider": "ollama", "model_id": "qwen2-local:latest"},
    )

    request, _timeout = requests[0]
    assert answer == "right"
    assert request.full_url == f"{llm.OLLAMA_BASE_URL}/chat/completions"
    assert json.loads(request.data)["model"] == "qwen2-local:latest"


def test_get_available_models_discovers_configured_and_ollama_models(
    monkeypatch,
) -> None:
    def urlopen_mock(request, timeout: int):
        assert timeout == 2
        if request.full_url == f"{llm.LLM_BASE_URL}/models":
            model_id = "Qwen/Qwen3-8B-GGUF:Q5_K_M"
        else:
            model_id = "qwen2-local:latest"
        payload = {"data": [{"id": model_id}]}
        return FakeResponse(json.dumps(payload).encode())

    monkeypatch.setattr(llm, "urlopen", urlopen_mock)

    assert llm.get_available_models() == [
        {
            "provider": "configured",
            "model_id": "Qwen/Qwen3-8B-GGUF:Q5_K_M",
        },
        {"provider": "ollama", "model_id": "qwen2-local:latest"},
    ]
