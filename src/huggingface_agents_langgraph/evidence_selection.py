"""Reusable retrieval of question-relevant text from external sources."""

import math
import re
from collections import Counter

from huggingface_agents_langgraph.config import (
    DOCUMENT_CHUNK_CHARACTERS,
    DOCUMENT_CHUNK_OVERLAP_CHARACTERS,
    DOCUMENT_MAX_EVIDENCE_CHARACTERS,
)
from huggingface_agents_langgraph.experiments import improvement_enabled
from huggingface_agents_langgraph.state import Evidence

TOKEN_PATTERN = re.compile(r"[a-z0-9]{2,}")
STOP_WORDS = {
    "about",
    "after",
    "all",
    "also",
    "and",
    "are",
    "article",
    "does",
    "from",
    "give",
    "have",
    "into",
    "its",
    "just",
    "name",
    "only",
    "that",
    "the",
    "their",
    "there",
    "these",
    "they",
    "this",
    "those",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}


def select_relevant_evidence(
    question: str,
    source_evidence: list[Evidence],
) -> list[Evidence]:
    """Chunk source text and keep the best matches within the context budget.

    The selector is independent of source type. Callers provide text with its
    provenance, such as a PDF page, a web page, or a Wikipedia article.
    """
    improved = improvement_enabled(None, "web_sources")
    if improved:
        from huggingface_agents_langgraph.source_store import retain_sources

        source_evidence = retain_sources(
            [item for item in source_evidence if not item.get("source_id")]
        ) + [item for item in source_evidence if item.get("source_id")]
    chunks = [
        (item | {"content": chunk})
        if improved
        else Evidence(
            content=chunk,
            source=item["source"],
            source_type=item["source_type"],
        )
        for item in source_evidence
        for chunk in _split_text(item["content"])
    ]
    total_characters = sum(len(chunk["content"]) for chunk in chunks)
    if total_characters <= DOCUMENT_MAX_EVIDENCE_CHARACTERS:
        return chunks

    question_terms = {
        token
        for token in TOKEN_PATTERN.findall(question.lower())
        if token not in STOP_WORDS
    }
    if not question_terms:
        return _sample_chunks(chunks)

    chunk_terms = [
        Counter(TOKEN_PATTERN.findall(chunk["content"].lower())) for chunk in chunks
    ]
    total_terms = sum(sum(counts.values()) for counts in chunk_terms)
    if not total_terms:
        return _sample_chunks(chunks)
    average_length = total_terms / len(chunk_terms)
    document_frequency = {
        term: sum(term in counts for counts in chunk_terms) for term in question_terms
    }
    scores: list[tuple[float, int]] = []
    for index, counts in enumerate(chunk_terms):
        length = sum(counts.values())
        score = 0.0
        for term in question_terms:
            frequency = counts[term]
            if frequency:
                inverse_frequency = math.log(
                    1
                    + (len(chunks) - document_frequency[term] + 0.5)
                    / (document_frequency[term] + 0.5)
                )
                length_factor = 0.25 + 0.75 * length / average_length
                score += (
                    inverse_frequency
                    * frequency
                    * 2.2
                    / (frequency + 1.2 * length_factor)
                )
        scores.append((score, index))

    if not any(score for score, _ in scores):
        return _sample_chunks(chunks)

    selected_indexes: list[int] = []
    selected_size = 0
    for _, index in sorted(scores, key=lambda item: (item[0], -item[1]), reverse=True):
        chunk_size = len(chunks[index]["content"])
        if selected_size + chunk_size > DOCUMENT_MAX_EVIDENCE_CHARACTERS:
            continue
        selected_indexes.append(index)
        selected_size += chunk_size
    return [chunks[index] for index in sorted(selected_indexes)]


def _split_text(text: str) -> list[str]:
    """Split extracted text into overlapping fragments of bounded size."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + DOCUMENT_CHUNK_CHARACTERS, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(end - DOCUMENT_CHUNK_OVERLAP_CHARACTERS, start + 1)
    return chunks


def _sample_chunks(chunks: list[Evidence]) -> list[Evidence]:
    """Sample across the sources when the question has no searchable terms."""
    largest_chunk_size = max(len(chunk["content"]) for chunk in chunks)
    sample_count = max(1, DOCUMENT_MAX_EVIDENCE_CHARACTERS // largest_chunk_size)
    if sample_count >= len(chunks):
        return chunks

    if sample_count == 1:
        sample_indexes = [len(chunks) // 2]
    else:
        sample_indexes = [
            round(index * (len(chunks) - 1) / (sample_count - 1))
            for index in range(sample_count)
        ]
    return [chunks[index] for index in sample_indexes]
