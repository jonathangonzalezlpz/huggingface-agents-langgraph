"""Spreadsheet processing node for tasks with Excel attachments."""

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TypedDict

from openpyxl import load_workbook

from huggingface_agents_langgraph.adapters.llm import ChatMessage, chat_completion
from huggingface_agents_langgraph.domain.experiments import (
    DEFAULT_EXPERIMENT,
    ModelSelection,
    improvement_enabled,
)
from huggingface_agents_langgraph.domain.state import AgentState, Evidence
from huggingface_agents_langgraph.pipeline.evidence_selection import (
    select_relevant_evidence,
)

OPERATIONS = {"sum", "count", "average", "min", "max"}
FILTER_OPERATORS = {
    "equals",
    "not_equals",
    "contains",
    "greater_than",
    "greater_or_equal",
    "less_than",
    "less_or_equal",
}
PLAN_INSTRUCTIONS = (
    "Decide whether the spreadsheet question can be expressed as one "
    "simple deterministic calculation. If so, return only a JSON "
    "object with strategy='compute', sheet, operation (sum, count, "
    "average, min, or max), column (header text, or null for count), "
    "and filters (a list of {column, operator, value}; operators are "
    "equals, not_equals, contains, greater_than, greater_or_equal, "
    "less_than, less_or_equal). Assume the first non-empty row is the "
    "header. If the task needs a more complex interpretation, "
    "comparison, ranking, multi-step calculation, or anything this "
    "simple plan cannot represent, return only "
    '{"strategy":"analyze"}. Never simplify a question to fit '
    "the calculation plan. /no_think"
)
ANALYSIS_INSTRUCTIONS = (
    "Answer the spreadsheet question using the workbook data. This "
    "fallback supports complex interpretation and calculations that "
    "do not fit a simple aggregation plan. Carefully show the relevant "
    "findings and calculation result, but do not invent missing data. "
    "If the workbook does not contain enough information, say so."
)


class SpreadsheetProcessingUpdate(TypedDict):
    """State fields produced by the spreadsheet processing node."""

    evidence: list[Evidence]


def _read_sheets(path: Path) -> dict[str, list[list[Any]]]:
    """The non-empty rows of every sheet, keyed by sheet title."""
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        return {
            worksheet.title: [
                list(row)
                for row in worksheet.iter_rows(values_only=True)
                if any(cell is not None for cell in row)
            ]
            for worksheet in workbook.worksheets
        }
    finally:
        workbook.close()


def _evidence(content: str, path: Path, source_type: str) -> Evidence:
    return {"content": content, "source": str(path), "source_type": source_type}


def _workbook_question(question: str, workbook_data: str) -> str:
    return f"Question:\n{question}\n\nWorkbook sheets and rows:\n{workbook_data}"


def _tools_evidence(
    state: AgentState,
    sheets: dict,
    workbook_data: str,
    path: Path,
    workbook_evidence: list[Evidence],
) -> list[Evidence]:
    """Evidence from the deterministic multi-column plan, or from the analysis."""
    from huggingface_agents_langgraph.pipeline.spreadsheet_tools import (
        plan_aggregation,
    )

    model = state.get("experiment", {}).get("model")
    try:
        calculation = plan_aggregation(state["question"], sheets, model)
    except (ValueError, TypeError, KeyError) as error:
        update = _analyze_workbook(state["question"], workbook_data, path, model)
        return [
            *update["evidence"],
            _evidence(
                f"Deterministic plan rejected: {error}", path, "spreadsheet_diagnostic"
            ),
            *workbook_evidence,
        ]
    return [
        _evidence(
            json.dumps(calculation, ensure_ascii=False),
            path,
            "spreadsheet_calculation",
        ),
        *workbook_evidence,
    ]


def _request_plan(question: str, workbook_data: str, model) -> dict | None:
    """Ask the model for a simple calculation plan; None when it cannot parse."""
    messages: list[ChatMessage] = [
        {"role": "system", "content": PLAN_INSTRUCTIONS},
        {"role": "user", "content": _workbook_question(question, workbook_data)},
    ]
    response = chat_completion(messages, max_tokens=384, model=model)
    try:
        plan = json.loads(response)
    except json.JSONDecodeError:
        return {"strategy": "analyze"}
    return plan if isinstance(plan, dict) else None


def spreadsheet_processing(state: AgentState) -> SpreadsheetProcessingUpdate:
    """Use deterministic calculations when possible and retain LLM fallback."""
    file_path = state.get("file_path")
    if file_path is None:
        raise ValueError("file_path is required to process an Excel attachment")

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Excel attachment does not exist: {path}")

    sheets = _read_sheets(path)
    if not any(sheets.values()):
        raise ValueError("Excel attachment contains no non-empty cells")

    workbook_data = json.dumps(sheets, ensure_ascii=False, default=str)
    workbook_evidence = select_relevant_evidence(
        state["question"], [_evidence(workbook_data, path, "spreadsheet_data")]
    )
    if improvement_enabled(state.get("experiment", {}), "spreadsheet_tools"):
        return {
            "evidence": _tools_evidence(
                state, sheets, workbook_data, path, workbook_evidence
            )
        }
    model = state.get("experiment", DEFAULT_EXPERIMENT).get("model")
    plan = _request_plan(state["question"], workbook_data, model)
    if plan is not None and plan.get("strategy") == "compute":
        result = _compute_plan(sheets, plan)
        if result is not None:
            return {
                "evidence": [
                    _evidence(result, path, "spreadsheet_calculation"),
                    _evidence(
                        json.dumps(plan, ensure_ascii=False),
                        path,
                        "spreadsheet_plan",
                    ),
                    *workbook_evidence,
                ]
            }

    update = _analyze_workbook(state["question"], workbook_data, path, model)
    return {"evidence": [*update["evidence"], *workbook_evidence]}


def _plan_header(rows: list[list[Any]]) -> dict[str, int] | None:
    """Column indexes by header, or None when the sheet cannot be queried."""
    if len(rows) < 2 or not rows[0]:
        return None
    headers = [str(header).strip() if header is not None else "" for header in rows[0]]
    if len(set(headers)) != len(headers):
        return None
    return {header: index for index, header in enumerate(headers) if header}


def _plan_filters(
    filters: list, column_indexes: dict[str, int]
) -> list[tuple[int, str, Any]] | None:
    """The filters as (column index, operator, value); None if any is unsupported."""
    resolved: list[tuple[int, str, Any]] = []
    for condition in filters:
        if (
            not isinstance(condition, dict)
            or condition.get("column") not in column_indexes
            or condition.get("operator") not in FILTER_OPERATORS
            or "value" not in condition
        ):
            return None
        resolved.append(
            (
                column_indexes[condition["column"]],
                condition["operator"],
                condition["value"],
            )
        )
    return resolved


def _aggregate(operation: str, values: list[Decimal]) -> Decimal:
    if operation == "sum":
        return sum(values, Decimal(0))
    if operation == "average":
        return sum(values, Decimal(0)) / len(values)
    if operation == "min":
        return min(values)
    return max(values)


def _compute_plan(
    sheets: dict[str, list[list[Any]]], plan: dict[str, Any]
) -> str | None:
    """Run a supported aggregation plan; return None for unsupported plans."""
    operation = plan.get("operation")
    column = plan.get("column")
    filters = plan.get("filters", [])
    if (
        plan.get("sheet") not in sheets
        or operation not in OPERATIONS
        or not isinstance(filters, list)
        or (operation != "count" and not isinstance(column, str))
    ):
        return None

    rows = sheets[plan["sheet"]]
    column_indexes = _plan_header(rows)
    if column_indexes is None or (
        operation != "count" and column not in column_indexes
    ):
        return None
    filter_indexes = _plan_filters(filters, column_indexes)
    if filter_indexes is None:
        return None

    matching_rows = [
        row
        for row in rows[1:]
        if all(
            _matches(row[index] if index < len(row) else None, operator, value)
            for index, operator, value in filter_indexes
        )
    ]
    if operation == "count":
        return f"Count: {len(matching_rows)}"

    value_index = column_indexes[column]
    try:
        values = [
            Decimal(str(row[value_index]))
            for row in matching_rows
            if value_index < len(row) and row[value_index] is not None
        ]
    except InvalidOperation:
        return None
    if not values:
        return None
    return f"{operation.title()} of {column}: {_aggregate(operation, values)}"


def _matches(cell: Any, operator: str, expected: Any) -> bool:
    """Compare a cell with one supported filter condition."""
    if operator == "equals":
        return str(cell).casefold() == str(expected).casefold()
    if operator == "not_equals":
        return str(cell).casefold() != str(expected).casefold()
    if operator == "contains":
        return str(expected).casefold() in str(cell).casefold()
    try:
        actual_number = Decimal(str(cell))
        expected_number = Decimal(str(expected))
    except InvalidOperation:
        return False
    if operator == "greater_than":
        return actual_number > expected_number
    if operator == "greater_or_equal":
        return actual_number >= expected_number
    if operator == "less_than":
        return actual_number < expected_number
    return actual_number <= expected_number


def _analyze_workbook(
    question: str,
    workbook_data: str,
    path: Path,
    model: ModelSelection | None = None,
) -> SpreadsheetProcessingUpdate:
    """Use the model's general analysis ability for plans beyond the DSL."""
    messages: list[ChatMessage] = [
        {"role": "system", "content": ANALYSIS_INSTRUCTIONS},
        {"role": "user", "content": _workbook_question(question, workbook_data)},
    ]
    content = chat_completion(messages, model=model)
    return {"evidence": [_evidence(content, path, "spreadsheet_analysis")]}
