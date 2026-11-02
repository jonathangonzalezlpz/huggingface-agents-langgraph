import json
from io import BytesIO

from huggingface_agents_langgraph.adapters import llm


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


# --- characterization of the request that chat_completion builds -------------

import pytest  # noqa: E402

from huggingface_agents_langgraph import tracing  # noqa: E402

MESSAGES = [{"role": "user", "content": "Q"}]


def _serve(monkeypatch, content="ok", *, finish_reason=None, body=None):
    sent = []

    def fake(request, timeout):
        sent.append((request, timeout))
        choice = {"message": {"content": content}}
        if finish_reason:
            choice["finish_reason"] = finish_reason
        payload = body if body is not None else {"choices": [choice]}
        return FakeResponse(json.dumps(payload).encode())

    monkeypatch.setattr(llm, "urlopen", fake)
    return sent


def _within_trace(experiment=None):
    trace = tracing.RunTrace(experiment=experiment or {})
    token = tracing.current_trace.set(trace)
    return trace, token


def test_the_basic_request_has_messages_and_zero_temperature(monkeypatch):
    sent = _serve(monkeypatch)
    llm.chat_completion(MESSAGES)
    body = json.loads(sent[0][0].data)
    assert body == {"messages": MESSAGES, "temperature": 0}
    assert sent[0][0].full_url == f"{llm.LLM_BASE_URL.rstrip('/')}/chat/completions"


def test_penalties_are_sent_only_when_given(monkeypatch):
    sent = _serve(monkeypatch)
    llm.chat_completion(MESSAGES, frequency_penalty=0.5, repeat_penalty=1.1)
    body = json.loads(sent[0][0].data)
    assert (body["frequency_penalty"], body["repeat_penalty"]) == (0.5, 1.1)


@pytest.mark.parametrize("enabled", [True, False])
def test_thinking_control_for_llama_cpp(monkeypatch, enabled):
    sent = _serve(monkeypatch)
    llm.chat_completion(MESSAGES, thinking=enabled, thinking_budget=300)
    body = json.loads(sent[0][0].data)
    assert body["chat_template_kwargs"] == {"enable_thinking": enabled}
    assert body["reasoning_format"] == "deepseek"
    assert ("reasoning_budget_tokens" in body) is enabled
    assert "reasoning_effort" not in body


@pytest.mark.parametrize(("enabled", "effort"), [(True, "medium"), (False, "none")])
def test_thinking_control_for_ollama(monkeypatch, enabled, effort):
    sent = _serve(monkeypatch)
    model = {"provider": "ollama", "model_id": "m"}
    llm.chat_completion(MESSAGES, thinking=enabled, model=model)
    body = json.loads(sent[0][0].data)
    assert body["reasoning_effort"] == effort
    assert "chat_template_kwargs" not in body


def test_version_3_1_controls_thinking_even_when_unspecified(monkeypatch):
    sent = _serve(monkeypatch)
    _trace, token = _within_trace({"pipeline_version": "3.1"})
    try:
        llm.chat_completion(MESSAGES)
    finally:
        tracing.current_trace.reset(token)
    body = json.loads(sent[0][0].data)
    assert body["chat_template_kwargs"] == {"enable_thinking": False}


@pytest.mark.parametrize(
    ("profile", "thinking", "model_id", "temperature", "top_p"),
    [
        ("controlled", True, "m", 0.6, 0.95),
        ("controlled", False, "m", 0.7, 0.8),
        ("author", True, "Qwen3.5-9B", 1.0, 0.95),
        ("author", True, "Qwen3-8B", 0.6, 0.95),
        ("author", False, "Qwen3.5-9B", 0.7, 0.8),
    ],
)
def test_sampling_profiles(
    monkeypatch, profile, thinking, model_id, temperature, top_p
):
    sent = _serve(monkeypatch)
    _trace, token = _within_trace({"sampling_profile": profile, "seed": 7})
    try:
        llm.chat_completion(
            MESSAGES,
            thinking=thinking,
            model={"provider": "configured", "model_id": model_id},
        )
    finally:
        tracing.current_trace.reset(token)
    body = json.loads(sent[0][0].data)
    assert (body["temperature"], body["top_p"]) == (temperature, top_p)
    assert (body["top_k"], body["min_p"], body["presence_penalty"]) == (20, 0, 1.5)
    assert (body["repeat_penalty"], body["seed"]) == (1.0, 7)


def test_the_legacy_profile_keeps_the_plain_request(monkeypatch):
    sent = _serve(monkeypatch)
    _trace, token = _within_trace({"seed": 7})
    try:
        llm.chat_completion(MESSAGES)
    finally:
        tracing.current_trace.reset(token)
    body = json.loads(sent[0][0].data)
    assert "top_p" not in body and "seed" not in body


def test_exclusive_mode_names_the_model_and_loads_it(monkeypatch):
    from huggingface_agents_langgraph import model_server

    sent = _serve(monkeypatch)
    monkeypatch.setattr(llm, "MODEL_SERVER_MODE", "exclusive")
    loaded = []
    monkeypatch.setattr(
        model_server, "ensure_model", lambda name: loaded.append(name) or 1.23456
    )
    trace, token = _within_trace()
    try:
        llm.chat_completion(MESSAGES)
    finally:
        tracing.current_trace.reset(token)
    assert json.loads(sent[0][0].data)["model"] == llm.LLM_DEFAULT_MODEL
    assert loaded == [llm.LLM_DEFAULT_MODEL]
    assert trace.calls[0]["model_load_seconds"] == 1.2346
    assert trace.calls[0]["request"]["model"] == llm.LLM_DEFAULT_MODEL


def test_exclusive_mode_refuses_models_outside_the_router(monkeypatch):
    monkeypatch.setattr(llm, "MODEL_SERVER_MODE", "exclusive")
    with pytest.raises(ValueError, match="Exclusive mode"):
        llm.chat_completion(MESSAGES, model={"provider": "ollama", "model_id": "m"})


def test_the_trace_keeps_the_response_and_endpoint(monkeypatch):
    _serve(monkeypatch)
    trace, token = _within_trace()
    try:
        llm.chat_completion(MESSAGES)
    finally:
        tracing.current_trace.reset(token)
    assert trace.calls[0]["endpoint"] == llm.LLM_BASE_URL
    assert trace.calls[0]["response"]["choices"][0]["message"]["content"] == "ok"


def test_reasoning_before_the_end_tag_is_dropped(monkeypatch):
    _serve(monkeypatch, "thoughts</think>  answer ")
    assert llm.chat_completion(MESSAGES) == "answer"


def test_a_network_failure_becomes_a_runtime_error(monkeypatch):
    from urllib.error import URLError

    def fail(*_args, **_kwargs):
        raise URLError("down")

    monkeypatch.setattr(llm, "urlopen", fail)
    with pytest.raises(RuntimeError, match="Could not get a response"):
        llm.chat_completion(MESSAGES)


@pytest.mark.parametrize("body", [{}, {"choices": []}, {"choices": [{}]}])
def test_a_malformed_response_is_refused(monkeypatch, body):
    _serve(monkeypatch, body=body)
    with pytest.raises(ValueError, match="invalid chat-completions"):
        llm.chat_completion(MESSAGES)


def test_a_truncated_response_keeps_its_partial_text(monkeypatch):
    _serve(monkeypatch, "partial", finish_reason="length")
    with pytest.raises(llm.CompletionTruncatedError) as error:
        llm.chat_completion(MESSAGES)
    assert error.value.partial_content == "partial"


@pytest.mark.parametrize("content", ["", "   ", None])
def test_an_empty_response_is_refused(monkeypatch, content):
    _serve(monkeypatch, content)
    with pytest.raises(ValueError, match="empty response"):
        llm.chat_completion(MESSAGES)
