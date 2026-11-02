"""Exports of a trace: JSONL spans, OTLP JSON, Markdown report and battery table."""

import csv
import io
import json

from huggingface_agents_langgraph.domain.trace_export import (
    battery_csv,
    battery_rows,
    otlp_json,
    report_markdown,
    spans_jsonl,
)
from huggingface_agents_langgraph.domain.trace_spans import build_trace


def _record(**overrides):
    record = {
        "id": "11111111-2222-3333-4444-555555555555",
        "created_at": "2026-11-02T10:00:00+00:00",
        "status": "completed",
        "duration_seconds": 3.0,
        "task": {"question": "Capital of France?", "task_id": "t1"},
        "result": {"submitted_answer": "Paris", "draft_answer": "Paris."},
        "steps": [
            {
                "node": "search",
                "update": {"evidence": ["e"]},
                "duration_seconds": 1.0,
                "started_offset_seconds": 0.0,
            },
            {
                "node": "vote",
                "update": {"draft_answer": "Paris"},
                "duration_seconds": 2.0,
                "started_offset_seconds": 1.0,
            },
        ],
        "calls": [
            {
                "messages": [],
                "parameters": {"model": "m", "max_tokens": 8},
                "response": {
                    "choices": [{"finish_reason": "length", "message": {}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 3},
                },
                "content": "x",
                "duration_seconds": 1.5,
                "started_offset_seconds": 1.2,
                "node": "vote",
            }
        ],
    }
    return record | overrides


def test_jsonl_has_one_valid_object_per_span_with_the_trace_id():
    trace = build_trace(_record())

    lines = spans_jsonl(trace).strip().split("\n")

    parsed = [json.loads(line) for line in lines]
    assert len(parsed) == len(trace["spans"])
    assert {item["trace_id"] for item in parsed} == {trace["trace_id"]}
    assert parsed[0]["kind"] == "run"


def test_otlp_uses_hex_ids_nanosecond_times_and_status_codes():
    record = _record(status="failed", error="bad")
    payload = otlp_json(build_trace(record), record)

    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(spans[0]["traceId"]) == 32 and int(spans[0]["traceId"], 16) >= 0
    assert all(len(span["spanId"]) == 16 for span in spans)
    root = spans[0]
    assert "parentSpanId" not in root or root["parentSpanId"] == ""
    assert root["status"]["code"] == 2
    child = next(span for span in spans if span["name"] == "vote")
    assert child["parentSpanId"] == root["spanId"]
    start, end = int(child["startTimeUnixNano"]), int(child["endTimeUnixNano"])
    assert end - start == 2_000_000_000
    assert start - int(root["startTimeUnixNano"]) == 1_000_000_000


def test_otlp_llm_span_carries_gen_ai_attributes():
    record = _record()
    spans = otlp_json(build_trace(record), record)["resourceSpans"][0]["scopeSpans"][0][
        "spans"
    ]

    llm = next(span for span in spans if span["name"] == "llm_call")
    values = {a["key"]: a["value"] for a in llm["attributes"]}
    assert values["gen_ai.request.model"] == {"stringValue": "m"}
    assert values["gen_ai.usage.input_tokens"] == {"intValue": "10"}
    assert values["gen_ai.usage.output_tokens"] == {"intValue": "3"}


def test_markdown_report_answers_what_happened_and_where_it_went_wrong():
    record = _record()

    text = report_markdown(record, build_trace(record))

    assert "Capital of France?" in text
    assert "Paris" in text
    assert "| vote |" in text
    assert "length" in text  # the call hit the token limit
    assert text.count("\n# ") == 0 and text.startswith("# ")


def test_markdown_report_lists_errors_first_when_the_run_failed():
    record = _record(status="failed", error="Pipeline time budget exhausted")

    text = report_markdown(record, build_trace(record))

    assert "Pipeline time budget exhausted" in text
    assert text.index("Pipeline time budget exhausted") < text.index("| vote |")


def test_markdown_report_truncates_long_texts():
    record = _record()
    record["task"]["question"] = "q" * 5000

    assert len(report_markdown(record, build_trace(record))) < 4000


def _experiment():
    base = {
        "route": "web",
        "duration_seconds": 10.0,
        "llm_calls": 3,
        "completion_tokens": 100,
        "truncated_calls": 0,
        "run_id": "r1",
        "stage_seconds": {"router": 1.0, "review": 6.0},
        "locally_correct": True,
        "submitted_answer": "a",
    }
    return {
        "id": "e1",
        "answers": [
            base | {"task_id": "t1"},
            base
            | {
                "task_id": "t2",
                "locally_correct": False,
                "error": "truncated",
                "route": "error",
            },
            {"task_id": "t3", "submitted_answer": "", "error": "x"},
        ],
    }


def test_battery_rows_have_one_row_per_task_with_the_slowest_stage():
    rows = battery_rows(_experiment())

    assert [row["task_id"] for row in rows] == ["t1", "t2", "t3"]
    assert rows[0]["slowest_stage"] == "review"
    assert rows[0]["correct"] is True and rows[1]["correct"] is False
    assert rows[1]["error"] == "truncated"
    assert rows[2]["slowest_stage"] is None and rows[2]["correct"] is None


def test_battery_csv_round_trips_and_never_contains_reference_answers():
    parsed = list(csv.DictReader(io.StringIO(battery_csv(_experiment()))))

    assert len(parsed) == 3
    assert parsed[0]["correct"] == "true" and parsed[2]["correct"] == ""
    assert "expected" not in parsed[0] and "final_answer" not in parsed[0]


def test_markdown_report_says_what_each_node_did():
    record = _record()
    record["steps"][1]["update"] = {
        "research_action": {"action": "fetch", "url": "https://x.org/p", "reason": "r"}
    }

    text = report_markdown(record, build_trace(record))

    assert "Qué hizo" in text
    assert "fetch https://x.org/p — r" in text


def test_markdown_report_warns_about_figures_missing_from_the_evidence():
    record = _record()
    record["steps"][1]["update"] = {
        "research_action": {"action": "finish", "reason": "he had 568 at bats"}
    }

    text = report_markdown(record, build_trace(record))

    assert "Cifras sin respaldo en la evidencia" in text
    assert "568" in text
