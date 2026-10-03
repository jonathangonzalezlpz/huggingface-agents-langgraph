from pathlib import Path

import pytest
from huggingface_hub.errors import EntryNotFoundError

from huggingface_agents_langgraph import attachments


@pytest.fixture(autouse=True)
def clear_attachment_index() -> None:
    attachments._load_attachment_index.cache_clear()
    yield
    attachments._load_attachment_index.cache_clear()


def mock_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {"task_id": "task-with-file", "file_path": "2023/test/file.pdf"},
        {"task_id": "task-without-file", "file_path": None},
    ]

    def load_dataset_mock(
        *args: object, **kwargs: object
    ) -> list[dict[str, str | None]]:
        return rows

    monkeypatch.setattr(attachments, "load_dataset", load_dataset_mock)


def test_get_attachment_path_returns_cached_local_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mock_dataset(monkeypatch)
    local_file = tmp_path / "file.pdf"
    local_file.touch()
    download_calls: list[dict[str, str]] = []

    def download_mock(**kwargs: str) -> str:
        download_calls.append(kwargs)
        return str(local_file)

    monkeypatch.setattr(attachments, "hf_hub_download", download_mock)

    result = attachments.get_attachment_path("task-with-file")

    assert result == local_file
    assert download_calls == [
        {
            "repo_id": "gaia-benchmark/GAIA",
            "filename": "2023/test/file.pdf",
            "repo_type": "dataset",
        }
    ]


def test_get_attachment_path_returns_none_for_task_without_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_dataset(monkeypatch)
    monkeypatch.setattr(
        attachments,
        "hf_hub_download",
        lambda **kwargs: pytest.fail("No download should be attempted"),
    )

    assert attachments.get_attachment_path("task-without-file") is None


def test_get_attachment_path_raises_for_unknown_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_dataset(monkeypatch)

    with pytest.raises(attachments.TaskNotFoundError, match="unknown-task"):
        attachments.get_attachment_path("unknown-task")


def test_get_attachment_path_raises_when_dataset_file_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_dataset(monkeypatch)

    def missing_file(**kwargs: str) -> str:
        raise EntryNotFoundError("Attachment missing")

    monkeypatch.setattr(attachments, "hf_hub_download", missing_file)

    with pytest.raises(attachments.AttachmentNotFoundError, match="file.pdf"):
        attachments.get_attachment_path("task-with-file")
