"""Small client for the local OpenAI-compatible chat-completions endpoint."""

import json
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from huggingface_agents_langgraph.config import (
    LLM_BASE_URL,
    LLM_TIMEOUT_SECONDS,
    OLLAMA_BASE_URL,
)
from huggingface_agents_langgraph.experiments import ModelSelection


class ChatMessage(TypedDict):
    """Message passed to the configured chat model."""

    role: str
    content: str


def chat_completion(
    messages: list[ChatMessage],
    *,
    max_tokens: int | None = None,
    frequency_penalty: float | None = None,
    model: ModelSelection | None = None,
) -> str:
    """Return the model's response text for a chat-completions request."""
    request_body = {"messages": messages, "temperature": 0}
    if max_tokens is not None:
        request_body["max_tokens"] = max_tokens
    if frequency_penalty is not None:
        request_body["frequency_penalty"] = frequency_penalty
    base_url = LLM_BASE_URL
    if model is not None:
        base_url = OLLAMA_BASE_URL if model["provider"] == "ollama" else LLM_BASE_URL
        request_body["model"] = model["model_id"]
    request = Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=LLM_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Could not get a response from the configured LLM: {error}"
        ) from error

    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("LLM returned an invalid chat-completions response") from error

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
