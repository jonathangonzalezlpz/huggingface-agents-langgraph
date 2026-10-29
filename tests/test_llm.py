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
