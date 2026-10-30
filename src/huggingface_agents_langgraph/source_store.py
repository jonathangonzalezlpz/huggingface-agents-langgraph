"""Retain full source text outside the model context for bounded rereading."""

import hashlib

from huggingface_agents_langgraph.run_tracking import current_trace


def retain_sources(items: list[dict]) -> list[dict]:
    """Assign content-addressed handles to the sources of the current run."""
    trace = current_trace.get()
    if trace is None:
        return items
    result = []
    for item in items:
        identifier = hashlib.sha256(
            (item["source"] + "\0" + item["content"]).encode()
        ).hexdigest()[:16]
        stored = item | {"source_id": identifier}
        trace.sources[identifier] = stored
        result.append(stored)
    return result


def source_catalog() -> list[dict]:
    """Return source handles and sizes without copying full documents to prompts."""
    trace = current_trace.get()
    return [
        {"source_id": key, "source": item["source"], "characters": len(item["content"])}
        for key, item in (trace.sources.items() if trace else [])
    ]


def read_source(source_id: str, *, query: str = "", start: int = 0) -> list[dict]:
    """Read a bounded passage, optionally located by a literal search term."""
    trace = current_trace.get()
    if trace is None or source_id not in trace.sources:
        raise ValueError("Unknown source handle")
    item = trace.sources[source_id]
    if query:
        position = item["content"].casefold().find(query.casefold(), start)
        if position < 0:
            raise ValueError("The requested text was not found in this source")
        start = max(0, position - 1000)
    return [
        item
        | {
            "content": item["content"][start : start + 8000],
            "source": f"{item['source']}#characters={start}-{start + 8000}",
        }
    ]
