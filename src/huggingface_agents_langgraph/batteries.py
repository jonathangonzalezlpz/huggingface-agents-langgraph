"""Run a question battery in the background so it outlives the browser tab.

One battery runs at a time. It reuses ``experiment_runner.run_experiment``, so its
records are the same ones the command line produces (source identity, task-set hash,
timings) and can be compared and resumed in the same way.
"""

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from huggingface_agents_langgraph.experiment_runner import run_experiment
from huggingface_agents_langgraph.experiments import normalize_experiment
from huggingface_agents_langgraph.pipeline_versions import V2_REFERENCE_ID
from huggingface_agents_langgraph.run_tracking import read_record

MAX_QUESTIONS = 20
_FINISHED = {"completed", "cancelled", "failed"}


class BatteryBusyError(RuntimeError):
    """A battery is already running."""


class BatteryUnavailableError(RuntimeError):
    """The frozen question set the batteries run on is not on this machine."""


def load_reference_tasks(limit: int = MAX_QUESTIONS) -> list[dict]:
    """The frozen GAIA validation questions, in the order every experiment uses."""
    try:
        reference = read_record("experiments", V2_REFERENCE_ID)
    except FileNotFoundError as error:
        raise BatteryUnavailableError(
            "The frozen V2 reference record is missing; batteries need its questions"
        ) from error
    return [
        {key: answer.get(key, "") for key in ("task_id", "question", "file_name")}
        for answer in reference["answers"][:limit]
    ]


class BatteryManager:
    """Start, observe, stop and resume the single active battery."""

    def __init__(
        self,
        runner: Callable[..., dict] = run_experiment,
        task_loader: Callable[[int], list[dict]] = load_reference_tasks,
    ) -> None:
        self._runner = runner
        self._load_tasks = task_loader
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._status: dict[str, Any] = {"state": "idle"}

    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def start(
        self,
        experiment: object,
        *,
        limit: int = MAX_QUESTIONS,
        resume_id: str | None = None,
    ) -> dict:
        """Launch a battery, or resume an unfinished experiment, in the background."""
        if type(limit) is not int or not 1 <= limit <= MAX_QUESTIONS:
            raise ValueError(f"limit must be between 1 and {MAX_QUESTIONS}")
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise BatteryBusyError("A battery is already running")
            record = None
            if resume_id is not None:
                record = read_record("experiments", resume_id)
                if record.get("status") == "completed":
                    raise ValueError("This experiment is already completed")
                config = record["config"]
                tasks = record["questions"]
                group_id = record.get("evaluation_group_id", str(uuid4()))
            else:
                config = normalize_experiment(experiment)
                tasks = self._load_tasks(limit)
                group_id = str(uuid4())
            self._stop.clear()
            self._status = {
                "state": "running",
                "experiment_id": record["id"] if record else None,
                "name": config.get("name"),
                "completed": len(record["answers"]) if record else 0,
                "total": len(tasks),
                "started_at": datetime.now(UTC).isoformat(),
                "error": None,
            }
            self._thread = threading.Thread(
                target=self._run,
                args=(tasks, config, group_id, record),
                name="battery",
                daemon=True,
            )
            self._thread.start()
            return dict(self._status)

    def stop(self) -> dict:
        """Ask the battery to finish after the question in progress."""
        with self._lock:
            if self._status["state"] == "running":
                self._stop.set()
                self._status["state"] = "stopping"
            return (
                dict(self._status)
                if self._status["state"] != "idle"
                else {"state": "idle"}
            )

    def wait(self, timeout: float | None = None) -> None:
        """Block until the background work ends (used by tests)."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _run(
        self, tasks: list[dict], config: dict, group_id: str, record: dict | None
    ) -> None:
        try:
            self._runner(
                tasks,
                config,
                group_id=group_id,
                record=record,
                should_stop=self._stop.is_set,
                on_progress=self._on_progress,
            )
        except Exception as error:  # noqa: BLE001 - reported to the client
            with self._lock:
                self._status.update(state="failed", error=str(error))

    def _on_progress(self, record: dict) -> None:
        with self._lock:
            self._status["experiment_id"] = record["id"]
            self._status["completed"] = len(record["answers"])
            if record["status"] in _FINISHED:
                self._status["state"] = record["status"]
