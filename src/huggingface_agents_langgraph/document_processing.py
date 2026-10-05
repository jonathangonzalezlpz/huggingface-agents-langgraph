"""Document processing node for PDF attachments."""

from pathlib import Path
from typing import TypedDict

from pypdf import PdfReader

from huggingface_agents_langgraph.evidence_selection import select_relevant_evidence
from huggingface_agents_langgraph.state import AgentState, Evidence


class DocumentProcessingUpdate(TypedDict):
    """State fields produced by the document processing node."""

    evidence: list[Evidence]


def document_processing(state: AgentState) -> DocumentProcessingUpdate:
    """Extract PDF text and select question-relevant evidence."""
    file_path = state.get("file_path")
    if file_path is None:
        raise ValueError("file_path is required to process a PDF attachment")

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF attachment does not exist: {path}")

    reader = PdfReader(path)
    page_evidence: list[Evidence] = [
        {
            "content": text.strip(),
            "source": f"{path}#page={page_number}",
            "source_type": "pdf_text",
        }
        for page_number, page in enumerate(reader.pages, start=1)
        if (text := page.extract_text() or "").strip()
    ]
    if not page_evidence:
        raise ValueError(
            "PDF attachment contains no extractable text; scanned PDFs require OCR"
        )

    return {"evidence": select_relevant_evidence(state["question"], page_evidence)}
