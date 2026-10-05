from huggingface_agents_langgraph.evidence_selection import select_relevant_evidence


def test_select_relevant_evidence_works_with_web_sources(monkeypatch) -> None:
    from huggingface_agents_langgraph import evidence_selection

    monkeypatch.setattr(evidence_selection, "DOCUMENT_CHUNK_CHARACTERS", 100)
    monkeypatch.setattr(evidence_selection, "DOCUMENT_CHUNK_OVERLAP_CHARACTERS", 0)
    monkeypatch.setattr(evidence_selection, "DOCUMENT_MAX_EVIDENCE_CHARACTERS", 60)
    source_evidence = [
        {
            "content": "Birds live in forests and build nests in trees.",
            "source": "https://example.org/article",
            "source_type": "web_page",
        },
        {
            "content": "The Vietnamese specimens were deposited in Paris.",
            "source": "https://example.org/article#museum",
            "source_type": "web_page",
        },
        {
            "content": "The paper also lists several related publications.",
            "source": "https://example.org/article#references",
            "source_type": "web_page",
        },
    ]

    selected = select_relevant_evidence(
        "Where were the Vietnamese specimens deposited?", source_evidence
    )

    assert selected == [
        {
            "content": "The Vietnamese specimens were deposited in Paris.",
            "source": "https://example.org/article#museum",
            "source_type": "web_page",
        }
    ]
