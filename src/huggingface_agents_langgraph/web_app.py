"""Serve a small local interface for GAIA questions and agent runs."""

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from huggingface_agents_langgraph.architecture_store import (
    ArchitectureNotFoundError,
    architecture_detail,
    get_catalog,
    get_layout,
    list_architectures,
    save_architecture,
    save_layout,
    validate_definition,
)
from huggingface_agents_langgraph.attachments import get_attachment_path
from huggingface_agents_langgraph.batteries import (
    BatteryBusyError,
    BatteryManager,
    BatteryUnavailableError,
)
from huggingface_agents_langgraph.config import LLM_BASE_URL, MODEL_SERVER_MODE
from huggingface_agents_langgraph.experiment_comparison import compare_experiments
from huggingface_agents_langgraph.experiment_scoring import (
    evaluate_experiment,
    official_answers,
    record_official_score,
)
from huggingface_agents_langgraph.graph_definition import AgentDefinition
from huggingface_agents_langgraph.llm import get_available_models
from huggingface_agents_langgraph.local_evaluation import evaluate_validation_answers
from huggingface_agents_langgraph.model_server import gpu_memory, model_inventory
from huggingface_agents_langgraph.multimedia_processing import (
    get_gpu_status,
    get_multimedia_model_status,
)
from huggingface_agents_langgraph.pipeline_versions import experiment_presentation
from huggingface_agents_langgraph.resource_tracking import host_memory
from huggingface_agents_langgraph.run_tracking import (
    delete_record,
    list_records,
    read_record,
    run_pipeline,
    write_record,
)

SCORING_API_URL = "https://agents-course-unit4-scoring.hf.space"
APP_DIRECTORY = Path(__file__).parent / "static" / "app"
APP_PREFIX = "/app"
WEB_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".map": "application/json; charset=utf-8",
}
BUNDLE_NOT_BUILT = (
    "<!doctype html><meta charset=utf-8><title>GAIA Agent Studio</title>"
    "<h1>GAIA Agent Studio is not built</h1>"
    "<p>Run <code>scripts/build_frontend.ps1</code> and reload. "
    'The previous interface is still available at <a href="/">/</a>.</p>'
)
MAX_REQUEST_BYTES = 1_000_000
MAX_COMPARED_EXPERIMENTS = 20


BATTERIES = BatteryManager()


class WebAppHandler(BaseHTTPRequestHandler):
    """Handle frontend assets and local API requests."""

    def do_GET(self) -> None:
        """Serve the application, questions, or an attachment."""
        request_path = urlsplit(self.path).path
        if request_path == APP_PREFIX or request_path.startswith(APP_PREFIX + "/"):
            self._serve_app(request_path.removeprefix(APP_PREFIX))
        elif request_path == "/":
            self._redirect(APP_PREFIX + "/")
        elif request_path in {"/api/questions", "/api/random-question"}:
            self._get_questions(request_path)
        elif request_path == "/api/status":
            inventory = model_inventory() if MODEL_SERVER_MODE == "exclusive" else []
            model_cards = [
                {
                    "name": "LLM / VLM" if model["vision"] else "LLM razonador",
                    "model": model["model_id"],
                    "state": model["state"],
                }
                for model in inventory
            ]
            if not model_cards and MODEL_SERVER_MODE == "exclusive":
                model_cards = [{"name": "Router LLM / VLM", "state": "unavailable"}]
            self._send_json(
                200,
                {
                    "llm": _get_llm_status()
                    if MODEL_SERVER_MODE != "exclusive"
                    else {
                        "state": "ready" if inventory else "unavailable",
                        "name": "Router · GPU exclusiva",
                    },
                    "gpu": get_gpu_status(),
                    "host_memory": host_memory(),
                    "multimedia_models": get_multimedia_model_status(),
                    **(
                        {
                            "model_cards": [
                                *model_cards,
                                *[
                                    item | {"name": item["name"] + " · CPU"}
                                    for item in get_multimedia_model_status()
                                ],
                            ],
                            "gpu_memory": gpu_memory(),
                            "gpu_policy": "exclusive",
                        }
                        if MODEL_SERVER_MODE == "exclusive"
                        else {}
                    ),
                },
            )
        elif request_path == "/api/models":
            inventory = model_inventory() if MODEL_SERVER_MODE == "exclusive" else []
            ready = {
                item["model_id"]
                for item in inventory
                if item["state"] not in {"downloading", "incomplete"}
            }
            models = get_available_models()
            if MODEL_SERVER_MODE == "exclusive":
                models = [
                    model
                    for model in models
                    if model["provider"] == "configured" and model["model_id"] in ready
                ]
            self._send_json(
                200,
                {
                    "models": models,
                    "vision_models": [
                        {"provider": "configured", "model_id": item["model_id"]}
                        for item in inventory
                        if item["vision"] and item["model_id"] in ready
                    ],
                },
            )
        elif request_path == "/api/experiments":
            self._send_json(
                200,
                {
                    "experiments": [
                        experiment_presentation(record)
                        for record in list_records("experiments")
                    ]
                },
            )
        elif request_path == "/api/batteries/current":
            self._send_json(200, BATTERIES.status())
        elif request_path == "/api/architectures":
            self._send_json(200, {"architectures": list_architectures()})
        elif request_path == "/api/catalog":
            self._send_json(200, get_catalog())
        elif request_path.startswith("/api/architectures/"):
            identifier = unquote(request_path.removeprefix("/api/architectures/"))
            try:
                if identifier.endswith("/layout"):
                    self._send_json(200, get_layout(identifier.removesuffix("/layout")))
                else:
                    self._send_json(200, architecture_detail(identifier))
            except ArchitectureNotFoundError:
                self._send_json(404, {"error": "Architecture not found"})
        elif request_path.startswith("/api/runs/"):
            try:
                record = read_record("runs", request_path.removeprefix("/api/runs/"))
                self._send_json(200, record)
            except (ValueError, FileNotFoundError):
                self._send_json(404, {"error": "Run not found"})
        elif request_path.startswith("/api/files/"):
            self._get_attachment(unquote(request_path.removeprefix("/api/files/")))
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        """Run a GAIA task through the local LangGraph workflow."""
        request_path = urlsplit(self.path).path
        if request_path == "/api/experiments":
            self._save_experiment()
            return
        if request_path == "/api/experiments/compare":
            self._compare_experiments()
            return
        if request_path == "/api/batteries":
            self._start_battery()
            return
        if request_path == "/api/batteries/stop":
            self._send_json(200, BATTERIES.stop())
            return
        if request_path == "/api/architectures/validate":
            self._validate_architecture()
            return
        if request_path == "/api/architectures":
            self._save_architecture()
            return
        if request_path == "/api/score":
            self._submit_score()
            return
        if request_path.startswith("/api/experiments/") and request_path.endswith(
            "/evaluate"
        ):
            self._evaluate_stored(
                request_path.removeprefix("/api/experiments/").removesuffix("/evaluate")
            )
            return
        if request_path == "/api/evaluate":
            self._evaluate_locally()
            return
        if request_path != "/api/run":
            self._send_json(404, {"error": "Not found"})
            return

        started_at = perf_counter()
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
                raise ValueError("Request body is empty or too large")
            payload = json.loads(self.rfile.read(content_length))
            task = self._validate_task(payload)
            result = run_pipeline(task)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._send_json(
                400,
                {
                    "error": str(error),
                    "run_id": getattr(error, "run_id", None),
                    "pipeline_version": getattr(error, "pipeline_version", None),
                    "llm_duration_seconds": getattr(
                        error, "llm_duration_seconds", None
                    ),
                    "duration_seconds": round(perf_counter() - started_at, 3),
                },
            )
            return
        except Exception as error:
            self._send_json(
                500,
                {
                    "error": str(error),
                    "run_id": getattr(error, "run_id", None),
                    "pipeline_version": getattr(error, "pipeline_version", None),
                    "llm_duration_seconds": getattr(
                        error, "llm_duration_seconds", None
                    ),
                    "duration_seconds": round(perf_counter() - started_at, 3),
                },
            )
            return

        result["duration_seconds"] = round(perf_counter() - started_at, 3)
        self._send_json(200, result)

    def do_PUT(self) -> None:
        """Store the node layout of an architecture version."""
        path = urlsplit(self.path).path
        prefix, suffix = "/api/architectures/", "/layout"
        if not (path.startswith(prefix) and path.endswith(suffix)):
            self._send_json(404, {"error": "Not found"})
            return
        version_id = unquote(path.removeprefix(prefix).removesuffix(suffix))
        try:
            self._send_json(200, save_layout(version_id, self._read_json_object()))
        except ArchitectureNotFoundError:
            self._send_json(404, {"error": "Architecture not found"})
        except (ValueError, TypeError) as error:
            self._send_json(400, {"error": str(error)})

    def do_DELETE(self) -> None:
        """Remove a selected persisted experiment without deleting other runs."""
        path = urlsplit(self.path).path
        if not path.startswith("/api/experiments/"):
            self._send_json(404, {"error": "Not found"})
            return
        try:
            delete_record("experiments", path.removeprefix("/api/experiments/"))
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
            return
        self._send_json(200, {"deleted": True})

    def _read_json_object(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_REQUEST_BYTES:
            raise ValueError("Request body is empty or too large")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object")
        return payload

    def _start_battery(self) -> None:
        try:
            payload = self._read_json_object()
            limit = payload.get("limit", 20)
            if type(limit) is not int:
                raise ValueError("limit must be an integer")
            resume_id = payload.get("resume_id")
            if resume_id is not None and not isinstance(resume_id, str):
                raise ValueError("resume_id must be an experiment id")
            status = BATTERIES.start(
                payload.get("experiment"), limit=limit, resume_id=resume_id
            )
        except BatteryBusyError as error:
            self._send_json(409, {"error": str(error)})
            return
        except BatteryUnavailableError as error:
            self._send_json(503, {"error": str(error)})
            return
        except FileNotFoundError:
            self._send_json(404, {"error": "Experiment not found"})
            return
        except (ValueError, TypeError, KeyError) as error:
            self._send_json(400, {"error": str(error)})
            return
        self._send_json(202, status)

    def _compare_experiments(self) -> None:
        try:
            payload = self._read_json_object()
            ids = payload.get("ids")
            base = payload.get("base")
            if (
                not isinstance(ids, list)
                or not 2 <= len(ids) <= MAX_COMPARED_EXPERIMENTS
                or not all(isinstance(item, str) for item in ids)
                or len(set(ids)) != len(ids)
            ):
                raise ValueError("ids must list 2 to 20 distinct experiment ids")
            if base is not None and not isinstance(base, str):
                raise ValueError("base must be an experiment id")
            records = []
            for experiment_id in ids:
                try:
                    record = read_record("experiments", experiment_id)
                except FileNotFoundError:
                    self._send_json(
                        404, {"error": f"Experiment not found: {experiment_id}"}
                    )
                    return
                records.append(experiment_presentation(record))
            comparison = compare_experiments(records, base_id=base)
        except (ValueError, TypeError, KeyError) as error:
            self._send_json(400, {"error": str(error)})
            return
        self._send_json(200, comparison)

    def _validate_architecture(self) -> None:
        try:
            report = validate_definition(self._read_json_object())
        except (ValueError, TypeError) as error:
            self._send_json(400, {"error": str(error)})
            return
        self._send_json(200, report)

    def _save_architecture(self) -> None:
        try:
            definition = AgentDefinition.from_dict(self._read_json_object())
            record = save_architecture(definition)
        except (KeyError, ValueError, TypeError, AttributeError) as error:
            message = (
                f"Missing field {error}" if isinstance(error, KeyError) else str(error)
            )
            self._send_json(400, {"error": message})
            return
        self._send_json(200, record)

    def _save_experiment(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                raise ValueError("Invalid experiment size")
            record = json.loads(self.rfile.read(length))
            if (
                not isinstance(record, dict)
                or not isinstance(record.get("answers"), list)
                or len(record["answers"]) > 20
            ):
                raise ValueError("Invalid experiment record")
            write_record("experiments", record)
        except (ValueError, KeyError, TypeError) as error:
            self._send_json(400, {"error": str(error)})
            return
        self._send_json(200, {"saved": True})

    def _evaluate_locally(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
                raise ValueError("Request body is empty or too large")
            payload = json.loads(self.rfile.read(content_length))
            answers = payload.get("answers") if isinstance(payload, dict) else None
            if not isinstance(answers, list) or len(answers) != 20:
                raise ValueError("Exactly 20 answers are required")
            for answer in answers:
                if (
                    not isinstance(answer, dict)
                    or not isinstance(answer.get("task_id"), str)
                    or not isinstance(answer.get("submitted_answer"), str)
                ):
                    raise ValueError("Each answer needs task_id and submitted_answer")
            result = evaluate_validation_answers(answers)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._send_json(400, {"error": str(error)})
            return
        except RuntimeError as error:
            self._send_json(503, {"error": str(error)})
            return
        self._send_json(200, result)

    def _evaluate_stored(self, experiment_id: str) -> None:
        try:
            self._send_json(200, evaluate_experiment(experiment_id))
        except FileNotFoundError:
            self._send_json(404, {"error": "Experiment not found"})
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
        except RuntimeError as error:
            self._send_json(503, {"error": str(error)})

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

    def _submit_score(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
                raise ValueError("Request body is empty or too large")
            payload = json.loads(self.rfile.read(content_length))
            if not isinstance(payload, dict):
                raise ValueError("Score request must be a JSON object")
            username = payload.get("username")
            agent_code = payload.get("agent_code")
            answers = payload.get("answers")
            experiment_id = payload.get("experiment_id")
            if not isinstance(username, str) or not username.strip():
                raise ValueError("username is required")
            if not isinstance(agent_code, str) or not agent_code.strip():
                raise ValueError("agent_code is required")
            if experiment_id is not None:
                if not isinstance(experiment_id, str):
                    raise ValueError("experiment_id must be a string")
                # The stored record is the only source of the answers that get sent.
                answers = official_answers(experiment_id)
            if not isinstance(answers, list) or len(answers) != 20:
                raise ValueError("Exactly 20 answers are required")
            for answer in answers:
                if (
                    not isinstance(answer, dict)
                    or not isinstance(answer.get("task_id"), str)
                    or not isinstance(answer.get("submitted_answer"), str)
                ):
                    raise ValueError("Each answer needs task_id and submitted_answer")
            body = json.dumps(
                {
                    "username": username.strip(),
                    "agent_code": agent_code.strip(),
                    "answers": answers,
                }
            ).encode("utf-8")
            request = Request(
                f"{SCORING_API_URL}/submit",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._send_json(400, {"error": str(error)})
            return
        except FileNotFoundError:
            self._send_json(404, {"error": "Experiment not found"})
            return
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            self._send_json(502, {"error": f"Official scoring failed: {error}"})
            return
        if experiment_id is not None and isinstance(result, dict):
            try:
                record_official_score(experiment_id, result)
                result = {**result, "saved": True}
            except (ValueError, OSError):
                result = {**result, "saved": False}
        self._send_json(200, result)

    @staticmethod
    def _validate_task(payload: object) -> dict:
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

        from huggingface_agents_langgraph.experiments import normalize_experiment

        return {
            "task_id": task_id,
            "question": question,
            "file_name": file_name,
            "experiment": normalize_experiment(payload.get("experiment")),
        }

    def _serve_app(self, relative_path: str) -> None:
        """Serve the compiled application; client routes fall back to the index."""
        root = APP_DIRECTORY.resolve()
        index = root / "index.html"
        if not index.is_file():
            self._send_bytes(404, BUNDLE_NOT_BUILT.encode(), WEB_CONTENT_TYPES[".html"])
            return
        requested = unquote(relative_path).strip("/")
        target = (root / requested).resolve() if requested else index
        if not target.is_relative_to(root):
            target = index
        if target.is_file():
            asset = target
        elif Path(requested).suffix:
            self._send_json(404, {"error": "Asset not found"})
            return
        else:
            asset = index
        cache = "no-cache" if asset == index else "public, max-age=31536000, immutable"
        self._send_bytes(
            200,
            asset.read_bytes(),
            WEB_CONTENT_TYPES.get(asset.suffix.lower(), "application/octet-stream"),
            {"Cache-Control": cache},
        )

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

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
