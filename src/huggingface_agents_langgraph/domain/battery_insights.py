"""Aggregates over a battery: where time goes, which routes fail and why."""

from collections import Counter, defaultdict
from statistics import mean

from huggingface_agents_langgraph.domain.trace_export import battery_rows


def _outcome(answer: dict) -> str:
    if answer.get("error"):
        return "error"
    correct = answer.get("locally_correct")
    if correct is None:
        return "unscored"
    return "correct" if correct else "wrong"


def _ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _totals(answers: list[dict]) -> dict:
    scored = [a for a in answers if a.get("locally_correct") is not None]
    correct = sum(bool(a["locally_correct"]) for a in scored)
    times = [a["duration_seconds"] for a in answers if a.get("duration_seconds")]
    return {
        "answered": len(answers),
        "scored": len(scored),
        "correct": correct,
        "accuracy": _ratio(correct, len(scored)),
        "mean_seconds": round(mean(times), 3) if times else None,
        "completion_tokens": sum(a.get("completion_tokens") or 0 for a in answers),
        "technical_errors": sum(bool(a.get("error")) for a in answers),
    }


def _routes(answers: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for answer in answers:
        groups[answer.get("route") or "unknown"].append(answer)
    routes = []
    for route, items in groups.items():
        scored = [a for a in items if a.get("locally_correct") is not None]
        correct = sum(bool(a["locally_correct"]) for a in scored)
        times = [a["duration_seconds"] for a in items if a.get("duration_seconds")]
        routes.append(
            {
                "route": route,
                "count": len(items),
                "scored": len(scored),
                "correct": correct,
                "accuracy": _ratio(correct, len(scored)),
                "mean_seconds": round(mean(times), 3) if times else None,
            }
        )
    return sorted(routes, key=lambda item: -item["count"])


def _stages(answers: list[dict]) -> list[dict]:
    totals, tasks = Counter(), Counter()
    for answer in answers:
        for stage, seconds in (answer.get("stage_seconds") or {}).items():
            totals[stage] += seconds
            tasks[stage] += 1
    overall = sum(totals.values())
    return [
        {
            "stage": stage,
            "total_seconds": round(seconds, 4),
            "mean_seconds": round(seconds / tasks[stage], 4),
            "tasks": tasks[stage],
            "share": round(seconds / overall, 4) if overall else 0.0,
        }
        for stage, seconds in totals.most_common()
    ]


def _failures(answers: list[dict]) -> dict:
    messages = Counter(a["error"] for a in answers if a.get("error"))
    return {
        "wrong_answers": sum(_outcome(a) == "wrong" for a in answers),
        "errors": [
            {"message": message, "count": count}
            for message, count in messages.most_common()
        ],
        "truncated_calls": sum(a.get("truncated_calls") or 0 for a in answers),
    }


def battery_insights(experiment: dict) -> dict:
    """Totals, routes, stages, failures and per-task outcomes of one battery."""
    answers = experiment.get("answers", [])
    rows = {row["task_id"]: row for row in battery_rows(experiment)}
    slowest = sorted(
        (a for a in answers if a.get("duration_seconds")),
        key=lambda a: -a["duration_seconds"],
    )[:3]
    return {
        "totals": _totals(answers),
        "routes": _routes(answers),
        "stages": _stages(answers),
        "failures": _failures(answers),
        "tasks": [{"task_id": a["task_id"], "outcome": _outcome(a)} for a in answers],
        "slowest_tasks": [
            {
                "task_id": a["task_id"],
                "duration_seconds": a["duration_seconds"],
                "slowest_stage": rows[a["task_id"]]["slowest_stage"],
            }
            for a in slowest
        ],
    }
