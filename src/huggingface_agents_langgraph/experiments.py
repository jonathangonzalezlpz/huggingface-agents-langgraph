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
    pipeline_version: NotRequired[str]
    improvements: NotRequired[list[str]]
    reasoning_mode: NotRequired[str]
    thinking_tokens: NotRequired[int]
    solution_tokens: NotRequired[int]


DEFAULT_EXPERIMENT: ExperimentConfig = {
    "name": "Completo",
    "force_direct": False,
    "enabled_capabilities": list(CAPABILITIES),
    "model": None,
    "pipeline_version": "2",
    "improvements": [],
    "reasoning_mode": "bounded",
    "thinking_tokens": 512,
    "solution_tokens": 1024,
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
    version = value.get("pipeline_version", "2")
    improvements = value.get("improvements", [])
    mode = value.get("reasoning_mode", "bounded")
    thinking = value.get("thinking_tokens", 512)
    solution = value.get("solution_tokens", 1024)
    if version not in {"2", "3"}:
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
    return {
        "name": name.strip()[:80],
        "force_direct": force_direct,
        "enabled_capabilities": list(dict.fromkeys(enabled)),
        "model": model,
        "pipeline_version": version,
        "improvements": list(dict.fromkeys(improvements)),
        "reasoning_mode": mode,
        "thinking_tokens": thinking,
        "solution_tokens": solution,
    }


def improvement_enabled(experiment: dict | None, improvement: str) -> bool:
    """Check an explicit feature switch, including nested tool calls in a run."""
    if experiment is None:
        from huggingface_agents_langgraph.run_tracking import current_trace

        trace = current_trace.get()
        experiment = trace.experiment if trace else {}
    return experiment.get("pipeline_version") == "3" and improvement in experiment.get(
        "improvements", []
    )


def is_capability_enabled(experiment: ExperimentConfig, capability: str) -> bool:
    """Return whether a capability is available in this experiment."""
    return (
        not experiment["force_direct"]
        and capability in experiment["enabled_capabilities"]
    )
