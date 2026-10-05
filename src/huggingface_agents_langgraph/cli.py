"""Run a random GAIA task or the full Unit 4 question set in a terminal."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from huggingface_agents_langgraph.graph import build_state_graph

SCORING_API_URL = "https://agents-course-unit4-scoring.hf.space"


def _fetch_questions(endpoint: str) -> list[dict[str, object]]:
    """Fetch one random task or all evaluation tasks from the course API."""
    try:
        with urlopen(f"{SCORING_API_URL}/{endpoint}", timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Could not load questions from /{endpoint}: {error}"
        ) from error

    if endpoint == "random-question":
        if not isinstance(payload, dict):
            raise ValueError(
                "The random-question endpoint returned an invalid response"
            )
        return [payload]
    if not isinstance(payload, list):
        raise ValueError("The questions endpoint did not return a list")
    return payload


def _run_task(task: dict[str, object], index: int, total: int) -> None:
    """Display the task and its answer produced by the local graph."""
    task_id = task.get("task_id")
    question = task.get("question")
    file_name = task.get("file_name") or ""
    if not isinstance(task_id, str) or not isinstance(question, str):
        print("Task skipped: the API response is missing task_id or question.")
        return

    print(f"\n{'=' * 72}\nQUESTION {index}/{total} · {task_id}\n{'=' * 72}")
    print(question)
    print(f"Attachment: {file_name if file_name else 'none'}")

    try:
        result = build_state_graph().invoke(
            {
                "task_id": task_id,
                "question": question,
                "file_name": file_name if isinstance(file_name, str) else "",
            }
        )
    except Exception as error:
        print(f"Agent error: {error}")
        return

    submitted_answer = result.get("submitted_answer")
    if submitted_answer:
        print(f"Answer: {submitted_answer}")
    else:
        print(f"Answer: not produced (route: {result.get('route', 'unknown')})")


def main() -> None:
    """Prompt for the question source and run the selected task set."""
    print("GAIA terminal runner\n1. Random question\n2. Full question battery")
    choice = input("Select 1 or 2: ").strip()
    if choice not in {"1", "2"}:
        print("No valid selection; exiting.")
        return

    endpoint = "random-question" if choice == "1" else "questions"
    try:
        questions = _fetch_questions(endpoint)
    except (RuntimeError, ValueError) as error:
        print(f"Could not start the run: {error}")
        return

    total = len(questions)
    print(f"Loaded {total} question(s).")
    for index, task in enumerate(questions, start=1):
        _run_task(task, index, total)


if __name__ == "__main__":
    main()
