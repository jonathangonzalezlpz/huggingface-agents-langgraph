"""Read-only views of a run's trace: structured, exported and on demand."""

from huggingface_agents_langgraph.adapters.records import read_record
from huggingface_agents_langgraph.api.http import (
    BytesResponse,
    Request,
    Response,
    failure,
    ok,
)
from huggingface_agents_langgraph.api.router import Router
from huggingface_agents_langgraph.domain.battery_insights import battery_insights
from huggingface_agents_langgraph.domain.trace_export import (
    battery_csv,
    otlp_json,
    report_markdown,
    spans_jsonl,
)
from huggingface_agents_langgraph.domain.trace_spans import build_trace, span_payload


def _text(body: str, content_type: str) -> BytesResponse:
    return BytesResponse(200, body.encode("utf-8"), f"{content_type}; charset=utf-8")


def _run(request: Request) -> dict | None:
    try:
        return read_record("runs", request.params["id"])
    except (ValueError, FileNotFoundError):
        return None


def trace(request: Request) -> Response:
    record = _run(request)
    return ok(build_trace(record)) if record else failure(404, "Run not found")


def trace_jsonl(request: Request) -> Response:
    record = _run(request)
    if not record:
        return failure(404, "Run not found")
    return _text(spans_jsonl(build_trace(record)), "application/x-ndjson")


def trace_otlp(request: Request) -> Response:
    record = _run(request)
    if not record:
        return failure(404, "Run not found")
    return ok(otlp_json(build_trace(record), record))


def report(request: Request) -> Response:
    record = _run(request)
    if not record:
        return failure(404, "Run not found")
    return _text(report_markdown(record, build_trace(record)), "text/markdown")


def span(request: Request) -> Response:
    record = _run(request)
    payload = span_payload(record, request.params["span"]) if record else None
    return ok(payload) if payload is not None else failure(404, "Span not found")


def _experiment(request: Request) -> dict | None:
    try:
        return read_record("experiments", request.params["id"])
    except (ValueError, FileNotFoundError):
        return None


def battery_table(request: Request) -> Response:
    experiment = _experiment(request)
    if not experiment:
        return failure(404, "Experiment not found")
    return _text(battery_csv(experiment), "text/csv")


def insights(request: Request) -> Response:
    experiment = _experiment(request)
    if not experiment:
        return failure(404, "Experiment not found")
    return ok(battery_insights(experiment))


def register(router: Router) -> None:
    router.add("GET", "/api/runs/{id}/trace")(trace)
    router.add("GET", "/api/runs/{id}/trace.jsonl")(trace_jsonl)
    router.add("GET", "/api/runs/{id}/trace.otlp.json")(trace_otlp)
    router.add("GET", "/api/runs/{id}/report.md")(report)
    router.add("GET", "/api/runs/{id}/spans/{span}")(span)
    router.add("GET", "/api/experiments/{id}/trace.csv")(battery_table)
    router.add("GET", "/api/experiments/{id}/insights")(insights)
