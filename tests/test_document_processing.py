from pathlib import Path

import pytest

from huggingface_agents_langgraph import document_processing, evidence_selection


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakePdfReader:
    def __init__(self, _path: Path) -> None:
        self.pages = [FakePage("First page text"), FakePage(""), FakePage("Last page")]


def test_document_processing_collects_text_with_page_numbers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "document.pdf"
    pdf_path.touch()
    monkeypatch.setattr(document_processing, "PdfReader", FakePdfReader)
    state = {
        "task_id": "task-1",
        "question": "What does the document say?",
        "file_name": "document.pdf",
        "file_path": pdf_path,
    }

    update = document_processing.document_processing(state)

    assert update == {
        "evidence": [
            {
                "content": "First page text",
                "source": f"{pdf_path}#page=1",
                "source_type": "pdf_text",
            },
            {
                "content": "Last page",
                "source": f"{pdf_path}#page=3",
                "source_type": "pdf_text",
            },
        ]
    }


def test_document_processing_selects_relevant_chunks_for_long_pdfs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "long.pdf"
    pdf_path.touch()

    class LongPdfReader:
        def __init__(self, _path: Path) -> None:
            self.pages = [
                FakePage("General background and other unrelated material."),
                FakePage("Specimens were deposited in Paris after examination."),
                FakePage("Additional unrelated notes and references."),
            ]

    monkeypatch.setattr(document_processing, "PdfReader", LongPdfReader)
    monkeypatch.setattr(evidence_selection, "DOCUMENT_MAX_EVIDENCE_CHARACTERS", 60)
    state = {
        "task_id": "task-1",
        "question": "Where were the specimens deposited?",
        "file_name": "long.pdf",
        "file_path": pdf_path,
    }

    update = document_processing.document_processing(state)

    assert update["evidence"] == [
        {
            "content": "Specimens were deposited in Paris after examination.",
            "source": f"{pdf_path}#page=2",
            "source_type": "pdf_text",
        }
    ]


def test_document_processing_rejects_scanned_pdf_without_text_layer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.touch()

    class ScannedPdfReader:
        def __init__(self, _path: Path) -> None:
            self.pages = [FakePage("")]

    monkeypatch.setattr(document_processing, "PdfReader", ScannedPdfReader)
    state = {
        "task_id": "task-1",
        "question": "What does the document say?",
        "file_name": "scanned.pdf",
        "file_path": pdf_path,
    }

    with pytest.raises(ValueError, match="scanned PDFs require OCR"):
        document_processing.document_processing(state)
