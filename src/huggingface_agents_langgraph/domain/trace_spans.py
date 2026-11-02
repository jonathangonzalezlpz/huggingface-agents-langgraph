"""Spans derived from a run record: a light tree plus heavy payloads on demand."""

import hashlib
import json

from huggingface_agents_langgraph.domain.trace_activity import (
    node_activity,
    unsupported_figures,
)
from huggingface_agents_langgraph.domain.trace_linking import infer_links

_LLM_PARAMETERS = ("model", "max_tokens", "temperature", "thinking")


def _span_id(trace_id: str, *parts: object) -> str:
    """Stable id: the same record always yields the same spans."""
    text = "|".join([trace_id, *map(str, parts)])
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _status(item: dict) -> str:
    return "error" if item.get("error") else "ok"


def _sequential_offsets(steps: list[dict]) -> list[float]:
    """Legacy records have no start times: lay the steps out one after another."""
    offsets, cursor = [], 0.0
    for step in steps:
        offsets.append(step.get("started_offset_seconds", round(cursor, 4)))
        cursor += step.get("duration_seconds", 0)
    return offsets


def _evidence_texts(record: dict) -> list[str]:
    """Every piece of evidence the run collected, as plain text."""
    items = list((record.get("result") or {}).get("evidence") or [])
    notes = list((record.get("result") or {}).get("research_notes") or [])
    for step in record.get("steps") or []:
        update = step.get("update") or {}
        items.extend(update.get("evidence") or [])
        notes.extend(update.get("research_notes") or [])
    texts = [str(item.get("content", "")) for item in items if isinstance(item, dict)]
    return texts + [str(note) for note in notes]


def _claims(update: dict) -> str:
    """The texts in which a node asserts something that evidence should support."""
    action = update.get("research_action")
    reason = action.get("reason") if isinstance(action, dict) else ""
    answer = update.get("submitted_answer")
    return " ".join(filter(None, [str(reason or ""), str(answer or "")]))


def _node_attributes(
    update: dict, question: str, evidence: list[str], known_notes: int
) -> dict:
    attributes: dict = {"updated_fields": sorted(update)}
    activity = node_activity(update, known_notes)
    if activity:
        attributes["activity"] = activity
    figures = unsupported_figures(_claims(update), question, evidence)
    if figures:
        attributes["unsupported_figures"] = figures
    return attributes


def _node_span(span_id: str, parent: str, step: dict, start: float, attributes: dict):
    return {
        "span_id": span_id,
        "parent_id": parent,
        "kind": "node",
        "name": step["node"],
        "status": _status(step),
        "start_offset_seconds": start,
        "duration_seconds": step.get("duration_seconds", 0),
        "attributes": attributes,
        **({"error": step["error"]} if step.get("error") else {}),
    }


def _scalar(value: object) -> object:
    """Attributes stay flat: a model given as provider and id is reported by its id."""
    if isinstance(value, dict):
        value = value.get("model_id") or json.dumps(value, sort_keys=True)
    return value if isinstance(value, (str, int, float, bool)) else str(value)


def _llm_attributes(call: dict, linked: bool, inferred: bool = False) -> dict:
    response = call.get("response") or {}
    usage = response.get("usage") or {}
    choice = (response.get("choices") or [{}])[0]
    parameters = call.get("parameters") or {}
    attributes = {
        key: _scalar(parameters[key]) for key in _LLM_PARAMETERS if key in parameters
    } | {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "cached_tokens": (usage.get("prompt_tokens_details") or {}).get(
            "cached_tokens"
        ),
        "finish_reason": choice.get("finish_reason"),
        "endpoint": call.get("endpoint"),
        "output_chars": len(call.get("content") or ""),
        "linked_to_node": linked,
    }
    if call.get("model_load_seconds"):
        attributes["model_load_seconds"] = call["model_load_seconds"]
    if inferred:
        attributes["inferred_link"] = True
    return {key: value for key, value in attributes.items() if value is not None}


def _llm_span(
    trace_id: str,
    index: int,
    call: dict,
    placement: tuple[str, float, bool, bool],
):
    parent, start, linked, inferred = placement
    return {
        "span_id": _span_id(trace_id, "llm", index),
        "parent_id": parent,
        "kind": "llm",
        "name": "llm_call",
        "status": _status(call),
        "start_offset_seconds": start,
        "duration_seconds": call.get("duration_seconds", 0),
        "attributes": _llm_attributes(call, linked, inferred),
        **({"error": call["error"]} if call.get("error") else {}),
    }


def _summary(record: dict, spans: list[dict]) -> dict:
    nodes = [span for span in spans if span["kind"] == "node"]
    calls = [span for span in spans if span["kind"] == "llm"]
    slowest = max(nodes, key=lambda span: span["duration_seconds"], default=None)

    def total(key: str) -> int:
        return sum(span["attributes"].get(key) or 0 for span in calls)

    return {
        "status": record.get("status"),
        "duration_seconds": record.get("duration_seconds"),
        "node_count": len(nodes),
        "llm_calls": len(calls),
        "prompt_tokens": total("prompt_tokens"),
        "completion_tokens": total("completion_tokens"),
        "error_count": sum(span["status"] == "error" for span in spans),
        "unsupported_figures": sorted(
            {
                figure
                for span in nodes
                for figure in span["attributes"].get("unsupported_figures", [])
            }
        ),
        "slowest_node": {
            "name": slowest["name"],
            "duration_seconds": slowest["duration_seconds"],
        }
        if slowest
        else None,
    }


def _named_placement(call: dict, node_spans: list[dict], run_id: str):
    """A call that names its node goes to the repetition that contains its start."""
    start = call.get("started_offset_seconds", 0.0)
    candidates = [span for span in node_spans if span["name"] == call.get("node")]
    if not candidates:
        return (run_id, start, False, False)
    container = next(
        (
            span
            for span in candidates
            if span["start_offset_seconds"] - 0.05
            <= start
            <= span["start_offset_seconds"] + span["duration_seconds"] + 0.05
        ),
        candidates[0],
    )
    return (container["span_id"], start, True, False)


def _call_placements(
    record: dict, node_spans: list[dict], run_id: str
) -> list[tuple[str, float, bool, bool]]:
    """For each call: parent span id, start offset, linked to a node, link inferred."""
    calls = record.get("calls") or []
    if not calls or any("node" in call for call in calls):
        return [_named_placement(call, node_spans, run_id) for call in calls]
    placements = []
    for link in infer_links(record.get("steps") or [], calls):
        if link is None:
            placements.append((run_id, 0.0, False, False))
            continue
        span = node_spans[link[0]]
        start = round(span["start_offset_seconds"] + link[1], 4)
        placements.append((span["span_id"], start, True, True))
    return placements


def build_trace(record: dict) -> dict:
    """A small, ordered span tree for one run; heavy content stays in the record."""
    trace_id = record["id"]
    steps = record.get("steps") or []
    run_id = _span_id(trace_id, "run")
    failed = record.get("status") == "failed" or record.get("error")
    run = {
        "span_id": run_id,
        "parent_id": None,
        "kind": "run",
        "name": "run",
        "status": "error" if failed else "ok",
        "start_offset_seconds": 0.0,
        "duration_seconds": record.get("duration_seconds", 0),
        "attributes": {},
        **({"error": record["error"]} if record.get("error") else {}),
    }
    question = str((record.get("task") or {}).get("question") or "")
    evidence = _evidence_texts(record)
    starts = _sequential_offsets(steps)
    node_spans, known_notes = [], 0
    for index, (step, start) in enumerate(zip(steps, starts, strict=True)):
        update = step.get("update") or {}
        attributes = _node_attributes(update, question, evidence, known_notes)
        known_notes = max(known_notes, len(update.get("research_notes") or []))
        node_spans.append(
            _node_span(
                _span_id(trace_id, "node", index), run_id, step, start, attributes
            )
        )
    calls = record.get("calls") or []
    placements = _call_placements(record, node_spans, run_id)
    call_spans = [
        _llm_span(trace_id, index, call, placement)
        for index, (call, placement) in enumerate(zip(calls, placements, strict=True))
    ]
    spans = [run, *node_spans, *call_spans]
    spans.sort(key=lambda span: (span["start_offset_seconds"], span["kind"] == "llm"))
    spans.sort(key=lambda span: span["kind"] != "run")
    return {"trace_id": trace_id, "spans": spans, "summary": _summary(record, spans)}


def span_payload(record: dict, span_id: str) -> dict | None:
    """The heavy content of one span (node update or model messages and output)."""
    trace_id = record["id"]
    for index, step in enumerate(record.get("steps") or []):
        if _span_id(trace_id, "node", index) == span_id:
            return {"update": step.get("update") or {}}
    for index, call in enumerate(record.get("calls") or []):
        if _span_id(trace_id, "llm", index) == span_id:
            return {
                "messages": call.get("messages"),
                "parameters": call.get("parameters"),
                "content": call.get("content"),
            }
    return None
