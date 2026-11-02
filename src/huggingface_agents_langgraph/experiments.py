"""Experiment profiles for selectively enabling graph capabilities."""

from copy import deepcopy
from typing import Literal, NotRequired, TypedDict

CAPABILITIES = ("code", "spreadsheet", "document", "multimedia", "web")
IMPROVEMENTS = (
    "reasoning_control",
    "answer_contract",
    "web_sources",
    "spreadsheet_tools",
    "multimedia_tools",
    "calculation_tools",
)
ModelProvider = Literal["configured", "ollama"]


class ModelSelection(TypedDict):
    """A locally available model served by a supported OpenAI-compatible API."""

    provider: ModelProvider
    model_id: str


class ExperimentConfig(TypedDict):
    """Runtime controls for a single graph experiment."""

    name: str
    force_direct: bool
    enabled_capabilities: list[str]
    model: ModelSelection | None
    vision_model: NotRequired[ModelSelection | None]
    pipeline_version: NotRequired[str]
    improvements: NotRequired[list[str]]
    reasoning_mode: NotRequired[str]
    thinking_tokens: NotRequired[int]
    solution_tokens: NotRequired[int]
    sampling_profile: NotRequired[str]
    seed: NotRequired[int | None]
    architecture: NotRequired[str]


DEFAULT_EXPERIMENT: ExperimentConfig = {
    "name": "Completo",
    "force_direct": False,
    "enabled_capabilities": list(CAPABILITIES),
    "model": None,
    "vision_model": None,
    "pipeline_version": "2",
    "improvements": [],
    "reasoning_mode": "bounded",
    "thinking_tokens": 512,
    "solution_tokens": 1024,
    "sampling_profile": "legacy",
    "seed": None,
}


def normalize_experiment(value: object) -> ExperimentConfig:
    """Validate user-supplied experiment settings and fill safe defaults."""
    if value is None:
        return deepcopy(DEFAULT_EXPERIMENT)
    if not isinstance(value, dict):
        raise ValueError("experiment must be an object")

    name = value.get("name", "Personalizado")
    force_direct = value.get("force_direct", False)
    enabled = value.get("enabled_capabilities", list(CAPABILITIES))
    model = value.get("model")
    vision_model = value.get("vision_model")
    version = value.get("pipeline_version", "2")
    improvements = value.get("improvements", [])
    mode = value.get("reasoning_mode", "bounded")
    thinking = value.get("thinking_tokens", 512)
    solution = value.get("solution_tokens", 1024)
    sampling = value.get(
        "sampling_profile", "controlled" if version == "3.1" else "legacy"
    )
    seed = value.get("seed", 42 if version == "3.1" else None)
    architecture = value.get("architecture")
    if architecture is not None and (
        not isinstance(architecture, str)
        or not architecture.strip()
        or len(architecture.strip()) > 100
    ):
        raise ValueError("experiment.architecture must be a non-empty string")
    if sampling not in {"legacy", "controlled", "author"}:
        raise ValueError("Unsupported sampling profile")
    if seed is not None and (type(seed) is not int or not 0 <= seed < 2**32):
        raise ValueError("seed must be an unsigned 32-bit integer")
    if version not in {"2", "3", "3.1"}:
        raise ValueError("Unsupported pipeline version")
    if (
        not isinstance(improvements, list)
        or any(
            not isinstance(item, str) or item not in IMPROVEMENTS
            for item in improvements
        )
        or (version == "2" and improvements)
    ):
        raise ValueError("Invalid improvements for this pipeline version")
    if mode not in {"off", "bounded"}:
        raise ValueError("Unsupported reasoning mode")
    if any(
        type(item) is not int or not 0 <= item <= 8192 for item in (thinking, solution)
    ):
        raise ValueError("Token budgets must be integers between 0 and 8192")
    if solution < 128:
        raise ValueError("The solution budget must be at least 128 tokens")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("experiment.name must be a non-empty string")
    if not isinstance(force_direct, bool):
        raise ValueError("experiment.force_direct must be a boolean")
    if not isinstance(enabled, list) or any(
        not isinstance(item, str) or item not in CAPABILITIES for item in enabled
    ):
        raise ValueError(
            "experiment.enabled_capabilities contains an unknown capability"
        )
    if model is not None:
        if not isinstance(model, dict):
            raise ValueError("experiment.model must be an object")
        provider = model.get("provider")
        model_id = model.get("model_id")
        if not isinstance(provider, str) or provider not in {"configured", "ollama"}:
            raise ValueError("experiment.model.provider is unsupported")
        if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 200:
            raise ValueError("experiment.model.model_id must be a non-empty string")
        model = {"provider": provider, "model_id": model_id.strip()}
    if vision_model is not None:
        if (
            not isinstance(vision_model, dict)
            or vision_model.get("provider") not in {"configured", "ollama"}
            or not isinstance(vision_model.get("model_id"), str)
            or not vision_model["model_id"].strip()
            or len(vision_model["model_id"]) > 200
        ):
            raise ValueError("experiment.vision_model is invalid")
        vision_model = {
            "provider": vision_model["provider"],
            "model_id": vision_model["model_id"].strip(),
        }
    normalized: ExperimentConfig = {
        "name": name.strip()[:80],
        "force_direct": force_direct,
        "enabled_capabilities": list(dict.fromkeys(enabled)),
        "model": model,
        "vision_model": vision_model,
        "pipeline_version": version,
        "improvements": list(dict.fromkeys(improvements)),
        "reasoning_mode": mode,
        "thinking_tokens": thinking,
        "solution_tokens": solution,
        "sampling_profile": sampling,
        "seed": seed,
    }
    if architecture is not None:
        normalized["architecture"] = architecture.strip()
    return normalized


def improvement_enabled(experiment: dict | None, improvement: str) -> bool:
    """Check an explicit feature switch, including nested tool calls in a run."""
    if experiment is None:
        from huggingface_agents_langgraph.run_tracking import current_trace

        trace = current_trace.get()
        experiment = trace.experiment if trace else {}
    return experiment.get("pipeline_version") in {
        "3",
        "3.1",
    } and improvement in experiment.get("improvements", [])


def is_capability_enabled(experiment: ExperimentConfig, capability: str) -> bool:
    """Return whether a capability is available in this experiment."""
    return (
        not experiment["force_direct"]
        and capability in experiment["enabled_capabilities"]
    )
