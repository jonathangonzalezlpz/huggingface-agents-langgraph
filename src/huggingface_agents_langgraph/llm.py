"""Small client for the local OpenAI-compatible chat-completions endpoint."""

import json
from copy import deepcopy
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from huggingface_agents_langgraph.config import (
    LLM_BASE_URL,
    LLM_TIMEOUT_SECONDS,
    OLLAMA_BASE_URL,
)
from huggingface_agents_langgraph.experiments import ModelSelection, improvement_enabled
from huggingface_agents_langgraph.run_tracking import (
    current_trace,
    remaining_seconds,
    traced_completion,
)


class ChatMessage(TypedDict):
    """Message passed to the configured chat model."""

    role: str
    content: str


class CompletionTruncatedError(ValueError):
    """The server exhausted its token allowance before completing a response."""

    def __init__(self, message: str, partial_content: str = "") -> None:
        super().__init__(message)
        self.partial_content = partial_content


@traced_completion
def chat_completion(
    messages: list[ChatMessage],
    *,
    max_tokens: int | None = None,
    frequency_penalty: float | None = None,
    repeat_penalty: float | None = None,
    model: ModelSelection | None = None,
    temperature: float = 0,
    thinking: bool | None = None,
    thinking_budget: int | None = None,
) -> str:
    """Return the model's response text for a chat-completions request."""
    request_body = {"messages": messages, "temperature": temperature}
    if max_tokens is not None:
        request_body["max_tokens"] = max_tokens
    if frequency_penalty is not None:
        request_body["frequency_penalty"] = frequency_penalty
    if repeat_penalty is not None:
        request_body["repeat_penalty"] = repeat_penalty
    base_url = LLM_BASE_URL
    if model is not None:
        base_url = OLLAMA_BASE_URL if model["provider"] == "ollama" else LLM_BASE_URL
        request_body["model"] = model["model_id"]
    if improvement_enabled(None, "reasoning_control") or thinking is not None:
        enabled = bool(thinking)
        if model and model["provider"] == "ollama":
            request_body["reasoning_effort"] = "medium" if enabled else "none"
        else:
            request_body["chat_template_kwargs"] = {"enable_thinking": enabled}
            request_body["reasoning_format"] = "deepseek"
            if enabled and thinking_budget is not None:
                request_body["reasoning_budget_tokens"] = thinking_budget
    trace = current_trace.get()
    if trace is not None:
        trace.calls[-1]["request"] = deepcopy(request_body)
    request = Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(
            request, timeout=min(LLM_TIMEOUT_SECONDS, remaining_seconds())
        ) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Could not get a response from the configured LLM: {error}"
        ) from error

    trace = current_trace.get()
    if trace is not None:
        trace.calls[-1].update(response=result, endpoint=base_url)
    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("LLM returned an invalid chat-completions response") from error

    if result["choices"][0].get("finish_reason") == "length":
        raise CompletionTruncatedError(
            "LLM output was truncated by the token limit",
            content if isinstance(content, str) else "",
        )
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM returned an empty response")
    return content.rsplit("</think>", 1)[-1].strip()


def get_available_models() -> list[dict[str, str]]:
    """List models exposed by the configured endpoint and local Ollama."""
    models: list[dict[str, str]] = []
    endpoints = [("configured", LLM_BASE_URL), ("ollama", OLLAMA_BASE_URL)]
    seen_endpoints: set[str] = set()

    for provider, base_url in endpoints:
        endpoint_url = base_url.rstrip("/")
        endpoint_key = endpoint_url.casefold()
        if endpoint_key in seen_endpoints:
            continue
        seen_endpoints.add(endpoint_key)
        request = Request(f"{endpoint_url}/models")
        try:
            with urlopen(request, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            continue

        if not isinstance(payload, dict):
            continue
        data = payload.get("data", [])
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id.strip():
                models.append(
                    {
                        "provider": provider,
                        "model_id": model_id.strip(),
                    }
                )
    return models
