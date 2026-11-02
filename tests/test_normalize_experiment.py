"""Characterization of ``normalize_experiment``: defaults, messages and check order."""

import pytest

from huggingface_agents_langgraph.domain.experiments import (
    DEFAULT_EXPERIMENT,
    normalize_experiment,
)


def test_none_gives_an_independent_copy_of_the_default():
    first = normalize_experiment(None)
    assert first == DEFAULT_EXPERIMENT
    first["enabled_capabilities"].append("x")
    assert normalize_experiment(None) == DEFAULT_EXPERIMENT


def test_an_empty_object_fills_the_documented_defaults():
    assert normalize_experiment({}) == {
        "name": "Personalizado",
        "force_direct": False,
        "enabled_capabilities": [
            "code",
            "spreadsheet",
            "document",
            "multimedia",
            "web",
        ],
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


def test_version_3_1_switches_sampling_and_seed_defaults():
    config = normalize_experiment({"pipeline_version": "3.1"})
    assert (config["sampling_profile"], config["seed"]) == ("controlled", 42)
    explicit = normalize_experiment(
        {"pipeline_version": "3.1", "sampling_profile": "author", "seed": None}
    )
    assert (explicit["sampling_profile"], explicit["seed"]) == ("author", None)


def test_values_are_cleaned():
    config = normalize_experiment(
        {
            "name": "  " + "n" * 100 + "  ",
            "enabled_capabilities": ["web", "code", "web"],
            "pipeline_version": "3",
            "improvements": ["web_sources", "web_sources"],
            "model": {"provider": "ollama", "model_id": " m ", "extra": 1},
            "vision_model": {"provider": "configured", "model_id": " v ", "x": 1},
            "architecture": " arch ",
        }
    )
    assert config["name"] == "n" * 80
    assert config["enabled_capabilities"] == ["web", "code"]
    assert config["improvements"] == ["web_sources"]
    assert config["model"] == {"provider": "ollama", "model_id": "m"}
    assert config["vision_model"] == {"provider": "configured", "model_id": "v"}
    assert config["architecture"] == "arch"


def test_architecture_is_absent_unless_given():
    assert "architecture" not in normalize_experiment({})


BAD = [
    ("x", "must be an object"),
    ({"architecture": ""}, "architecture must be a non-empty"),
    ({"architecture": 3}, "architecture must be a non-empty"),
    ({"architecture": "a" * 101}, "architecture must be a non-empty"),
    ({"sampling_profile": "wild"}, "Unsupported sampling profile"),
    ({"seed": True}, "seed must be"),
    ({"seed": -1}, "seed must be"),
    ({"seed": 2**32}, "seed must be"),
    ({"pipeline_version": "4"}, "Unsupported pipeline version"),
    ({"improvements": "x", "pipeline_version": "3"}, "Invalid improvements"),
    ({"improvements": ["nope"], "pipeline_version": "3"}, "Invalid improvements"),
    ({"improvements": ["web_sources"]}, "Invalid improvements"),
    ({"reasoning_mode": "x"}, "Unsupported reasoning mode"),
    ({"thinking_tokens": 8193}, "Token budgets"),
    ({"solution_tokens": True}, "Token budgets"),
    ({"solution_tokens": 127}, "at least 128"),
    ({"name": " "}, "name must be"),
    ({"name": 3}, "name must be"),
    ({"force_direct": 1}, "force_direct must be"),
    ({"enabled_capabilities": "web"}, "unknown capability"),
    ({"enabled_capabilities": ["teleport"]}, "unknown capability"),
    ({"model": "m"}, "model must be an object"),
    ({"model": {"provider": "x", "model_id": "m"}}, "provider is unsupported"),
    ({"model": {"provider": "ollama", "model_id": " "}}, "model_id must be"),
    ({"model": {"provider": "ollama", "model_id": "m" * 201}}, "model_id must be"),
    ({"vision_model": "v"}, "vision_model is invalid"),
    ({"vision_model": {"provider": "x", "model_id": "v"}}, "vision_model is invalid"),
    (
        {"vision_model": {"provider": "ollama", "model_id": ""}},
        "vision_model is invalid",
    ),
    ({"vision_model": {"provider": "ollama"}}, "vision_model is invalid"),
]


@pytest.mark.parametrize(("value", "message"), BAD)
def test_invalid_settings_are_refused_with_a_specific_message(value, message):
    with pytest.raises(ValueError, match=message):
        normalize_experiment(value)


ORDER = [
    ({"architecture": "", "sampling_profile": "x"}, "architecture"),
    ({"sampling_profile": "x", "seed": -1}, "sampling"),
    ({"seed": -1, "pipeline_version": "9"}, "seed"),
    ({"pipeline_version": "9", "improvements": "x"}, "pipeline version"),
    ({"improvements": "x", "reasoning_mode": "x"}, "improvements"),
    ({"reasoning_mode": "x", "thinking_tokens": -1}, "reasoning mode"),
    ({"thinking_tokens": -1, "solution_tokens": 1}, "Token budgets"),
    ({"solution_tokens": 1, "name": ""}, "at least 128"),
    ({"name": "", "force_direct": 1}, "name"),
    ({"force_direct": 1, "enabled_capabilities": 1}, "force_direct"),
    ({"enabled_capabilities": 1, "model": 1}, "capability"),
    ({"model": 1, "vision_model": 1}, "experiment.model must"),
]


@pytest.mark.parametrize(("value", "first"), ORDER)
def test_the_first_failing_check_wins(value, first):
    with pytest.raises(ValueError) as error:
        normalize_experiment(value)
    assert first.lower() in str(error.value).lower()
