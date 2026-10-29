import pytest

from huggingface_agents_langgraph import llm


@pytest.fixture(autouse=True)
def prevent_live_model_calls(monkeypatch):
    """Normal tests must supply mocks instead of calling a running model."""

    def unexpected(*_args, **_kwargs):
        raise AssertionError("Live model calls are not allowed in unit tests")

    monkeypatch.setattr(llm, "urlopen", unexpected)
