import json
from io import BytesIO

from huggingface_agents_langgraph import web_app


class FakeResponse:
    def __init__(self, payload: dict[str, object], status: int = 200) -> None:
        self.status = status
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_exc_info) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_llm_status_reports_sleep_without_waking_model(monkeypatch) -> None:
    requested_urls = []

    def fake_urlopen(url: str, timeout: int):
        requested_urls.append(url)
        assert timeout == 2
        if url.endswith("/health"):
            return FakeResponse({"status": "ok"})
        return FakeResponse({"is_sleeping": True})

    monkeypatch.setattr(web_app, "urlopen", fake_urlopen)

    assert web_app._get_llm_status() == {
        "state": "sleeping",
        "name": "LLM razonador",
    }
    assert requested_urls == [
        "http://127.0.0.1:8080/health",
        "http://127.0.0.1:8080/props",
    ]


def test_llm_status_reports_loading_when_health_returns_503(monkeypatch) -> None:
    def fake_urlopen(_url: str, timeout: int):
        raise web_app.HTTPError(
            "http://127.0.0.1:8080/health", 503, "Loading", {}, BytesIO()
        )

    monkeypatch.setattr(web_app, "urlopen", fake_urlopen)

    assert web_app._get_llm_status()["state"] == "loading"
