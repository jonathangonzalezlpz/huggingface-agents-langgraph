"""Extract question-focused evidence from local audio, images, and video."""

import gc
import math
import re
import sys
import tempfile
from pathlib import Path
from threading import Condition, Timer
from time import monotonic
from typing import TypedDict

from huggingface_agents_langgraph.config import (
    MEDIA_ASR_MODEL,
    MEDIA_AUDIO_CLASSIFIER_MODEL,
    MEDIA_MAX_VIDEO_FRAMES,
    MEDIA_MODELS_IDLE_SECONDS,
    MEDIA_VIDEO_FRAME_INTERVAL_SECONDS,
    MEDIA_VLM_MODEL,
)
from huggingface_agents_langgraph.state import AgentState, Evidence

IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".avi", ".mkv", ".mov", ".mp4", ".webm"}
AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}
SOUND_QUESTION_TERMS = re.compile(
    r"\b(sound|music|song|sing|instrument|noise|birdsong|audio|sounds|"
    r"m\u00fasica|canci\u00f3n|canta|instrumento|ruido|sonido|sonidos)\b",
    re.IGNORECASE,
)
SPEECH_QUESTION_TERMS = re.compile(
    r"\b(transcrib\w*|transcript|speech|spoken|speaker|say|says|said|speak|"
    r"talking|conversation|dialogue|lyrics|words|phrase|what is being said|"
    r"qu[eé] dice|transcripci[oó]n|habla|hablando|cantando|letra)\b",
    re.IGNORECASE,
)
ACOUSTIC_ONLY_QUESTION_TERMS = re.compile(
    r"\b(sound(s)?|noise(s)?|instrument(s)?|birdsong|footsteps|"
    r"audio event(s)?|sonido(s)?|ruido(s)?|instrumento(s)?)\b",
    re.IGNORECASE,
)
VIDEO_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?v=[\w-]+|youtu\.be/[\w-]+)",
    re.IGNORECASE,
)


class MultimediaProcessingUpdate(TypedDict):
    """State fields produced by multimedia processing."""

    evidence: list[Evidence]


def multimedia_processing(state: AgentState) -> MultimediaProcessingUpdate:
    """Transcribe or inspect the attachment, then return concise evidence."""
    file_path = state.get("file_path")
    if file_path is None:
        match = VIDEO_URL_PATTERN.search(state["question"])
        if match is None:
            raise ValueError(
                "file_path is required unless the question contains a YouTube URL"
            )
        with tempfile.TemporaryDirectory(prefix="gaia-video-") as temporary_directory:
            path = download_video(match.group(), Path(temporary_directory))
            evidence = _inspect_video(path, state["question"], match.group())
        return {"evidence": evidence}

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Multimedia attachment does not exist: {path}")

    extension = path.suffix.lower()
    source = str(path)
    if extension in IMAGE_EXTENSIONS:
        evidence = [_inspect_image(path, state["question"], source)]
    elif extension in AUDIO_EXTENSIONS:
        evidence = _inspect_audio(path, state["question"], source)
    elif extension in VIDEO_EXTENSIONS:
        evidence = _inspect_video(path, state["question"], source)
    else:
        raise ValueError(f"Unsupported multimedia attachment: {extension}")

    if not any(item["content"].strip() for item in evidence):
        raise ValueError("Multimedia processing produced no usable evidence")
    return {"evidence": evidence}


def _inspect_audio(path: Path, question: str, source: str) -> list[Evidence]:
    evidence: list[Evidence] = []
    needs_transcription = not ACOUSTIC_ONLY_QUESTION_TERMS.search(
        question
    ) or SPEECH_QUESTION_TERMS.search(question)
    if needs_transcription:
        transcript = _transcribe(path)
        if transcript:
            evidence.append(
                {
                    "content": f"Audio transcription:\n{transcript}",
                    "source": source,
                    "source_type": "audio_transcription",
                }
            )

    if SOUND_QUESTION_TERMS.search(question):
        labels = _classify_audio(path)
        if labels:
            evidence.append(
                {
                    "content": "Likely audio events: "
                    + "; ".join(
                        f"{label['label']} ({label['score']:.2f})" for label in labels
                    ),
                    "source": source,
                    "source_type": "audio_classification",
                }
            )
    return evidence


def _inspect_image(path: Path, question: str, source: str) -> Evidence:
    return {
        "content": _run_vision_model(path, question),
        "source": source,
        "source_type": "image_vlm",
    }


def _inspect_video(path: Path, question: str, source: str) -> list[Evidence]:
    asks_about_audio = bool(
        SOUND_QUESTION_TERMS.search(question) or SPEECH_QUESTION_TERMS.search(question)
    )
    evidence = (
        _inspect_audio(path, question, source)
        if asks_about_audio and _has_audio_stream(path)
        else []
    )
    for timestamp, image in _sample_video_frames(path):
        description = _run_vision_model(image, question)
        evidence.append(
            {
                "content": f"Video frame at {timestamp:.1f} seconds:\n{description}",
                "source": f"{source}#t={timestamp:.1f}s",
                "source_type": "video_frame_vlm",
            }
        )
    return evidence


def _transcribe(path: Path) -> str:
    try:
        with _asr_model_manager.use() as asr_model:
            segments, _ = asr_model.transcribe(str(path), vad_filter=True)
    except ImportError as error:
        raise RuntimeError(
            "Audio transcription requires the optional 'multimedia' dependencies"
        ) from error
    return " ".join(segment.text.strip() for segment in segments).strip()


def _load_asr_model():
    from faster_whisper import WhisperModel

    return WhisperModel(MEDIA_ASR_MODEL, device="cpu", compute_type="int8")


def _classify_audio(path: Path) -> list[dict[str, float | str]]:
    try:
        with _audio_classifier_manager.use() as classifier:
            predictions = classifier(str(path), top_k=5)
    except ImportError as error:
        raise RuntimeError(
            "Audio event recognition requires the optional 'multimedia' dependencies"
        ) from error
    return [
        {"label": str(item["label"]), "score": float(item["score"])}
        for item in predictions
    ]


def _load_audio_classifier():
    import torch
    from transformers import pipeline

    return pipeline(
        "audio-classification",
        model=MEDIA_AUDIO_CLASSIFIER_MODEL,
        device=0 if torch.cuda.is_available() else "cpu",
    )


def _run_vision_model(image, question: str) -> str:
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError(
            "Image and video analysis requires the optional 'multimedia' dependencies"
        ) from error

    if isinstance(image, Path):
        with Image.open(image) as opened_image:
            image = opened_image.convert("RGB")
    elif not isinstance(image, Image.Image):
        image = Image.fromarray(image).convert("RGB")

    image.thumbnail((1280, 1280))
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {
                    "type": "text",
                    "text": (
                        "Describe only visual evidence relevant to this question. "
                        "Do not guess details that are not visible.\nQuestion: "
                        f"{question}"
                    ),
                },
            ],
        }
    ]
    try:
        with _vision_pipeline_manager.use() as vision_pipeline:
            response = vision_pipeline(
                text=messages,
                max_new_tokens=120,
                return_full_text=False,
            )
    except ImportError as error:
        raise RuntimeError(
            "Image and video analysis requires the optional 'multimedia' dependencies"
        ) from error
    try:
        text = response[0]["generated_text"]
    except (IndexError, KeyError, TypeError) as error:
        raise ValueError("The configured VLM returned an invalid response") from error
    if not isinstance(text, str) or not text.strip():
        raise ValueError("The configured VLM returned empty evidence")
    return text.strip()


def _get_vision_pipeline():
    import torch
    from transformers import pipeline

    return pipeline(
        "image-text-to-text",
        model=MEDIA_VLM_MODEL,
        device=0 if torch.cuda.is_available() else "cpu",
    )


class IdleModelManager:
    """Keep a model available during use and unload it after an idle period."""

    def __init__(self, loader, idle_seconds: int) -> None:
        self._loader = loader
        self._idle_seconds = idle_seconds
        self._model = None
        self._active_users = 0
        self._loading = False
        self._ever_loaded = False
        self._last_used_at: float | None = None
        self._timer: Timer | None = None
        self._condition = Condition()

    def use(self):
        """Return a context manager that protects an in-use model from unloading."""
        return _ModelUse(self)

    def status(self) -> dict[str, str | int | float | None]:
        """Describe current model state without loading the model."""
        with self._condition:
            if self._loading:
                state = "loading"
            elif self._active_users:
                state = "in_use"
            elif self._model is not None:
                state = "loaded"
            elif self._ever_loaded:
                state = "unloaded"
            else:
                state = "not_loaded"
            idle_for = (
                max(0, int(monotonic() - self._last_used_at))
                if self._last_used_at is not None and self._model is None
                else 0
            )
            return {
                "state": state,
                "idle_for_seconds": idle_for,
                "idle_timeout_seconds": self._idle_seconds,
            }

    def _acquire(self):
        with self._condition:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            while self._loading:
                self._condition.wait()
            if self._model is not None:
                self._active_users += 1
                return self._model
            self._loading = True

        try:
            model = self._loader()
        except Exception:
            with self._condition:
                self._loading = False
                self._condition.notify_all()
            raise

        with self._condition:
            self._model = model
            self._loading = False
            self._ever_loaded = True
            self._active_users += 1
            self._condition.notify_all()
            return self._model

    def _release(self) -> None:
        with self._condition:
            self._active_users -= 1
            if self._active_users == 0:
                self._last_used_at = monotonic()
                self._timer = Timer(self._idle_seconds, self._unload)
                self._timer.daemon = True
                self._timer.start()

    def _unload(self) -> None:
        with self._condition:
            if self._active_users:
                return
            self._model = None
            self._timer = None
        gc.collect()
        torch = sys.modules.get("torch")
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()


class _ModelUse:
    def __init__(self, manager: IdleModelManager) -> None:
        self._manager = manager
        self._model = None

    def __enter__(self):
        self._model = self._manager._acquire()
        return self._model

    def __exit__(self, *_exc_info) -> None:
        self._model = None
        self._manager._release()


_vision_pipeline_manager = IdleModelManager(
    _get_vision_pipeline, MEDIA_MODELS_IDLE_SECONDS
)
_asr_model_manager = IdleModelManager(_load_asr_model, MEDIA_MODELS_IDLE_SECONDS)
_audio_classifier_manager = IdleModelManager(
    _load_audio_classifier,
    MEDIA_MODELS_IDLE_SECONDS,
)


def get_multimedia_model_status() -> list[dict[str, str | int | float | None]]:
    """Return model configuration and runtime state without loading models."""
    return [
        {
            "id": "vlm",
            "name": "VLM · vision",
            "model": MEDIA_VLM_MODEL,
            **_vision_pipeline_manager.status(),
        },
        {
            "id": "whisper",
            "name": "Whisper · transcription",
            "model": MEDIA_ASR_MODEL,
            **_asr_model_manager.status(),
        },
        {
            "id": "ast",
            "name": "AST · audio events",
            "model": MEDIA_AUDIO_CLASSIFIER_MODEL,
            **_audio_classifier_manager.status(),
        },
    ]


def _sample_video_frames(path: Path) -> list[tuple[float, object]]:
    try:
        import av
    except ImportError as error:
        raise RuntimeError(
            "Video frame extraction requires the optional 'multimedia' dependencies"
        ) from error

    frames: list[tuple[float, object]] = []
    with av.open(str(path)) as container:
        video_stream = next(
            (stream for stream in container.streams if stream.type == "video"), None
        )
        if video_stream is None:
            raise ValueError("Video attachment contains no video stream")
        duration = (
            float(video_stream.duration * video_stream.time_base)
            if video_stream.duration is not None and video_stream.time_base is not None
            else 0.0
        )
        if duration > 0 and video_stream.time_base is not None:
            interval = max(
                MEDIA_VIDEO_FRAME_INTERVAL_SECONDS,
                duration / max(MEDIA_MAX_VIDEO_FRAMES - 1, 1),
            )
            sample_count = min(
                MEDIA_MAX_VIDEO_FRAMES,
                math.floor(duration / interval) + 1,
            )
            start_ticks = video_stream.start_time or 0
            start_seconds = float(start_ticks * video_stream.time_base)
            for index in range(sample_count):
                offset = min(index * interval, duration)
                target_seconds = start_seconds + offset
                target_ticks = start_ticks + round(offset / video_stream.time_base)
                container.seek(target_ticks, stream=video_stream)
                for frame in container.decode(video_stream):
                    timestamp = frame.time
                    if timestamp is None and frame.pts is not None:
                        frame_time_base = frame.time_base or video_stream.time_base
                        timestamp = float(frame.pts * frame_time_base)
                    if timestamp is None or timestamp < target_seconds:
                        continue
                    frames.append((float(timestamp), frame.to_image()))
                    break
        else:
            next_timestamp = 0.0
            for frame in container.decode(video_stream):
                timestamp = float(frame.time or 0.0)
                if timestamp < next_timestamp:
                    continue
                frames.append((timestamp, frame.to_image()))
                next_timestamp = timestamp + MEDIA_VIDEO_FRAME_INTERVAL_SECONDS
                if len(frames) >= MEDIA_MAX_VIDEO_FRAMES:
                    break
    return frames


def _has_audio_stream(path: Path) -> bool:
    import av

    with av.open(str(path)) as container:
        return any(stream.type == "audio" for stream in container.streams)


def download_video(url: str, directory: Path) -> Path:
    """Download a video URL to a temporary directory using yt-dlp."""
    try:
        import yt_dlp
    except ImportError as error:
        raise RuntimeError(
            "Downloading videos requires the optional 'multimedia' dependencies"
        ) from error

    options = {
        "format": "best[height<=480]/bestvideo*[height<=480]/bestvideo*/best",
        "outtmpl": str(directory / "source.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)
        downloaded_path = Path(downloader.prepare_filename(info))
    if not downloaded_path.is_file():
        downloaded_path = directory / "source.mp4"
    if not downloaded_path.is_file():
        raise FileNotFoundError("The video downloader produced no media file")
    return downloaded_path


def get_gpu_status() -> dict[str, str | bool | None]:
    """Report whether CUDA is available to multimedia models."""
    try:
        import torch
    except ImportError:
        return {"available": False, "name": None, "backend": "PyTorch no instalado"}

    try:
        available = torch.cuda.is_available()
        return {
            "available": available,
            "name": torch.cuda.get_device_name(0) if available else None,
            "backend": "CUDA" if available else "CPU",
        }
    except Exception:
        return {"available": False, "name": None, "backend": "CUDA no disponible"}
