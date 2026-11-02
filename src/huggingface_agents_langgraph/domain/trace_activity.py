"""One line on what a node did, and figures that the evidence does not support."""

import re

MAX_REASON = 120
MAX_ANSWER = 80
_FIGURE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3})")


def _clip(value: object, limit: int) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[:limit] + "…"


def _decision(action: dict) -> str:
    target = action.get("url") or action.get("query") or action.get("expression")
    text = f"{action['action']} {target}" if target else str(action["action"])
    reason = action.get("reason")
    return f"{text} — {_clip(reason, MAX_REASON)}" if reason else text


def _acquisition(update: dict, known_notes: int) -> list[str]:
    parts = []
    notes = (update.get("research_notes") or [])[known_notes:]
    if notes:
        parts.append(_clip(notes[-1], MAX_REASON))
    if update.get("evidence"):
        parts.append(f"evidence: {len(update['evidence'])}")
    return parts


def _result(update: dict) -> list[str]:
    parts = []
    if update.get("draft_answer"):
        parts.append(f"draft: {len(update['draft_answer'])} chars")
    if "submitted_answer" in update:
        parts.append(f"answer: {_clip(update['submitted_answer'], MAX_ANSWER)}")
        if update.get("answer_warnings"):
            parts.append(f"warnings: {len(update['answer_warnings'])}")
    return parts


def node_activity(update: dict | None, known_notes: int = 0) -> str | None:
    """A short line from the fields a node changed, whatever the node is called.

    ``known_notes`` is how many acquisition notes earlier steps already reported.
    """
    if not update:
        return None
    action = update.get("research_action")
    if isinstance(action, dict) and action.get("action"):
        parts = [_decision(action)]
    else:
        parts = _acquisition(update, known_notes)
    if update.get("route"):
        parts.insert(0, f"route: {update['route']}")
    parts.extend(_result(update))
    return " · ".join(parts) or None


def _normalised(text: str) -> str:
    return _THOUSANDS.sub("", text)


def unsupported_figures(text: str, question: str, evidence: list[str]) -> list[str]:
    """Figures in ``text`` that appear in neither the question nor any evidence."""
    haystack = _normalised(" ".join([question, *evidence]))
    found: list[str] = []
    for match in _FIGURE.findall(_normalised(text)):
        if len(match.replace(".", "")) < 2 or match in found:
            continue
        if not re.search(rf"(?<![\d.]){re.escape(match)}(?![\d])", haystack):
            found.append(match)
    return found
