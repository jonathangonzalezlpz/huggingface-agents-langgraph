import json
from pathlib import Path

from openpyxl import Workbook

from huggingface_agents_langgraph import spreadsheet_processing


def test_spreadsheet_processing_passes_workbook_data_to_llm(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "sales.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sales"
    sheet.append(["Item", "Category", "Sales"])
    sheet.append(["Burger", "Food", 10.5])
    sheet.append(["Soda", "Drink", 2.0])
    workbook.save(workbook_path)

    captured_messages = []

    responses = iter(
        [
            json.dumps(
                {
                    "strategy": "compute",
                    "sheet": "Sales",
                    "operation": "sum",
                    "column": "Sales",
                    "filters": [
                        {
                            "column": "Category",
                            "operator": "equals",
                            "value": "Food",
                        }
                    ],
                }
            )
        ]
    )

    def chat_completion_mock(messages):
        captured_messages.extend(messages)
        return next(responses)

    monkeypatch.setattr(spreadsheet_processing, "chat_completion", chat_completion_mock)
    state = {
        "task_id": "task-1",
        "question": "What were food sales, excluding drinks?",
        "file_name": "sales.xlsx",
        "file_path": workbook_path,
    }

    update = spreadsheet_processing.spreadsheet_processing(state)

    workbook_data = json.loads(
        captured_messages[1]["content"].split(
            "Workbook sheets and rows:\n", maxsplit=1
        )[1]
    )
    assert workbook_data["Sales"] == [
        ["Item", "Category", "Sales"],
        ["Burger", "Food", 10.5],
        ["Soda", "Drink", 2],
    ]
    assert update == {
        "evidence": [
            {
                "content": "Sum of Sales: 10.5",
                "source": str(workbook_path),
                "source_type": "spreadsheet_calculation",
            }
        ]
    }


def test_spreadsheet_processing_falls_back_for_complex_questions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "sales.xlsx"
    workbook = Workbook()
    workbook.active.append(["Item", "Sales"])
    workbook.active.append(["Burger", 10.5])
    workbook.save(workbook_path)
    responses = iter([json.dumps({"strategy": "analyze"}), "Top item: Burger"])

    def chat_completion_mock(_messages):
        return next(responses)

    monkeypatch.setattr(spreadsheet_processing, "chat_completion", chat_completion_mock)
    state = {
        "task_id": "task-1",
        "question": "Which item had the highest sales and why?",
        "file_name": "sales.xlsx",
        "file_path": workbook_path,
    }

    update = spreadsheet_processing.spreadsheet_processing(state)

    assert update["evidence"][0]["content"] == "Top item: Burger"
    assert update["evidence"][0]["source_type"] == "spreadsheet_analysis"
