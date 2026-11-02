"""Pure summaries of the timings and errors recorded in an experiment."""

import math
from statistics import mean, median


def timing_summary(answers: list[dict]) -> dict:
    """Summarize observed timings without counting missing measurements as zero."""
    times = sorted(
        answer["duration_seconds"]
        for answer in answers
        if isinstance(answer.get("duration_seconds"), (int, float))
    )
    return {
        "count": len(times),
        "total_seconds": sum(times),
        "mean_seconds": mean(times) if times else None,
        "median_seconds": median(times) if times else None,
        "p95_seconds": times[max(0, math.ceil(len(times) * 0.95) - 1)]
        if times
        else None,
        "technical_errors": sum(bool(answer.get("error")) for answer in answers),
    }
