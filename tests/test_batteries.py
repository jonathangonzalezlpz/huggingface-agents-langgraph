"""BatteryManager: one background battery at a time, stoppable and resumable."""

import threading

import pytest

from huggingface_agents_langgraph import run_tracking
from huggingface_agents_langgraph.batteries import (
    BatteryBusyError,
    BatteryManager,
    BatteryUnavailableError,
    load_reference_tasks,
)
from huggingface_agents_langgraph.pipeline_versions import V2_REFERENCE_ID

TASKS = [{"task_id": f"t{n}", "question": f"q{n}", "file_name": ""} for n in (1, 2)]


@pytest.fixture(autouse=True)
def runtime_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))


def fake_runner(gate=None, fail=None):
    """A runner that answers task by task, optionally waiting on ``gate``."""
    calls = []

    def runner(tasks, config, *, group_id, record=None, should_stop, on_progress):
        calls.append({"tasks": tasks, "config": config, "record": record})
        record = record or {
            "id": "11111111-1111-4111-8111-111111111111",
            "config": config,
            "questions": tasks,
            "answers": [],
        }
        record["status"] = "running"
        on_progress(record)
        if fail:
            raise ValueError(fail)
        for task in tasks:
            if any(a["task_id"] == task["task_id"] for a in record["answers"]):
                continue
            if gate:
                gate.wait(5)
            if should_stop():
                record["status"] = "cancelled"
                on_progress(record)
                return record
            record["answers"].append({"task_id": task["task_id"]})
            on_progress(record)
        record["status"] = "completed"
        on_progress(record)
        return record

    runner.calls = calls
    return runner


def manager(runner, tasks=TASKS):
    return BatteryManager(runner=runner, task_loader=lambda limit: tasks[:limit])


def test_idle_before_anything_runs():
    assert manager(fake_runner()).status() == {"state": "idle"}


def test_runs_to_completion_and_reports_progress():
    battery = manager(fake_runner())
    started = battery.start({"name": "x"})
    assert started["total"] == 2
    battery.wait(5)
    status = battery.status()
    assert status["state"] == "completed"
    assert status["completed"] == 2
    assert status["experiment_id"] == "11111111-1111-4111-8111-111111111111"


def test_passes_the_normalized_config_and_limit():
    runner = fake_runner()
    battery = manager(runner)
    battery.start(
        {"name": "x", "pipeline_version": "3.1", "architecture": "builtin:gaia_v31"},
        limit=1,
    )
    battery.wait(5)
    call = runner.calls[0]
    assert len(call["tasks"]) == 1
    assert call["config"]["architecture"] == "builtin:gaia_v31"
    assert call["config"]["seed"] == 42


def test_rejects_an_invalid_experiment_without_starting():
    runner = fake_runner()
    battery = manager(runner)
    with pytest.raises(ValueError):
        battery.start({"pipeline_version": "9"})
    assert runner.calls == []
    assert battery.status() == {"state": "idle"}


def test_only_one_battery_runs_at_a_time():
    gate = threading.Event()
    battery = manager(fake_runner(gate))
    battery.start({"name": "x"})
    with pytest.raises(BatteryBusyError):
        battery.start({"name": "y"})
    gate.set()
    battery.wait(5)
    battery.start({"name": "z"})
    battery.wait(5)


def test_stop_ends_the_battery_after_the_current_question():
    gate = threading.Event()
    battery = manager(fake_runner(gate))
    battery.start({"name": "x"})
    assert battery.stop()["state"] == "stopping"
    gate.set()
    battery.wait(5)
    assert battery.status()["state"] == "cancelled"


def test_stop_with_nothing_running_changes_nothing():
    assert manager(fake_runner()).stop() == {"state": "idle"}


def test_a_failing_runner_is_reported_not_raised():
    battery = manager(fake_runner(fail="code changed"))
    battery.start({"name": "x"})
    battery.wait(5)
    status = battery.status()
    assert status["state"] == "failed"
    assert "code changed" in status["error"]


def test_resumes_a_stored_experiment_with_its_own_config_and_questions():
    stored = {
        "id": "22222222-2222-4222-8222-222222222222",
        "config": {"name": "old", "pipeline_version": "2"},
        "questions": TASKS,
        "evaluation_group_id": "g-old",
        "answers": [{"task_id": "t1"}],
        "status": "cancelled",
    }
    run_tracking.write_record("experiments", stored)
    runner = fake_runner()
    battery = manager(runner)
    started = battery.start(None, resume_id=stored["id"])
    assert started["experiment_id"] == stored["id"]
    battery.wait(5)
    call = runner.calls[0]
    assert call["config"]["name"] == "old"
    assert call["tasks"] == TASKS
    assert battery.status()["completed"] == 2


def test_refuses_to_resume_a_finished_or_missing_experiment():
    done = {
        "id": "33333333-3333-4333-8333-333333333333",
        "config": {},
        "questions": TASKS,
        "answers": [],
        "status": "completed",
    }
    run_tracking.write_record("experiments", done)
    battery = manager(fake_runner())
    with pytest.raises(ValueError):
        battery.start(None, resume_id=done["id"])
    with pytest.raises(FileNotFoundError):
        battery.start(None, resume_id="44444444-4444-4444-8444-444444444444")


def test_reference_tasks_come_from_the_frozen_record():
    run_tracking.write_record(
        "experiments",
        {
            "id": V2_REFERENCE_ID,
            "answers": [
                {
                    "task_id": "a",
                    "question": "qa",
                    "file_name": "",
                    "submitted_answer": "no",
                },
                {
                    "task_id": "b",
                    "question": "qb",
                    "file_name": "f.txt",
                    "submitted_answer": "no",
                },
            ],
        },
    )
    tasks = load_reference_tasks(1)
    assert tasks == [{"task_id": "a", "question": "qa", "file_name": ""}]


def test_missing_reference_is_reported_as_unavailable():
    with pytest.raises(BatteryUnavailableError):
        load_reference_tasks(20)
