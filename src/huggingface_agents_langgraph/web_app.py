"""Serve a small local interface for GAIA questions and agent runs."""

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from urllib.request import urlopen

from huggingface_agents_langgraph.attachments import get_attachment_path
from huggingface_agents_langgraph.config import LLM_BASE_URL
from huggingface_agents_langgraph.graph import build_state_graph
from huggingface_agents_langgraph.multimedia_processing import (
    get_multimedia_model_status,
)

SCORING_API_URL = "https://agents-course-unit4-scoring.hf.space"
FRONTEND_DIRECTORY = Path(__file__).parent / "frontend"
MAX_REQUEST_BYTES = 1_000_000


class WebAppHandler(BaseHTTPRequestHandler):
    """Handle frontend assets and local API requests."""

    def do_GET(self) -> None:
        """Serve the application, questions, or an attachment."""
        request_path = urlsplit(self.path).path
        if request_path == "/":
            self._serve_asset("index.html")
        elif request_path == "/assets/app.js":
            self._serve_asset("app.js")
        elif request_path == "/assets/styles.css":
            self._serve_asset("styles.css")
        elif request_path in {"/api/questions", "/api/random-question"}:
            self._get_questions(request_path)
        elif request_path == "/api/status":
            self._send_json(
                200,
                {
                    "llm": _get_llm_status(),
                    "multimedia_models": get_multimedia_model_status(),
                },
            )
        elif request_path.startswith("/api/files/"):
            self._get_attachment(unquote(request_path.removeprefix("/api/files/")))
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        """Run a GAIA task through the local LangGraph workflow."""
        if urlsplit(self.path).path != "/api/run":
            self._send_json(404, {"error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
                raise ValueError("Request body is empty or too large")
            payload = json.loads(self.rfile.read(content_length))
            task = self._validate_task(payload)
            result = build_state_graph().invoke(task)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._send_json(400, {"error": str(error)})
            return
        except Exception as error:
            self._send_json(500, {"error": str(error)})
            return

        self._send_json(200, result)

    def _get_questions(self, request_path: str) -> None:
        endpoint = (
            "/questions" if request_path == "/api/questions" else "/random-question"
        )
        try:
            with urlopen(f"{SCORING_API_URL}{endpoint}", timeout=30) as response:
                body = response.read()
        except (HTTPError, URLError, TimeoutError) as error:
            self._send_json(502, {"error": f"Could not fetch questions: {error}"})
            return

        self._send_bytes(200, body, "application/json; charset=utf-8")

    def _get_attachment(self, task_id: str) -> None:
        if not task_id or "/" in task_id or "\\" in task_id:
            self._send_json(400, {"error": "Invalid task ID"})
            return

        try:
            attachment_path = get_attachment_path(task_id)
        except Exception as error:
            self._send_json(502, {"error": f"Could not retrieve attachment: {error}"})
            return

        if attachment_path is None:
            self._send_json(404, {"error": "This question has no attachment"})
            return

        content_type = mimetypes.guess_type(attachment_path.name)[0]
        self._send_bytes(
            200,
            attachment_path.read_bytes(),
            content_type or "application/octet-stream",
            extra_headers={
                "Content-Disposition": (
                    "attachment; filename*=UTF-8''" + quote(attachment_path.name)
                )
            },
        )

    @staticmethod
    def _validate_task(payload: object) -> dict[str, str]:
        if not isinstance(payload, dict):
            raise ValueError("Task must be a JSON object")

        task_id = payload.get("task_id")
        question = payload.get("question")
        file_name = payload.get("file_name") or ""
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id is required")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question is required")
        if not isinstance(file_name, str):
            raise ValueError("file_name must be a string")

        return {
            "task_id": task_id,
            "question": question,
            "file_name": file_name,
        }

    def _serve_asset(self, file_name: str) -> None:
        asset_path = FRONTEND_DIRECTORY / file_name
        if not asset_path.is_file():
            self._send_json(404, {"error": "Frontend asset not found"})
            return

        content_type = mimetypes.guess_type(file_name)[0]
        self._send_bytes(
            200,
            asset_path.read_bytes(),
            content_type or "application/octet-stream",
        )

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    """Start the local frontend server."""
    server = ThreadingHTTPServer(("127.0.0.1", 7860), WebAppHandler)
    print("GAIA workbench available at http://127.0.0.1:7860")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _get_llm_status() -> dict[str, str]:
    """Probe llama.cpp without sending a request that could wake the model."""
    parsed_url = urlsplit(LLM_BASE_URL)
    api_path = parsed_url.path.rstrip("/")
    root_path = api_path.removesuffix("/v1")
    server_url = urlunsplit(
        (parsed_url.scheme, parsed_url.netloc, root_path, "", "")
    ).rstrip("/")

    try:
        with urlopen(f"{server_url}/health", timeout=2) as response:
            health_status = response.status
    except HTTPError as error:
        if error.code == 503:
            return {"state": "loading", "name": "LLM razonador"}
        return {"state": "unavailable", "name": "LLM razonador"}
    except (URLError, TimeoutError, OSError):
        return {"state": "unavailable", "name": "LLM razonador"}

    try:
        with urlopen(f"{server_url}/props", timeout=2) as response:
            properties = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        state = "ready" if health_status == 200 else "loading"
        return {"state": state, "name": "LLM razonador"}

    state = "sleeping" if properties.get("is_sleeping") else "ready"
    return {"state": state, "name": "LLM razonador"}


if __name__ == "__main__":
    main()
