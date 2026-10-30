"""Deterministic, auditable multi-column spreadsheet aggregation."""

import json
from decimal import Decimal, InvalidOperation


def aggregate_table(sheets: dict, plan: dict, question: str) -> dict:
    """Execute a validated plan without copying or changing source cell values."""
    rows = sheets.get(plan.get("sheet"))
    columns = plan.get("columns")
    operation = plan.get("operation")
    filters = plan.get("filters", [])
    if (
        not rows
        or len(rows) < 2
        or not isinstance(columns, list)
        or not columns
        or any(not isinstance(column, str) for column in columns)
        or len(set(columns)) != len(columns)
        or operation not in {"sum", "average", "min", "max", "count"}
        or not isinstance(filters, list)
    ):
        raise ValueError("Unsupported spreadsheet plan")
    headers = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    if len(set(headers)) != len(headers) or any(
        column not in headers for column in columns
    ):
        raise ValueError("Selected columns must identify unique source headers")
    indexes = [headers.index(column) for column in columns]
    for condition in filters:
        if (
            not isinstance(condition, dict)
            or condition.get("column") not in headers
            or condition.get("operator") not in {"equals", "not_equals"}
            or "value" not in condition
            or not isinstance(condition.get("question_span"), str)
            or not condition["question_span"].strip()
            or condition["question_span"].casefold() not in question.casefold()
            or str(condition["value"]).casefold()
            not in condition["question_span"].casefold()
        ):
            raise ValueError("Each row filter must cite its condition in the question")
    used = []
    excluded = []
    values = []
    for row_number, row in enumerate(rows[1:], 2):
        selected = True
        for condition in filters:
            index = headers.index(condition["column"])
            cell = row[index] if index < len(row) else None
            equal = str(cell).casefold() == str(condition["value"]).casefold()
            selected &= equal if condition["operator"] == "equals" else not equal
        if not selected:
            excluded.append(row_number)
            continue
        used.append(row_number)
        if operation == "count":
            continue
        for index in indexes:
            cell = row[index] if index < len(row) else None
            if cell is None:
                continue
            if isinstance(cell, bool):
                raise ValueError("Boolean values cannot be aggregated as sales")
            try:
                value = Decimal(str(cell))
            except InvalidOperation as error:
                raise ValueError("A selected cell is not numeric") from error
            if not value.is_finite():
                raise ValueError("Selected values must be finite")
            values.append(value)
    if not values and operation != "count":
        raise ValueError("The selection contains no numeric values")
    result = {
        "sum": lambda: sum(values, Decimal(0)),
        "average": lambda: sum(values, Decimal(0)) / len(values),
        "min": lambda: min(values),
        "max": lambda: max(values),
        "count": lambda: len(used),
    }[operation]()
    return {
        "sheet": plan["sheet"],
        "operation": operation,
        "columns": columns,
        "included_rows": used,
        "excluded_rows": excluded,
        "numeric_cells": len(values),
        "value": str(result),
    }


def plan_aggregation(question: str, sheets: dict, model: dict | None) -> dict:
    """Ask the LLM to identify data and scope, then compute on original cells."""
    from huggingface_agents_langgraph.llm import chat_completion

    response = chat_completion(
        [
            {
                "role": "system",
                "content": "Plan an exact spreadsheet aggregation. Return JSON with "
                "strategy compute or analyze. For compute provide sheet, operation "
                "(sum, average, min, max, count), "
                "columns (ALL relevant exact headers), "
                "filters (list). Each row filter requires column, operator "
                "equals/not_equals, value, question_span "
                "quoting the original condition INCLUDING the value. Never invent "
                "geographical or other exclusions. Distinguish selecting columns from "
                "filtering rows. Account for every requested category and unit. If the "
                "operation cannot represent the task faithfully, "
                "use analyze. /no_think",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"question": question, "sheets": sheets},
                    ensure_ascii=False,
                    default=str,
                ),
            },
        ],
        max_tokens=768,
        model=model,
    )
    plan = json.loads(response)
    if not isinstance(plan, dict) or plan.get("strategy") != "compute":
        raise ValueError("This task needs general spreadsheet analysis")
    return {"plan": plan, "result": aggregate_table(sheets, plan, question)}
