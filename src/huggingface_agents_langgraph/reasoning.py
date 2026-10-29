"""Reasoning node that answers a task from acquired evidence."""

import json
import re
from typing import TypedDict

from huggingface_agents_langgraph.llm import ChatMessage, chat_completion
from huggingface_agents_langgraph.state import AgentState, Evidence

COUNT_QUESTION_PATTERN = re.compile(
    r"\bhow many\s+(?P<section>.+?)\s+(?:were|was|are|is)\b", re.IGNORECASE
)
YEAR_RANGE_PATTERN = re.compile(r"\bbetween\s+(\d{4})\s+and\s+(\d{4})\b", re.IGNORECASE)
WIKIPEDIA_HEADING_PATTERN = re.compile(r"^={2,4}\s*(.*?)\s*={2,4}$")
WIKIPEDIA_TABLE_YEAR_PATTERN = re.compile(r"^\|\s*(\d{4})(?:\s*\||\s*$)")


class ReasoningUpdate(TypedDict):
    """State fields produced by the reasoning node."""

    submitted_answer: str


def reasoning(state: AgentState) -> ReasoningUpdate:
    """Derive and format the final benchmark answer in one model call."""
    evidence = state.get("evidence", [])
    table_count = _count_wikipedia_table_entries(state["question"], evidence)
    if table_count is not None:
        return {"submitted_answer": str(table_count)}

    if evidence:
        system_instruction = (
            "Answer the question using only the supplied evidence. If the evidence "
            "contains program output, use that output. Do not introduce outside "
            "facts or invent missing information. Return only the concise final "
            "answer for an exact-match benchmark, without explanation, greeting, "
            "label, or quotation marks. Preserve units and requested notation. "
            "Do not repeat phrases; stop once the requested answer is complete."
        )
        task_content = (
            f"Question:\n{state['question']}\n\nEvidence:\n"
            f"{json.dumps(evidence, ensure_ascii=False)}\n/no_think"
        )
    else:
        system_instruction = (
            "Answer using only information in the question and reasoning that can "
            "be derived from it. Do not search for or introduce external facts. "
            "Return only the concise final answer for an exact-match benchmark, "
            "without explanation, greeting, label, or quotation marks. Preserve "
            "units and requested notation. Do not repeat phrases; stop once the "
            "requested answer is complete."
        )
        task_content = f"{state['question']}\n/no_think"

    messages: list[ChatMessage] = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": task_content},
    ]
    return {
        "submitted_answer": chat_completion(
            messages, max_tokens=512, frequency_penalty=0.3
        ).strip()
    }


def _count_wikipedia_table_entries(
    question: str,
    evidence: list[Evidence],
) -> int | None:
    """Count dated rows when the question names a matching Wikipedia section."""
    count_match = COUNT_QUESTION_PATTERN.search(question)
    range_match = YEAR_RANGE_PATTERN.search(question)
    if count_match is None or range_match is None:
        return None

    section_name = count_match.group("section").strip(" .?!").casefold()
    first_year, last_year = map(int, range_match.groups())
    if first_year > last_year:
        return None

    content = "\n".join(
        item["content"] for item in evidence if item["source_type"] == "wikipedia"
    )
    in_section = False
    section_found = False
    table_rows = 0
    matching_rows = 0
    for line in content.splitlines():
        heading_match = WIKIPEDIA_HEADING_PATTERN.match(line.strip())
        if heading_match:
            heading = heading_match.group(1).strip().casefold()
            if in_section and heading != section_name:
                break
            in_section = heading == section_name
            section_found |= in_section
            continue

        if not in_section:
            continue
        year_match = WIKIPEDIA_TABLE_YEAR_PATTERN.match(line.strip())
        if year_match:
            table_rows += 1
            year = int(year_match.group(1))
            if first_year <= year <= last_year:
                matching_rows += 1

    if section_found and table_rows:
        return matching_rows
    return None
