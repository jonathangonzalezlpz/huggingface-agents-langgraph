"""Assign the model calls of older records to their node by duration and order."""

EXACT_SECONDS = 0.03

Link = tuple[int, float] | None


def _durations(items: list[dict]) -> list[float]:
    return [item.get("duration_seconds") or 0.0 for item in items]


def _exact_matches(capacity: list[float], durations: list[float]) -> list[int | None]:
    """Calls that last as long as a step: that step was a single model call."""
    matches: list[int | None] = [None] * len(durations)
    cursor = 0
    for index, duration in enumerate(durations):
        if duration <= 0:
            continue
        for step in range(cursor, len(capacity)):
            if abs(capacity[step] - duration) <= EXACT_SECONDS:
                matches[index], cursor = step, step
                break
    return matches


def infer_links(steps: list[dict], calls: list[dict]) -> list[Link]:
    """For each call: the step it ran in and its offset there, or ``None``."""
    capacity, durations = _durations(steps), _durations(calls)
    exact = _exact_matches(capacity, durations)
    reserved = {step for step in exact if step is not None}
    used = [0.0] * len(steps)
    links: list[Link] = []
    previous = 0
    for index, duration in enumerate(durations):
        step = exact[index]
        if step is None:
            upper = next(
                (s for s in exact[index + 1 :] if s is not None), len(steps) - 1
            )
            step = next(
                (
                    s
                    for s in range(previous, upper + 1)
                    if s not in reserved
                    and capacity[s] - used[s] + EXACT_SECONDS >= duration
                ),
                None,
            )
        if step is None:
            links.append(None)
            continue
        links.append((step, round(used[step], 4)))
        used[step] += duration
        previous = step
    return links
