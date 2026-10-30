import json
from contextlib import contextmanager
from io import BytesIO

import pytest

from huggingface_agents_langgraph import (
    llm,
    multimedia_processing,
    reasoning,
    web_research,
)
from huggingface_agents_langgraph.answer_contract import AnswerContract
from huggingface_agents_langgraph.calculation import (
    calculate,
    execution_environment,
    validate_expression,
)
from huggingface_agents_langgraph.evidence_selection import select_relevant_evidence
from huggingface_agents_langgraph.experiment_runner import (
    timing_summary,
    variant_config,
)
from huggingface_agents_langgraph.experiments import IMPROVEMENTS, normalize_experiment
from huggingface_agents_langgraph.run_tracking import RunTrace, current_trace
from huggingface_agents_langgraph.source_store import read_source, source_catalog
from huggingface_agents_langgraph.spreadsheet_tools import aggregate_table


@contextmanager
def features(*names):
    config = normalize_experiment(
        {"pipeline_version": "3", "improvements": list(names)}
    )
    trace = RunTrace(experiment=config)
    token = current_trace.set(trace)
    try:
        yield trace
    finally:
        current_trace.reset(token)


@pytest.mark.parametrize(
    "field,value",
    [
        ("pipeline_version", "4"),
        ("improvements", ["missing"]),
        ("thinking_tokens", True),
        ("solution_tokens", 0),
    ],
)
def test_rejects_invalid_v3_configuration(field, value):
    with pytest.raises(ValueError):
        normalize_experiment({"pipeline_version": "3", field: value})


def test_ablation_changes_only_the_selected_feature():
    reference = normalize_experiment(
        {"model": {"provider": "configured", "model_id": "same"}}
    )
    for feature in IMPROVEMENTS:
        config = variant_config(reference, feature)
        assert config["improvements"] == [feature]
        assert config["model"] == reference["model"]
        assert config["enabled_capabilities"] == reference["enabled_capabilities"]
    assert variant_config(reference, "baseline")["pipeline_version"] == "2"
    assert variant_config(reference, "combined")["improvements"] == list(IMPROVEMENTS)


@pytest.mark.parametrize(
    "question,answer,expected",
    [
        (
            "Alphabetize a comma-separated list",
            "zebra, fresh apples",
            "fresh apples, zebra",
        ),
        ("Comma-delimited list in ascending order", "20, 3, 10", "3, 10, 20"),
        ("Use two decimal places", "12.5", "12.50"),
        ("Keep the order", "zebra, apple", "zebra, apple"),
    ],
)
def test_contract_changes_presentation_only(question, answer, expected):
    assert AnswerContract.from_question(question).present(answer) == expected


def test_truncated_reasoning_continues_partial_work_once(monkeypatch):
    calls = []

    def complete(messages, **parameters):
        calls.append((list(messages), parameters))
        if len(calls) == 1:
            raise llm.CompletionTruncatedError(
                "limit", "A verified intermediate result"
            )
        return "Candidate"

    monkeypatch.setattr(reasoning, "chat_completion", complete)
    with features("reasoning_control") as trace:
        result = reasoning.reasoning(
            {"question": "An unseen task", "experiment": trace.experiment}
        )
    assert result["draft_answer"] == "Candidate"
    assert calls[0][1]["thinking_budget"] == 512
    assert calls[1][1]["thinking"] is False
    assert calls[1][0][-2]["content"] == "A verified intermediate result"


def test_native_thinking_controls_are_absent_for_v2(monkeypatch):
    requests = []

    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def respond(request, **_kwargs):
        requests.append(json.loads(request.data))
        return Response(
            json.dumps({"choices": [{"message": {"content": "answer"}}]}).encode()
        )

    monkeypatch.setattr(llm, "urlopen", respond)
    llm.chat_completion([{"role": "user", "content": "Task"}])
    with features("reasoning_control"):
        llm.chat_completion(
            [{"role": "user", "content": "Task"}], thinking=True, thinking_budget=32
        )
    assert "chat_template_kwargs" not in requests[0]
    assert requests[1]["reasoning_budget_tokens"] == 32
    assert requests[1]["chat_template_kwargs"] == {"enable_thinking": True}


def test_source_retrieval_retains_text_outside_selected_context():
    text = "ordinary context " * 3000 + "Rare anchor near the end"
    with features("web_sources"):
        selected = select_relevant_evidence(
            "ordinary",
            [
                {
                    "content": text,
                    "source": "https://example.org",
                    "source_type": "web_page",
                }
            ],
        )
        handle = source_catalog()[0]["source_id"]
        reread = read_source(handle, query="Rare anchor")
        assert len(selected[0]["content"]) < len(text)
        assert "Rare anchor" in reread[0]["content"]
        assert len(reread[0]["content"]) <= 8000
    assert source_catalog() == []


def test_v3_html_parser_does_not_swallow_text_after_void_elements():
    with features("web_sources"):
        parser = web_research._WikipediaHTMLTextParser()
        parser.feed('<div class="navbox"><br>Navigation</div><p>Useful text.</p>')
        assert parser.get_text() == "Useful text."


def test_multi_column_sum_uses_all_rows_and_decimal_values():
    sheets = {
        "Sales": [
            ["Location", "Bread", "Soup", "Water"],
            ["North", 0.1, 0.2, 7],
            ["South", 0.3, 0.4, 8],
        ]
    }
    plan = {
        "sheet": "Sales",
        "columns": ["Bread", "Soup"],
        "operation": "sum",
        "filters": [],
    }
    result = aggregate_table(sheets, plan, "Total food sales")
    assert result["value"] == "1.0"
    assert result["included_rows"] == [2, 3]
    assert result["numeric_cells"] == 4
    plan["filters"] = [
        {
            "column": "Location",
            "operator": "not_equals",
            "value": "South",
            "question_span": "excluding South",
        }
    ]
    with pytest.raises(ValueError, match="question"):
        aggregate_table(sheets, plan, "Total food sales")


def test_calculation_supports_text_but_blocks_arbitrary_attributes(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "test-only-secret")
    assert "HF_TOKEN" not in execution_environment()
    with features("calculation_tools"):
        assert json.loads(calculate("''.join(reversed('abc'))")) == "cba"
        assert json.loads(calculate("'Beta alpha'.lower().split()")) == [
            "beta",
            "alpha",
        ]
    for expression in ("'x'.__class__", "open('file')", "().__class__", "'x'.format()"):
        with pytest.raises(ValueError):
            validate_expression(expression, enhanced=True)


def test_dialogue_downloads_audio_and_skips_visual_inference(monkeypatch, tmp_path):
    path = tmp_path / "audio.webm"
    path.touch()
    requests = []
    monkeypatch.setattr(
        llm, "chat_completion", lambda *_a, **_k: '{"audio":true,"vision":false}'
    )

    def download(_url, _directory, *, audio_only=False):
        requests.append(audio_only)
        return path

    monkeypatch.setattr(multimedia_processing, "download_video", download)
    monkeypatch.setattr(multimedia_processing, "RUNTIME_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(multimedia_processing, "_has_audio_stream", lambda _path: True)
    monkeypatch.setattr(
        multimedia_processing, "_transcribe", lambda _path: "Recorded dialogue"
    )
    monkeypatch.setattr(
        multimedia_processing,
        "_sample_video_frames",
        lambda _path: pytest.fail("No frames needed"),
    )
    with features("multimedia_tools") as trace:
        result = multimedia_processing.multimedia_processing(
            {
                "question": "What does the speaker say in https://youtu.be/test?",
                "experiment": trace.experiment,
                "file_name": "",
                "task_id": "test",
            }
        )
    assert requests == [True]
    assert result["evidence"][0]["source_type"] == "audio_transcription"
    assert "video_path" not in result


def test_timing_statistics_preserve_slow_outliers():
    metrics = timing_summary([{"duration_seconds": value} for value in [1, 2, 100]])
    assert metrics["median_seconds"] == 2
    assert metrics["p95_seconds"] == 100
    assert metrics["count"] == 3


def test_experiment_resume_keeps_completed_tasks_and_excludes_reference_answers(
    monkeypatch,
    tmp_path,
):
    from huggingface_agents_langgraph import experiment_runner, run_tracking

    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(
        experiment_runner, "source_identity", lambda: {"source_sha256": "fixed"}
    )
    calls = []

    def interrupted(task):
        assert set(task) == {"task_id", "question", "file_name", "experiment"}
        calls.append(task["task_id"])
        if len(calls) == 2:
            raise KeyboardInterrupt
        return {"submitted_answer": "candidate", "route": "direct"}

    monkeypatch.setattr(experiment_runner, "run_pipeline", interrupted)
    tasks = [
        {
            "task_id": str(index),
            "question": "An unseen task",
            "file_name": "",
            "submitted_answer": "historical candidate",
            "locally_correct": True,
        }
        for index in range(2)
    ]
    config = normalize_experiment(None)
    with pytest.raises(KeyboardInterrupt):
        experiment_runner.run_experiment(tasks, config, group_id="group", score=False)
    record = run_tracking.list_records("experiments")[0]
    assert len(record["answers"]) == 1
    monkeypatch.setattr(
        experiment_runner,
        "run_pipeline",
        lambda task: {
            "submitted_answer": "second",
            "route": "direct",
        },
    )
    resumed = experiment_runner.run_experiment(
        tasks,
        config,
        group_id="group",
        score=False,
        record=record,
    )
    assert resumed["id"] == record["id"]
    assert [answer["submitted_answer"] for answer in resumed["answers"]] == [
        "candidate",
        "second",
    ]
    assert resumed["status"] == "completed"
