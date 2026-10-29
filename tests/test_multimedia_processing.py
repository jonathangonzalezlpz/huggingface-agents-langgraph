import sys
from pathlib import Path
from time import sleep
from types import SimpleNamespace

import pytest

from huggingface_agents_langgraph import multimedia_processing as media


def test_image_processing_returns_vlm_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "board.png"
    image_path.touch()
    monkeypatch.setattr(media, "_run_vision_model", lambda _image, _question: "Board")

    result = media.multimedia_processing(
        {
            "task_id": "task-1",
            "question": "What is on the board?",
            "file_name": "board.png",
            "file_path": image_path,
        }
    )

    assert result["evidence"] == [
        {
            "content": "Board",
            "source": str(image_path),
            "source_type": "image_vlm",
        }
    ]


def test_audio_recognition_runs_only_when_question_needs_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "memo.mp3"
    audio_path.touch()
    monkeypatch.setattr(media, "_transcribe", lambda _path: "Add strawberries.")
    monkeypatch.setattr(
        media,
        "_classify_audio",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("Transcription questions should skip audio classification")
        ),
    )
    state = {
        "task_id": "task-1",
        "question": "Transcribe the recipe from this audio recording.",
        "file_name": "memo.mp3",
        "file_path": audio_path,
    }

    result = media.multimedia_processing(state)

    assert len(result["evidence"]) == 1
    assert result["evidence"][0]["source_type"] == "audio_transcription"


def test_audio_classification_is_added_for_sound_questions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "song.mp3"
    audio_path.touch()

    def unexpected_transcription(_path):
        raise AssertionError("Acoustic-only questions should skip transcription")

    monkeypatch.setattr(media, "_transcribe", unexpected_transcription)
    monkeypatch.setattr(
        media,
        "_classify_audio",
        lambda _path: [{"label": "singing", "score": 0.75}],
    )
    state = {
        "task_id": "task-1",
        "question": "What sounds do you hear?",
        "file_name": "song.mp3",
        "file_path": audio_path,
    }

    result = media.multimedia_processing(state)

    assert result["evidence"][0]["source_type"] == "audio_classification"


def test_video_processing_uses_transcript_and_sampled_frames(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "clip.mp4"
    video_path.touch()
    monkeypatch.setattr(media, "_has_audio_stream", lambda _path: True)
    monkeypatch.setattr(media, "_transcribe", lambda _path: "Birds are flying.")
    monkeypatch.setattr(media, "_sample_video_frames", lambda _path: [(2.5, object())])
    monkeypatch.setattr(
        media, "_run_vision_model", lambda _image, _question: "Two birds are visible."
    )

    result = media.multimedia_processing(
        {
            "task_id": "task-1",
            "question": "How many birds are visible and what does the narrator say?",
            "file_name": "clip.mp4",
            "file_path": video_path,
        }
    )

    assert [item["source_type"] for item in result["evidence"]] == [
        "audio_transcription",
        "video_frame_vlm",
    ]
    assert result["evidence"][1]["source"].endswith("#t=2.5s")


def test_video_skips_audio_models_for_visual_question(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "birds.mp4"
    video_path.touch()

    def unexpected_audio_call(_path):
        raise AssertionError("Visual-only video questions should skip audio analysis")

    monkeypatch.setattr(media, "_has_audio_stream", unexpected_audio_call)
    monkeypatch.setattr(media, "_transcribe", unexpected_audio_call)
    monkeypatch.setattr(media, "_sample_video_frames", lambda _path: [(4.0, object())])
    monkeypatch.setattr(
        media, "_run_vision_model", lambda _image, _question: "Three birds are visible."
    )

    result = media.multimedia_processing(
        {
            "task_id": "task-1",
            "question": "How many bird species are visible at once?",
            "file_name": "birds.mp4",
            "file_path": video_path,
        }
    )

    assert [item["source_type"] for item in result["evidence"]] == ["video_frame_vlm"]


def test_video_sampling_seeks_to_sparse_timestamps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seeks = []
    stream = SimpleNamespace(type="video", duration=20, time_base=1, start_time=0)
    target_stream = stream

    class FakeFrame:
        def __init__(self, timestamp: float) -> None:
            self.time = timestamp
            self.pts = None

        def to_image(self) -> float:
            return self.time

    class FakeContainer:
        streams = [stream]

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def seek(self, offset: int, *, stream: object) -> None:
            assert stream is target_stream
            seeks.append(offset)

        def decode(self, _stream):
            return iter([FakeFrame(float(seeks[-1]))])

    monkeypatch.setitem(
        sys.modules,
        "av",
        SimpleNamespace(open=lambda _path: FakeContainer()),
    )

    frames = media._sample_video_frames(tmp_path / "clip.mp4")

    assert seeks == [0, 5, 10, 15, 20]
    assert [timestamp for timestamp, _frame in frames] == [0, 5, 10, 15, 20]


def test_media_processing_rejects_missing_attachment() -> None:
    state = {"task_id": "task-1", "question": "Describe this", "file_name": ""}

    with pytest.raises(ValueError, match="file_path is required"):
        media.multimedia_processing(state)


def test_multimedia_model_is_reloaded_after_idle_timeout() -> None:
    load_count = 0

    def load_model() -> object:
        nonlocal load_count
        load_count += 1
        return object()

    manager = media.IdleModelManager(load_model, idle_seconds=0.02)
    assert manager.status()["state"] == "not_loaded"
    with manager.use() as first_model:
        assert first_model is not None
        assert manager.status()["state"] == "in_use"
    with manager.use() as reused_model:
        assert reused_model is first_model

    sleep(0.1)
    assert manager.status()["state"] == "unloaded"

    with manager.use() as reloaded_model:
        assert reloaded_model is not first_model
    assert load_count == 2


def test_transcription_consumes_segments_before_releasing_model(monkeypatch):
    from contextlib import contextmanager

    active = []

    def segments():
        assert active == [True]
        yield SimpleNamespace(start=1.0, end=2.0, text="Study pages 10 and 20.")

    model = SimpleNamespace(transcribe=lambda *_a, **_k: (segments(), None))

    @contextmanager
    def use():
        active.append(True)
        try:
            yield model
        finally:
            active.clear()

    monkeypatch.setattr(media, "_asr_model_manager", SimpleNamespace(use=use))
    assert (
        media._transcribe(Path("recording.mp3")) == "[1.0-2.0s] Study pages 10 and 20."
    )
    assert active == []


def test_audio_classifier_receives_waveform_instead_of_filename(monkeypatch):
    from contextlib import nullcontext

    waveform = object()
    calls = []

    def classify(inputs, **kwargs):
        calls.append(inputs)
        return [{"label": "Music", "score": 0.9}]

    classify.feature_extractor = SimpleNamespace(sampling_rate=16000)
    monkeypatch.setattr(
        media,
        "_audio_classifier_manager",
        SimpleNamespace(use=lambda: nullcontext(classify)),
    )
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper.audio",
        SimpleNamespace(decode_audio=lambda *_a, **_k: waveform),
    )
    result = media._classify_audio(Path("sample.mp3"))
    assert calls == [{"raw": waveform, "sampling_rate": 16000}]
    assert result[0]["label"] == "Music"
