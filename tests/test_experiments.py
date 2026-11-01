import pytest

from huggingface_agents_langgraph.experiments import (
    CAPABILITIES,
    DEFAULT_EXPERIMENT,
    is_capability_enabled,
    normalize_experiment,
)
from huggingface_agents_langgraph.graph import (
    _route_after_preprocessing,
    _route_after_router,
)
from huggingface_agents_langgraph.routing import router


def test_default_experiment_enables_all_capabilities() -> None:
    assert normalize_experiment(None) == DEFAULT_EXPERIMENT
    assert all(
        is_capability_enabled(DEFAULT_EXPERIMENT, capability)
        for capability in CAPABILITIES
    )


def test_experiment_rejects_unknown_capability() -> None:
    with pytest.raises(ValueError, match="unknown capability"):
        normalize_experiment({"enabled_capabilities": ["chess"]})


def test_experiment_keeps_selected_local_model() -> None:
    model = {"provider": "ollama", "model_id": "qwen2-local:latest"}

    experiment = normalize_experiment({"model": model})

    assert experiment["model"] == model


def test_experiment_rejects_unknown_model_provider() -> None:
    with pytest.raises(ValueError, match="provider is unsupported"):
        normalize_experiment({"model": {"provider": "remote", "model_id": "model-id"}})


def test_direct_experiment_skips_attachment_download() -> None:
    state = {
        "task_id": "task-1",
        "question": "What is this?",
        "file_name": "document.pdf",
        "experiment": normalize_experiment({"force_direct": True}),
    }

    assert _route_after_preprocessing(state) == "skip_attachment"


def test_disabled_document_skips_attachment_download() -> None:
    state = {
        "task_id": "task-1",
        "question": "What is this?",
        "file_name": "document.pdf",
        "experiment": normalize_experiment({"enabled_capabilities": ["web", "code"]}),
    }

    assert _route_after_preprocessing(state) == "skip_attachment"


def test_disabled_attachment_route_falls_back_to_direct() -> None:
    state = {
        "task_id": "task-1",
        "question": "What is in the spreadsheet?",
        "file_name": "data.xlsx",
        "route": "spreadsheet",
        "experiment": normalize_experiment(
            {"enabled_capabilities": ["web", "document"]}
        ),
    }

    assert _route_after_router(state) == "direct"


def test_router_sends_attachment_direct_when_capability_disabled() -> None:
    state = {
        "task_id": "task-1",
        "question": "Read the PDF",
        "file_name": "file.pdf",
        "experiment": normalize_experiment(
            {"enabled_capabilities": ["web", "spreadsheet"]}
        ),
    }

    assert router(state) == {"route": "direct"}


def test_router_sends_web_question_direct_when_web_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        "huggingface_agents_langgraph.routing._classify_question",
        lambda _question, _model=None: "web",
    )
    state = {
        "task_id": "task-1",
        "question": "What happened yesterday?",
        "file_name": "",
        "experiment": normalize_experiment(
            {"enabled_capabilities": ["code", "document"]}
        ),
    }

    assert router(state) == {"route": "direct"}


def test_architecture_is_omitted_unless_requested() -> None:
    assert "architecture" not in normalize_experiment({"name": "plain"})
    assert "architecture" not in normalize_experiment({"architecture": None})


def test_architecture_reference_is_kept_and_trimmed() -> None:
    experiment = normalize_experiment({"architecture": "  builtin:gaia_v31 "})
    assert experiment["architecture"] == "builtin:gaia_v31"


@pytest.mark.parametrize("value", ["", "   ", 7, ["x"], "x" * 101])
def test_invalid_architecture_reference_is_rejected(value) -> None:
    with pytest.raises(ValueError, match="architecture"):
        normalize_experiment({"architecture": value})


def test_variant_config_can_carry_an_architecture_reference() -> None:
    from huggingface_agents_langgraph.experiment_runner import variant_config

    reference = normalize_experiment(None)
    assert "architecture" not in variant_config(reference, "combined")
    configured = variant_config(reference, "combined", architecture="builtin:gaia_v31")
    assert configured["architecture"] == "builtin:gaia_v31"
