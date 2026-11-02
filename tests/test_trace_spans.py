"""Spans derived from a run record: hierarchy, status, tokens and lazy payloads."""

import json

from huggingface_agents_langgraph.domain.trace_spans import (
    build_trace,
    span_payload,
)


def _call(node, offset, duration=1.0, **extra):
    base = {
        "messages": [{"role": "user", "content": "hello"}],
        "parameters": {"max_tokens": 64, "temperature": 0.2, "model": "m"},
        "request": {"messages": []},
        "response": {
            "choices": [{"finish_reason": "stop", "message": {"content": "hi"}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 3,
                "prompt_tokens_details": {"cached_tokens": 4},
            },
        },
        "endpoint": "http://127.0.0.1:8080/v1",
        "content": "hi",
        "duration_seconds": duration,
        "started_offset_seconds": offset,
        "node": node,
    }
    return base | extra


def _record(**overrides):
    record = {
        "id": "run-1",
        "status": "completed",
        "duration_seconds": 3.0,
        "steps": [
            {
                "node": "search",
                "update": {"evidence": ["x" * 100]},
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
        "calls": [_call("vote", 1.2, 1.5)],
        "sources": {"a": {"content": "y" * 1000}},
    }
    return record | overrides


def test_run_span_is_the_root_and_nodes_hang_from_it():
    trace = build_trace(_record())

    root, *others = trace["spans"]
    assert root["kind"] == "run" and root["parent_id"] is None
    assert trace["trace_id"] == "run-1"
    nodes = [span for span in others if span["kind"] == "node"]
    assert [span["name"] for span in nodes] == ["search", "vote"]
    assert all(span["parent_id"] == root["span_id"] for span in nodes)


def test_llm_call_hangs_from_its_node_and_reports_tokens():
    trace = build_trace(_record())

    llm = next(span for span in trace["spans"] if span["kind"] == "llm")
    vote = next(span for span in trace["spans"] if span["name"] == "vote")
    assert llm["parent_id"] == vote["span_id"]
    attributes = llm["attributes"]
    assert attributes["prompt_tokens"] == 10
    assert attributes["completion_tokens"] == 3
    assert attributes["cached_tokens"] == 4
    assert attributes["finish_reason"] == "stop"
    assert attributes["model"] == "m"


def test_failed_step_and_call_are_marked_as_errors():
    record = _record(
        status="failed",
        steps=[
            {
                "node": "search",
                "error": "boom",
                "duration_seconds": 1.0,
                "started_offset_seconds": 0.0,
            }
        ],
        calls=[
            {
                "messages": [],
                "parameters": {},
                "error": "timeout",
                "duration_seconds": 0.5,
                "started_offset_seconds": 0.1,
                "node": "search",
            }
        ],
    )

    trace = build_trace(record)

    by_kind = {span["kind"]: span for span in trace["spans"]}
    assert by_kind["node"]["status"] == "error"
    assert by_kind["node"]["error"] == "boom"
    assert by_kind["llm"]["status"] == "error"
    assert by_kind["llm"]["error"] == "timeout"
    assert by_kind["run"]["status"] == "error"
    assert trace["summary"]["error_count"] == 3


def test_legacy_record_without_offsets_is_laid_out_sequentially():
    record = _record()
    for step in record["steps"]:
        del step["started_offset_seconds"]
    for call in record["calls"]:
        del call["started_offset_seconds"]
        del call["node"]
        call["duration_seconds"] = 99.0  # fits no step, so it cannot be linked

    trace = build_trace(record)

    nodes = [span for span in trace["spans"] if span["kind"] == "node"]
    assert [span["start_offset_seconds"] for span in nodes] == [0.0, 1.0]
    llm = next(span for span in trace["spans"] if span["kind"] == "llm")
    assert llm["parent_id"] == trace["spans"][0]["span_id"]
    assert llm["attributes"]["linked_to_node"] is False


def test_summary_points_at_the_slowest_node_and_totals_the_tokens():
    summary = build_trace(_record())["summary"]

    assert summary["slowest_node"] == {"name": "vote", "duration_seconds": 2.0}
    assert summary["llm_calls"] == 1
    assert summary["prompt_tokens"] == 10
    assert summary["completion_tokens"] == 3
    assert summary["status"] == "completed"


def test_trace_is_small_and_excludes_heavy_payloads():
    record = _record(sources={"a": {"content": "y" * 200_000}})
    record["calls"][0]["messages"][0]["content"] = "z" * 50_000
    trace = build_trace(record)

    text = json.dumps(trace)
    assert "yyyy" not in text and "zzzz" not in text and "xxxx" not in text
    assert len(text) < 5_000


def test_payload_of_a_node_and_of_a_call_is_loaded_on_demand():
    trace = build_trace(_record())
    llm = next(span for span in trace["spans"] if span["kind"] == "llm")
    vote = next(span for span in trace["spans"] if span["name"] == "vote")

    assert span_payload(_record(), vote["span_id"]) == {
        "update": {"draft_answer": "Paris"}
    }
    payload = span_payload(_record(), llm["span_id"])
    assert payload["messages"][0]["content"] == "hello"
    assert payload["content"] == "hi"


def test_span_ids_are_stable_and_unknown_payload_is_none():
    assert build_trace(_record()) == build_trace(_record())
    assert span_payload(_record(), "nope") is None


def test_record_without_steps_still_yields_a_run_span():
    trace = build_trace({"id": "r", "status": "failed", "error": "bad"})

    assert [span["kind"] for span in trace["spans"]] == ["run"]
    assert trace["spans"][0]["error"] == "bad"


def test_a_model_given_as_provider_and_id_is_reported_as_its_id():
    record = _record()
    record["calls"][0]["parameters"]["model"] = {
        "provider": "configured",
        "model_id": "unsloth/Qwen3.5-9B-GGUF:Q5_K_M",
    }

    llm = next(s for s in build_trace(record)["spans"] if s["kind"] == "llm")

    assert llm["attributes"]["model"] == "unsloth/Qwen3.5-9B-GGUF:Q5_K_M"


def test_every_attribute_is_a_scalar_or_a_list_of_strings():
    record = _record()
    record["calls"][0]["parameters"]["model"] = {"odd": 1}
    record["calls"][0]["parameters"]["thinking"] = {"budget": 3}

    for span in build_trace(record)["spans"]:
        for value in span["attributes"].values():
            assert isinstance(value, (str, int, float, bool)) or (
                isinstance(value, list) and all(isinstance(v, str) for v in value)
            )
