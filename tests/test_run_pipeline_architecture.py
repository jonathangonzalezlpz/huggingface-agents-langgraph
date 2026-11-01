"""run_pipeline executes the selected architecture and records which one ran."""

import pytest

from huggingface_agents_langgraph import run_tracking
from huggingface_agents_langgraph.architecture_store import BUILTIN_V31_ID

VOLATILE = {
    "run_id",
    "duration_seconds",
    "llm_duration_seconds",
    "model_load_seconds",
}


@pytest.fixture(autouse=True)
def runtime_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))


def _task(**experiment):
    return {
        "task_id": "t",
        "question": "web question",
        "file_name": "",
        "experiment": experiment,
    }


def _stable(result):
    return {k: v for k, v in result.items() if k not in VOLATILE}


def _steps(run_id):
    record = run_tracking.read_record("runs", run_id)
    return [
        {k: v for k, v in step.items() if k != "duration_seconds"}
        for step in record["steps"]
    ]


@pytest.mark.usefixtures("stubbed_nodes")
class TestRunPipelineArchitecture:
    def test_default_run_records_the_runtime_engine(self):
        result = run_tracking.run_pipeline(_task())
        record = run_tracking.read_record("runs", result["run_id"])
        assert record["architecture"] == {"engine": "graph.py"}

    def test_compiled_builtin_matches_the_runtime_graph(self):
        legacy = run_tracking.run_pipeline(_task())
        compiled = run_tracking.run_pipeline(_task(architecture=BUILTIN_V31_ID))
        assert _stable(compiled)["submitted_answer"] == "answer"
        assert _steps(compiled["run_id"]) == _steps(legacy["run_id"])
        assert {k: v for k, v in _stable(compiled).items() if k != "experiment"} == {
            k: v for k, v in _stable(legacy).items() if k != "experiment"
        }

    def test_compiled_run_records_the_architecture_identity(self):
        result = run_tracking.run_pipeline(_task(architecture=BUILTIN_V31_ID))
        record = run_tracking.read_record("runs", result["run_id"])
        assert record["architecture"]["engine"] == "compiled"
        assert record["architecture"]["id"] == BUILTIN_V31_ID
        assert len(record["architecture"]["content_sha256"]) == 64

    def test_architecture_changes_the_configuration_hash(self):
        legacy = run_tracking.run_pipeline(_task())
        compiled = run_tracking.run_pipeline(_task(architecture=BUILTIN_V31_ID))
        hashes = {
            run_tracking.read_record("runs", r["run_id"])["configuration_sha256"]
            for r in (legacy, compiled)
        }
        assert len(hashes) == 2

    def test_unknown_architecture_fails_and_is_recorded(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown architecture") as error:
            run_tracking.run_pipeline(_task(architecture="nope"))
        record = run_tracking.read_record("runs", error.value.run_id)
        assert record["status"] == "error"
