"""Characterization of the spreadsheet plans: what they compute and what they refuse."""

import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from huggingface_agents_langgraph.domain.experiments import normalize_experiment
from huggingface_agents_langgraph.pipeline import (
    spreadsheet_processing,
    spreadsheet_tools,
)

SHEETS = {
    "Sales": [
        ["Item", "Category", "Sales", "Units"],
        ["Burger", "Food", 10.5, 2],
        ["Soda", "Drink", 2, 4],
        ["Fries", "Food", 4, None],
        ["Salad", "Food", "n/a", 1],
    ]
}


def _plan(**changes):
    plan = {"sheet": "Sales", "operation": "sum", "column": "Units", "filters": []}
    return plan | changes


def _filter(column="Category", operator="equals", value="Food"):
    return {"column": column, "operator": operator, "value": value}


@pytest.mark.parametrize(
    ("plan", "expected"),
    [
        (_plan(operation="count"), "Count: 4"),
        (_plan(operation="count", filters=[_filter()]), "Count: 3"),
        (_plan(), "Sum of Units: 7"),
        (_plan(operation="average"), "Average of Units: 2.333333333333333333333333333"),
        (_plan(operation="min"), "Min of Units: 1"),
        (_plan(operation="max"), "Max of Units: 4"),
        (_plan(filters=[_filter(value="food")]), "Sum of Units: 3"),
        (_plan(filters=[_filter(operator="not_equals")]), "Sum of Units: 4"),
        (_plan(filters=[_filter(operator="contains", value="oo")]), "Sum of Units: 3"),
        (
            _plan(
                operation="count",
                filters=[_filter("Sales", "greater_than", 3)],
            ),
            "Count: 2",
        ),
        (
            _plan(
                operation="count",
                filters=[_filter("Sales", "greater_or_equal", 4)],
            ),
            "Count: 2",
        ),
        (
            _plan(operation="count", filters=[_filter("Sales", "less_than", 4)]),
            "Count: 1",
        ),
        (
            _plan(
                operation="count",
                filters=[_filter("Sales", "less_or_equal", 4)],
            ),
            "Count: 2",
        ),
    ],
)
def test_supported_plans_compute(plan, expected):
    assert spreadsheet_processing._compute_plan(SHEETS, plan) == expected


@pytest.mark.parametrize(
    "plan",
    [
        _plan(sheet="Missing"),
        _plan(operation="median"),
        _plan(filters="x"),
        _plan(column=None),
        _plan(column="Nope"),
        _plan(filters=["x"]),
        _plan(filters=[_filter(column="Nope")]),
        _plan(filters=[_filter(operator="matches")]),
        _plan(filters=[{"column": "Category", "operator": "equals"}]),
        _plan(column="Sales"),
        _plan(filters=[_filter("Item", "equals", "Nothing")]),
    ],
)
def test_unsupported_plans_return_nothing(plan):
    assert spreadsheet_processing._compute_plan(SHEETS, plan) is None


def test_a_sheet_without_unique_headers_or_rows_is_refused():
    duplicate = {"S": [["a", "a"], [1, 2]]}
    header_only = {"S": [["a", "b"]]}
    plan = {"sheet": "S", "operation": "count"}
    assert spreadsheet_processing._compute_plan(duplicate, plan) is None
    assert spreadsheet_processing._compute_plan(header_only, plan) is None


def _workbook(tmp_path: Path, rows) -> Path:
    path = tmp_path / "book.xlsx"
    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    workbook.save(path)
    return path


def _state(path, **extra):
    return {"question": "Total?", "file_path": path, "file_name": "b.xlsx", **extra}


def test_a_missing_or_empty_attachment_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="file_path"):
        spreadsheet_processing.spreadsheet_processing({"question": "q"})
    with pytest.raises(FileNotFoundError):
        spreadsheet_processing.spreadsheet_processing(_state(tmp_path / "no.xlsx"))
    empty = tmp_path / "empty.xlsx"
    Workbook().save(empty)
    with pytest.raises(ValueError, match="no non-empty"):
        spreadsheet_processing.spreadsheet_processing(_state(empty))


def test_an_unparsable_plan_falls_back_to_analysis(monkeypatch, tmp_path):
    path = _workbook(tmp_path, [["a", "b"], [1, 2]])
    replies = iter(["not json", "analysis"])
    monkeypatch.setattr(
        spreadsheet_processing, "chat_completion", lambda *_a, **_k: next(replies)
    )
    evidence = spreadsheet_processing.spreadsheet_processing(_state(path))["evidence"]
    assert [item["source_type"] for item in evidence] == [
        "spreadsheet_analysis",
        "spreadsheet_data",
    ]


def test_a_plan_that_cannot_run_falls_back_to_analysis(monkeypatch, tmp_path):
    path = _workbook(tmp_path, [["a", "b"], [1, 2]])
    plan = json.dumps({"strategy": "compute", "sheet": "Nope", "operation": "sum"})
    replies = iter([plan, "analysis"])
    monkeypatch.setattr(
        spreadsheet_processing, "chat_completion", lambda *_a, **_k: next(replies)
    )
    evidence = spreadsheet_processing.spreadsheet_processing(_state(path))["evidence"]
    assert evidence[0]["content"] == "analysis"


def _tools_state(path):
    experiment = normalize_experiment(
        {"pipeline_version": "3.1", "improvements": ["spreadsheet_tools"]}
    )
    return _state(path, experiment=experiment)


def test_the_tools_plan_adds_its_calculation_first(monkeypatch, tmp_path):
    path = _workbook(tmp_path, [["a", "b"], [1, 2]])
    calculation = {"plan": {}, "result": {"value": "3"}}
    monkeypatch.setattr(spreadsheet_tools, "plan_aggregation", lambda *_a: calculation)
    evidence = spreadsheet_processing.spreadsheet_processing(_tools_state(path))[
        "evidence"
    ]
    assert json.loads(evidence[0]["content"]) == calculation
    assert evidence[0]["source_type"] == "spreadsheet_calculation"
    assert evidence[-1]["source_type"] == "spreadsheet_data"


def test_a_rejected_tools_plan_is_reported_after_the_analysis(monkeypatch, tmp_path):
    path = _workbook(tmp_path, [["a", "b"], [1, 2]])

    def rejected(*_args):
        raise ValueError("Unsupported spreadsheet plan")

    monkeypatch.setattr(spreadsheet_tools, "plan_aggregation", rejected)
    monkeypatch.setattr(
        spreadsheet_processing, "chat_completion", lambda *_a, **_k: "analysis"
    )
    evidence = spreadsheet_processing.spreadsheet_processing(_tools_state(path))[
        "evidence"
    ]
    assert [item["source_type"] for item in evidence] == [
        "spreadsheet_analysis",
        "spreadsheet_diagnostic",
        "spreadsheet_data",
    ]
    assert evidence[1]["content"] == (
        "Deterministic plan rejected: Unsupported spreadsheet plan"
    )


TABLE = [
    ["Item", "Cat", "A", "B"],
    ["x", "F", 1, 2],
    ["y", "D", 3, None],
    ["z", "F", 5, 6],
]


def _table_plan(**changes):
    plan = {"sheet": "S", "operation": "sum", "columns": ["A", "B"], "filters": []}
    return plan | changes


def _span_filter(value="F", operator="equals"):
    return {
        "column": "Cat",
        "operator": operator,
        "value": value,
        "question_span": f"Cat is {value}",
    }


def test_aggregate_table_reports_rows_and_values():
    result = spreadsheet_tools.aggregate_table(
        {"S": TABLE}, _table_plan(filters=[_span_filter()]), "when Cat is F"
    )
    assert result == {
        "sheet": "S",
        "operation": "sum",
        "columns": ["A", "B"],
        "included_rows": [2, 4],
        "excluded_rows": [3],
        "numeric_cells": 4,
        "value": "14",
    }


@pytest.mark.parametrize(
    ("operation", "value"),
    [("average", "3.5"), ("min", "1"), ("max", "6"), ("count", "2")],
)
def test_aggregate_table_operations(operation, value):
    plan = _table_plan(operation=operation, filters=[_span_filter()])
    result = spreadsheet_tools.aggregate_table({"S": TABLE}, plan, "Cat is F")
    assert result["value"] == value


def test_aggregate_table_count_ignores_cell_types():
    table = [["a"], ["text"], [True]]
    plan = {"sheet": "S", "operation": "count", "columns": ["a"], "filters": []}
    result = spreadsheet_tools.aggregate_table({"S": table}, plan, "q")
    assert result["value"] == "2"
    assert result["numeric_cells"] == 0


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"sheet": "Nope"}, "Unsupported"),
        ({"columns": []}, "Unsupported"),
        ({"columns": ["A", "A"]}, "Unsupported"),
        ({"columns": [1]}, "Unsupported"),
        ({"operation": "median"}, "Unsupported"),
        ({"filters": "x"}, "Unsupported"),
        ({"columns": ["Nope"]}, "unique source headers"),
        ({"filters": ["x"]}, "must cite"),
        ({"filters": [_span_filter(operator="greater_than")]}, "must cite"),
        ({"filters": [_span_filter()]}, "must cite"),
    ],
)
def test_aggregate_table_refuses_invalid_plans(changes, message):
    with pytest.raises(ValueError, match=message):
        spreadsheet_tools.aggregate_table({"S": TABLE}, _table_plan(**changes), "q")


@pytest.mark.parametrize(
    ("cell", "message"),
    [(True, "Boolean"), ("abc", "not numeric"), (float("inf"), "finite")],
)
def test_aggregate_table_refuses_bad_cells(cell, message):
    table = [["A"], [cell]]
    plan = {"sheet": "S", "operation": "sum", "columns": ["A"], "filters": []}
    with pytest.raises(ValueError, match=message):
        spreadsheet_tools.aggregate_table({"S": table}, plan, "q")


def test_aggregate_table_needs_numeric_values_unless_counting():
    table = [["A"], [None]]
    plan = {"sheet": "S", "operation": "sum", "columns": ["A"], "filters": []}
    with pytest.raises(ValueError, match="no numeric"):
        spreadsheet_tools.aggregate_table({"S": table}, plan, "q")


def test_plan_aggregation_accepts_only_compute_plans(monkeypatch):
    from huggingface_agents_langgraph.adapters import llm

    plan = {
        "strategy": "compute",
        "sheet": "S",
        "operation": "count",
        "columns": ["A"],
        "filters": [],
    }
    replies = iter([json.dumps(plan), '{"strategy":"analyze"}'])
    monkeypatch.setattr(llm, "chat_completion", lambda *_a, **_k: next(replies))
    result = spreadsheet_tools.plan_aggregation("q", {"S": [["A"], [1]]}, None)
    assert result["result"]["value"] == "1"
    with pytest.raises(ValueError, match="general spreadsheet analysis"):
        spreadsheet_tools.plan_aggregation("q", {"S": [["A"], [1]]}, None)
