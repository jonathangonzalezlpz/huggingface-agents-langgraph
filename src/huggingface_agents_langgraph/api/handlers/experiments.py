"""Stored experiments: list, save, compare, delete and score locally."""

from huggingface_agents_langgraph.adapters.records import (
    delete_record,
    list_records,
    read_record,
    write_record,
)
from huggingface_agents_langgraph.api.http import Request, Response, failure, ok
from huggingface_agents_langgraph.api.router import Router
from huggingface_agents_langgraph.application.experiment_scoring import (
    evaluate_experiment,
)
from huggingface_agents_langgraph.domain.experiment_comparison import (
    compare_experiments,
)
from huggingface_agents_langgraph.domain.pipeline_versions import (
    experiment_presentation,
)

MAX_COMPARED_EXPERIMENTS = 20
MAX_STORED_ANSWERS = 20


def list_all(request: Request) -> Response:
    records = [
        experiment_presentation(record) for record in list_records("experiments")
    ]
    return ok({"experiments": records})


def save(request: Request) -> Response:
    try:
        record = request.json_value()
        answers = record.get("answers") if isinstance(record, dict) else None
        if not isinstance(answers, list) or len(answers) > MAX_STORED_ANSWERS:
            raise ValueError("Invalid experiment record")
        write_record("experiments", record)
    except (ValueError, KeyError, TypeError) as error:
        return failure(400, str(error))
    return ok({"saved": True})


def delete(request: Request) -> Response:
    """Remove one persisted experiment without deleting other runs."""
    try:
        delete_record("experiments", request.params["id"])
    except ValueError as error:
        return failure(400, str(error))
    return ok({"deleted": True})


def _comparison_request(request: Request) -> tuple[list[str], str | None]:
    payload = request.json_object()
    ids, base = payload.get("ids"), payload.get("base")
    if (
        not isinstance(ids, list)
        or not 2 <= len(ids) <= MAX_COMPARED_EXPERIMENTS
        or not all(isinstance(item, str) for item in ids)
        or len(set(ids)) != len(ids)
    ):
        raise ValueError("ids must list 2 to 20 distinct experiment ids")
    if base is not None and not isinstance(base, str):
        raise ValueError("base must be an experiment id")
    return ids, base


def compare(request: Request) -> Response:
    try:
        ids, base = _comparison_request(request)
        records = []
        for experiment_id in ids:
            try:
                record = read_record("experiments", experiment_id)
            except FileNotFoundError:
                return failure(404, f"Experiment not found: {experiment_id}")
            records.append(experiment_presentation(record))
        return ok(compare_experiments(records, base_id=base))
    except (ValueError, TypeError, KeyError) as error:
        return failure(400, str(error))


def evaluate(request: Request) -> Response:
    """Score a stored, complete experiment against GAIA validation."""
    try:
        return ok(evaluate_experiment(request.params["id"]))
    except FileNotFoundError:
        return failure(404, "Experiment not found")
    except ValueError as error:
        return failure(400, str(error))
    except RuntimeError as error:
        return failure(503, str(error))


def register(router: Router) -> None:
    router.add("GET", "/api/experiments")(list_all)
    router.add("POST", "/api/experiments")(save)
    router.add("POST", "/api/experiments/compare")(compare)
    router.add("POST", "/api/experiments/{id}/evaluate")(evaluate)
    router.add("DELETE", "/api/experiments/{id}")(delete)
