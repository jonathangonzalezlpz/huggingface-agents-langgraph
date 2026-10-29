"""Experiment profiles for selectively enabling graph capabilities."""

from typing import Literal, TypedDict

CAPABILITIES = ("code", "spreadsheet", "document", "multimedia", "web")
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


DEFAULT_EXPERIMENT: ExperimentConfig = {
    "name": "Completo",
    "force_direct": False,
    "enabled_capabilities": list(CAPABILITIES),
    "model": None,
}


def normalize_experiment(value: object) -> ExperimentConfig:
    """Validate user-supplied experiment settings and fill safe defaults."""
    if value is None:
        return dict(DEFAULT_EXPERIMENT)
    if not isinstance(value, dict):
        raise ValueError("experiment must be an object")

    name = value.get("name", "Personalizado")
    force_direct = value.get("force_direct", False)
    enabled = value.get("enabled_capabilities", list(CAPABILITIES))
    model = value.get("model")
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
    }


def is_capability_enabled(experiment: ExperimentConfig, capability: str) -> bool:
    """Return whether a capability is available in this experiment."""
    return (
        not experiment["force_direct"]
        and capability in experiment["enabled_capabilities"]
    )
