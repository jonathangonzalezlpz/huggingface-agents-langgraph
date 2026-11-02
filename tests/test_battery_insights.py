"""Aggregates over a battery: where time goes, which routes fail, why runs break."""

from huggingface_agents_langgraph.domain.battery_insights import battery_insights


def _answer(task_id, route, correct, duration, stages, **extra):
    return {
        "task_id": task_id,
        "route": route,
        "locally_correct": correct,
        "duration_seconds": duration,
        "stage_seconds": stages,
        "llm_calls": 2,
        "completion_tokens": 10,
        "truncated_calls": 0,
        "submitted_answer": "a",
        **extra,
    }


def _experiment():
    return {
        "id": "e1",
        "answers": [
            _answer("t1", "web", True, 10.0, {"router": 1.0, "review": 6.0}),
            _answer("t2", "web", False, 30.0, {"router": 1.0, "review": 20.0}),
            _answer("t3", "code", True, 5.0, {"router": 1.0, "code": 2.0}),
            _answer(
                "t4",
                "error",
                False,
                20.0,
                {"review": 19.0},
                error="LLM output was truncated by the token limit",
                truncated_calls=1,
                submitted_answer="",
            ),
            _answer("t5", "web", None, 5.0, {"review": 3.0}),
        ],
    }


def test_totals_count_only_scored_answers_for_accuracy():
    totals = battery_insights(_experiment())["totals"]

    assert totals["answered"] == 5
    assert totals["scored"] == 4 and totals["correct"] == 2
    assert totals["accuracy"] == 0.5
    assert totals["mean_seconds"] == 14.0
    assert totals["completion_tokens"] == 50
    assert totals["technical_errors"] == 1


def test_routes_report_accuracy_and_mean_time():
    routes = {item["route"]: item for item in battery_insights(_experiment())["routes"]}

    assert routes["web"]["count"] == 3 and routes["web"]["scored"] == 2
    assert routes["web"]["correct"] == 1 and routes["web"]["accuracy"] == 0.5
    assert routes["code"]["accuracy"] == 1.0
    assert routes["error"]["accuracy"] == 0.0


def test_stages_are_ordered_by_total_time_with_their_share():
    stages = battery_insights(_experiment())["stages"]

    assert [item["stage"] for item in stages][:2] == ["review", "router"]
    review = stages[0]
    assert review["total_seconds"] == 48.0 and review["tasks"] == 4
    assert round(sum(item["share"] for item in stages), 4) == 1.0


def test_failures_group_errors_wrong_answers_and_truncations():
    failures = battery_insights(_experiment())["failures"]

    assert failures["wrong_answers"] == 1
    assert failures["errors"] == [
        {"message": "LLM output was truncated by the token limit", "count": 1}
    ]
    assert failures["truncated_calls"] == 1


def test_outcomes_classify_every_task_and_slowest_are_listed():
    insights = battery_insights(_experiment())

    outcomes = {item["task_id"]: item["outcome"] for item in insights["tasks"]}
    assert outcomes == {
        "t1": "correct",
        "t2": "wrong",
        "t3": "correct",
        "t4": "error",
        "t5": "unscored",
    }
    assert insights["slowest_tasks"][0] == {
        "task_id": "t2",
        "duration_seconds": 30.0,
        "slowest_stage": "review",
    }


def test_an_empty_battery_does_not_divide_by_zero():
    insights = battery_insights({"id": "e", "answers": []})

    assert insights["totals"]["accuracy"] is None
    assert insights["stages"] == [] and insights["routes"] == []
