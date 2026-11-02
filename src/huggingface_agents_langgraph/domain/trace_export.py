"""Exports of a trace for people, scripts and OpenTelemetry-compatible tools."""

import csv
import hashlib
import io
import json
from datetime import datetime
from uuid import UUID

MAX_TEXT = 400
_GEN_AI_NAMES = {
    "model": "gen_ai.request.model",
    "max_tokens": "gen_ai.request.max_tokens",
    "temperature": "gen_ai.request.temperature",
    "prompt_tokens": "gen_ai.usage.input_tokens",
    "completion_tokens": "gen_ai.usage.output_tokens",
}
_BATTERY_COLUMNS = (
    "task_id",
    "route",
    "correct",
    "duration_seconds",
    "llm_calls",
    "completion_tokens",
    "truncated_calls",
    "slowest_stage",
    "error",
    "run_id",
)


def spans_jsonl(trace: dict) -> str:
    """One JSON object per line, each span carrying its trace id."""
    lines = [
        json.dumps({"trace_id": trace["trace_id"]} | span, ensure_ascii=False)
        for span in trace["spans"]
    ]
    return "\n".join(lines) + "\n"


def _trace_id(value: str) -> str:
    try:
        return UUID(value).hex
    except ValueError:
        return hashlib.sha256(value.encode()).hexdigest()[:32]


def _any_value(value: object) -> dict:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, list):
        return {"stringValue": ", ".join(map(str, value))}
    return {"stringValue": str(value)}


def _otlp_attributes(span: dict) -> list[dict]:
    names = {
        _GEN_AI_NAMES.get(key, f"gaia.{key}"): value
        for key, value in span["attributes"].items()
    }
    names["gaia.span.kind"] = span["kind"]
    return [{"key": key, "value": _any_value(value)} for key, value in names.items()]


def _start_nanoseconds(record: dict) -> int:
    created = record.get("created_at")
    return int(datetime.fromisoformat(created).timestamp() * 1e9) if created else 0


def _otlp_span(span: dict, trace_id: str, origin: int) -> dict:
    start = origin + round(span["start_offset_seconds"] * 1e9)
    end = start + round(span["duration_seconds"] * 1e9)
    status = {"code": 2 if span["status"] == "error" else 1}
    if span.get("error"):
        status["message"] = span["error"]
    converted = {
        "traceId": trace_id,
        "spanId": span["span_id"],
        "name": span["name"],
        "kind": 1,
        "startTimeUnixNano": str(start),
        "endTimeUnixNano": str(end),
        "attributes": _otlp_attributes(span),
        "status": status,
    }
    if span["parent_id"]:
        converted["parentSpanId"] = span["parent_id"]
    return converted


def otlp_json(trace: dict, record: dict) -> dict:
    """The trace as OTLP/JSON, ready for any OpenTelemetry-compatible backend."""
    trace_id = _trace_id(trace["trace_id"])
    origin = _start_nanoseconds(record)
    resource = {"attributes": [{"key": "service.name", "value": _any_value("gaia")}]}
    return {
        "resourceSpans": [
            {
                "resource": resource,
                "scopeSpans": [
                    {
                        "scope": {"name": "huggingface_agents_langgraph"},
                        "spans": [
                            _otlp_span(span, trace_id, origin)
                            for span in trace["spans"]
                        ],
                    }
                ],
            }
        ]
    }


def _clip(value: object) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "…"


def _node_table(trace: dict) -> list[str]:
    rows = [
        "| Nodo | Inicio (s) | Duración (s) | Estado | Qué hizo |",
        "|---|---|---|---|---|",
    ]
    for span in trace["spans"]:
        if span["kind"] == "node":
            attrs = span["attributes"]
            did = attrs.get("activity") or ", ".join(attrs.get("updated_fields", []))
            rows.append(
                f"| {span['name']} | {span['start_offset_seconds']} "
                f"| {span['duration_seconds']} | {span['status']} "
                f"| {did.replace('|', '/')} |"
            )
    return rows


def _call_table(trace: dict) -> list[str]:
    rows = [
        "| Nodo | Duración (s) | Tokens in/out | Fin | Estado |",
        "|---|---|---|---|---|",
    ]
    names = {span["span_id"]: span["name"] for span in trace["spans"]}
    for span in trace["spans"]:
        if span["kind"] != "llm":
            continue
        attrs = span["attributes"]
        tokens = (
            f"{attrs.get('prompt_tokens', '?')}/{attrs.get('completion_tokens', '?')}"
        )
        rows.append(
            f"| {names[span['parent_id']]} | {span['duration_seconds']} "
            f"| {tokens} "
            f"| {attrs.get('finish_reason', '?')} | {span['status']} |"
        )
    return rows


def _errors(trace: dict) -> list[str]:
    found = [
        f"- {span['kind']} `{span['name']}`: {_clip(span['error'])}"
        for span in trace["spans"]
        if span.get("error")
    ]
    return ["## Errores", *found, ""] if found else []


def _unsupported(trace: dict) -> list[str]:
    figures = trace["summary"].get("unsupported_figures") or []
    if not figures:
        return []
    return [
        "## Cifras sin respaldo en la evidencia",
        "Aparecen en una decisión o respuesta pero no en la pregunta ni en ninguna "
        "fuente recogida: " + ", ".join(figures),
        "",
    ]


def report_markdown(record: dict, trace: dict) -> str:
    """A short account of the run: what was asked, what happened and where it hurt."""
    summary = trace["summary"]
    result = record.get("result") or {}
    slowest = summary["slowest_node"]
    lines = [
        f"# Ejecución {record['id']}",
        "",
        f"- Pregunta: {_clip((record.get('task') or {}).get('question'))}",
        f"- Respuesta enviada: {_clip(result.get('submitted_answer'))}",
        f"- Estado: {summary['status']} en {summary['duration_seconds']} s",
        f"- Llamadas al modelo: {summary['llm_calls']} "
        f"({summary['prompt_tokens']} tokens de entrada, "
        f"{summary['completion_tokens']} de salida)",
        f"- Nodo más lento: {slowest['name']} ({slowest['duration_seconds']} s)"
        if slowest
        else "- Nodo más lento: —",
        "",
        *_errors(trace),
        *_unsupported(trace),
        "## Nodos",
        *_node_table(trace),
        "",
        "## Llamadas al modelo",
        *_call_table(trace),
        "",
    ]
    return "\n".join(lines)


def _slowest_stage(stages: dict) -> str | None:
    return max(stages, key=stages.get) if stages else None


def battery_rows(experiment: dict) -> list[dict]:
    """One row per task: route, outcome, cost and where the time went."""
    return [
        {
            "task_id": answer["task_id"],
            "route": answer.get("route"),
            "correct": answer.get("locally_correct"),
            "duration_seconds": answer.get("duration_seconds"),
            "llm_calls": answer.get("llm_calls"),
            "completion_tokens": answer.get("completion_tokens"),
            "truncated_calls": answer.get("truncated_calls"),
            "slowest_stage": _slowest_stage(answer.get("stage_seconds") or {}),
            "error": answer.get("error"),
            "run_id": answer.get("run_id"),
        }
        for answer in experiment.get("answers", [])
    ]


def _cell(value: object) -> object:
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else value


def battery_csv(experiment: dict) -> str:
    """The battery table as CSV, without answers or reference answers."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_BATTERY_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in battery_rows(experiment):
        writer.writerow({key: _cell(value) for key, value in row.items()})
    return buffer.getvalue()
