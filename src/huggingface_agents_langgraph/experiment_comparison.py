"""Structured comparison of persisted experiments.

Experiments with the same configuration, code and task set are treated as
repetitions of one setup, so differences between setups can be judged against
the variation observed between repetitions. Reference answers are never read;
only the stored correctness flags are used.
"""

import hashlib
import json
from collections.abc import Sequence
from statistics import mean
from typing import Any

from huggingface_agents_langgraph.experiment_runner import timing_summary

IGNORED_CONFIG_FIELDS = {"name"}
MIN_EXPERIMENTS = 2


def _task_ids(record: dict) -> frozenset[str]:
    return frozenset(answer["task_id"] for answer in record.get("answers", []))


def _source_hash(record: dict) -> str | None:
    return (record.get("source_identity") or {}).get("source_sha256")


def _setup_key(record: dict) -> str:
    config = {
        key: value
        for key, value in record.get("config", {}).items()
        if key not in IGNORED_CONFIG_FIELDS
    }
    payload = {
        "config": config,
        "source": _source_hash(record),
        "tasks": sorted(_task_ids(record)),
        "task_set": record.get("task_set_sha256"),
    }
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _score(record: dict) -> tuple[int | None, int | None]:
    flags = [
        answer["locally_correct"]
        for answer in record.get("answers", [])
        if isinstance(answer.get("locally_correct"), bool)
    ]
    if flags:
        return sum(flags), len(flags)
    stored = record.get("local_score")
    if stored and stored.get("total_attempted"):
        return stored["correct_count"], stored["total_attempted"]
    return None, None


def _experiment_summary(record: dict, group_key: str) -> dict:
    answers = record.get("answers", [])
    correct, scored = _score(record)
    timing = timing_summary(answers)
    return {
        "id": record["id"],
        "name": record.get("display_name") or record.get("config", {}).get("name"),
        "created_at": record.get("created_at"),
        "status": record.get("status"),
        "group": group_key,
        "metrics": {
            "answered": len(answers),
            "correct": correct,
            "accuracy": round(correct / scored, 4) if scored else None,
            "mean_seconds": timing["mean_seconds"],
            "median_seconds": timing["median_seconds"],
            "p95_seconds": timing["p95_seconds"],
            "technical_errors": timing["technical_errors"],
            "truncated_calls": sum(
                answer.get("truncated_calls") or 0 for answer in answers
            ),
        },
    }


def _is_partial(record: dict) -> bool:
    expected = record.get("total_questions")
    return record.get("status", "completed") != "completed" or (
        expected is not None and len(record.get("answers", [])) < expected
    )


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _config_differences(records: Sequence[dict]) -> dict[str, dict[str, Any]]:
    keys = {
        key
        for record in records
        for key in record.get("config", {})
        if key not in IGNORED_CONFIG_FIELDS
    }
    differences = {}
    for key in sorted(keys):
        values = {r["id"]: r.get("config", {}).get(key) for r in records}
        if len({_canonical(value) for value in values.values()}) > 1:
            differences[key] = values
    return differences


def _comparability(records: Sequence[dict], groups: list[dict]) -> dict:
    same_tasks = len({_task_ids(r) for r in records}) == 1
    hashes = [r.get("task_set_sha256") for r in records]
    if all(hashes):
        same_tasks = same_tasks and len(set(hashes)) == 1
    sources = [_source_hash(r) for r in records]
    same_code = None if None in sources else len(set(sources)) == 1
    architectures = {r.get("config", {}).get("architecture") for r in records}
    warnings = []
    if not same_tasks:
        warnings.append("The experiments do not share the same task set.")
    if same_code is False:
        warnings.append("The experiments were run with different code.")
    elif same_code is None:
        warnings.append("Code identity is unknown for some experiments.")
    if any(_is_partial(r) for r in records):
        warnings.append("Some experiments are partial (cancelled or incomplete).")
    if any(group["runs"] == 1 for group in groups):
        warnings.append(
            "Some groups have a single run: no noise estimate is available."
        )
    return {
        "same_task_set": same_tasks,
        "same_code": same_code,
        "same_architecture": len(architectures) == 1,
        "config_differences": _config_differences(records),
        "warnings": warnings,
    }


def _range(values: list[float]) -> dict | None:
    if not values:
        return None
    return {
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(mean(values), 4),
    }


def _group_summaries(records: Sequence[dict], summaries: dict[str, dict]) -> list[dict]:
    members: dict[str, list[dict]] = {}
    for record in records:
        members.setdefault(summaries[record["id"]]["group"], []).append(record)
    groups = []
    for key, items in members.items():
        metrics = [summaries[r["id"]]["metrics"] for r in items]
        accuracy = [m["accuracy"] for m in metrics if m["accuracy"] is not None]
        seconds = [m["mean_seconds"] for m in metrics if m["mean_seconds"] is not None]
        groups.append(
            {
                "key": key,
                "experiment_ids": [r["id"] for r in items],
                "runs": len(items),
                "accuracy": _range(accuracy),
                "mean_seconds": _range(seconds),
                "noise_estimate": "observed_range" if len(items) > 1 else "none",
                "versus_base": None,
            }
        )
    return groups


def _answer(record: dict, task_id: str) -> dict:
    return next((a for a in record.get("answers", []) if a["task_id"] == task_id), {})


def _correct_rate(records: Sequence[dict], task_id: str) -> float | None:
    flags = [_answer(record, task_id).get("locally_correct") for record in records]
    scored = [flag for flag in flags if isinstance(flag, bool)]
    return sum(scored) / len(scored) if scored else None


def _group_change(candidate: float | None, base: float | None) -> str:
    """Compare the correctness rates of two groups on one task."""
    if candidate is None or base is None:
        return "unknown"
    if candidate > base:
        return "gained"
    return "lost" if candidate < base else "unchanged"


def _run_change(correct: bool | None, base_rate: float | None) -> str:
    """Compare one run with the majority outcome of the base group."""
    if correct is None or base_rate is None:
        return "unknown"
    if correct and base_rate < 0.5:
        return "gained"
    if not correct and base_rate > 0.5:
        return "lost"
    return "unchanged"


def _assess(candidate: dict, base: dict) -> dict:
    if not candidate["accuracy"] or not base["accuracy"]:
        return {"delta": None, "assessment": "not_assessable"}
    delta = round(candidate["accuracy"]["mean"] - base["accuracy"]["mean"], 4)
    if candidate["runs"] < 2 or base["runs"] < 2:
        return {"delta": delta, "assessment": "not_assessable"}
    overlap = (
        candidate["accuracy"]["min"] <= base["accuracy"]["max"]
        and candidate["accuracy"]["max"] >= base["accuracy"]["min"]
    )
    return {
        "delta": delta,
        "assessment": "within_observed_range" if overlap else "outside_observed_range",
    }


def _task_alignment(
    records: Sequence[dict], base_group: dict, by_id: dict[str, dict]
) -> list[dict]:
    common = frozenset.intersection(*(_task_ids(r) for r in records))
    order = [
        a["task_id"] for a in records[0].get("answers", []) if a["task_id"] in common
    ]
    base_records = [by_id[i] for i in base_group["experiment_ids"]]
    tasks = []
    for task_id in dict.fromkeys(order):
        base_rate = _correct_rate(base_records, task_id)
        reference = _answer(base_records[0], task_id)
        outcomes = {}
        for record in records:
            answer = _answer(record, task_id)
            flag = answer.get("locally_correct")
            correct = flag if isinstance(flag, bool) else None
            outcome: dict[str, Any] = {
                "correct": correct,
                "route": answer.get("route"),
                "seconds": answer.get("duration_seconds"),
                "error": bool(answer.get("error")),
                "versus_base": None,
                "same_answer_as_base": None,
            }
            if record["id"] not in base_group["experiment_ids"]:
                outcome["versus_base"] = _run_change(correct, base_rate)
                outcome["same_answer_as_base"] = answer.get(
                    "submitted_answer"
                ) == reference.get("submitted_answer")
            outcomes[record["id"]] = outcome
        tasks.append({"task_id": task_id, "outcomes": outcomes})
    return tasks


def _versus_base(
    group: dict, base_group: dict, by_id: dict[str, dict], common_tasks: list[str]
) -> dict:
    counts = {"gained": 0, "lost": 0, "unchanged": 0, "unknown": 0}
    group_records = [by_id[i] for i in group["experiment_ids"]]
    base_records = [by_id[i] for i in base_group["experiment_ids"]]
    for task_id in common_tasks:
        change = _group_change(
            _correct_rate(group_records, task_id),
            _correct_rate(base_records, task_id),
        )
        counts[change] += 1
    seconds, base_seconds = group["mean_seconds"], base_group["mean_seconds"]
    return {
        **counts,
        "accuracy_difference": _assess(group, base_group),
        "mean_seconds_delta": (
            round(seconds["mean"] - base_seconds["mean"], 3)
            if seconds and base_seconds
            else None
        ),
    }


def compare_experiments(records: Sequence[dict], base_id: str | None = None) -> dict:
    """Compare two or more persisted experiments, grouping repetitions."""
    if len(records) < MIN_EXPERIMENTS:
        raise ValueError("at least two experiments are required")
    by_id = {record["id"]: record for record in records}
    if base_id is not None and base_id not in by_id:
        raise ValueError(f"base experiment '{base_id}' is not among those compared")
    summaries = {
        record["id"]: _experiment_summary(record, _setup_key(record))
        for record in records
    }
    groups = _group_summaries(records, summaries)
    reference_id = base_id or records[0]["id"]
    base_group = next(g for g in groups if reference_id in g["experiment_ids"])
    tasks = _task_alignment(records, base_group, by_id)
    common_tasks = [task["task_id"] for task in tasks]
    for group in groups:
        if group is not base_group:
            group["versus_base"] = _versus_base(group, base_group, by_id, common_tasks)
    return {
        "base_group": base_group["key"],
        "experiments": [summaries[record["id"]] for record in records],
        "groups": groups,
        "comparability": _comparability(records, groups),
        "tasks": tasks,
    }
