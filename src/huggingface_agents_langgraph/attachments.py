"""Retrieve GAIA task attachments from the official Hugging Face dataset."""

from functools import lru_cache
from pathlib import Path

from datasets import load_dataset
from huggingface_hub import hf_hub_download
from huggingface_hub.errors import EntryNotFoundError

DATASET_REPO_ID = "gaia-benchmark/GAIA"
DATASET_CONFIG = "2023_level1"
DATASET_SPLIT = "validation"


class TaskNotFoundError(LookupError):
    """Raised when a task ID is absent from the Unit 4 GAIA split."""


class AttachmentNotFoundError(FileNotFoundError):
    """Raised when GAIA metadata references an unavailable attachment."""


@lru_cache(maxsize=1)
def _load_attachment_index() -> dict[str, str | None]:
    dataset = load_dataset(
        DATASET_REPO_ID,
        DATASET_CONFIG,
        split=DATASET_SPLIT,
    )
    return {row["task_id"]: row.get("file_path") or None for row in dataset}


def get_attachment_path(task_id: str) -> Path | None:
    """Return the cached local path for a task attachment, if one exists.

    Raises:
        TaskNotFoundError: If ``task_id`` is not in the Unit 4 validation split.
        AttachmentNotFoundError: If metadata references a missing repository file.
    """
    attachment_index = _load_attachment_index()
    if task_id not in attachment_index:
        raise TaskNotFoundError(f"GAIA task ID not found: {task_id}")

    attachment_path = attachment_index[task_id]
    if attachment_path is None:
        return None

    try:
        local_path = hf_hub_download(
            repo_id=DATASET_REPO_ID,
            filename=attachment_path,
            repo_type="dataset",
        )
    except EntryNotFoundError as error:
        raise AttachmentNotFoundError(
            f"Attachment {attachment_path!r} for GAIA task {task_id!r} "
            "was not found in the official dataset repository."
        ) from error

    return Path(local_path)
