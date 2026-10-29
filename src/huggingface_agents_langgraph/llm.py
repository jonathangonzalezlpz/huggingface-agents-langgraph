"""Small client for the local OpenAI-compatible chat-completions endpoint."""

import json
from typing import TypedDict
from urllib.error import URLError
from urllib.request import Request, urlopen

from huggingface_agents_langgraph.config import LLM_BASE_URL, LLM_TIMEOUT_SECONDS


class ChatMessage(TypedDict):
    """Message passed to the configured chat model."""

    role: str
    content: str


def chat_completion(
    messages: list[ChatMessage],
    *,
    max_tokens: int | None = None,
    frequency_penalty: float | None = None,
) -> str:
    """Return the model's response text for a chat-completions request."""
    request_body = {"messages": messages, "temperature": 0}
    if max_tokens is not None:
        request_body["max_tokens"] = max_tokens
    if frequency_penalty is not None:
        request_body["frequency_penalty"] = frequency_penalty
    request = Request(
        f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
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
