import json
from io import BytesIO

import pytest

from huggingface_agents_langgraph import llm, model_server, multimedia_processing
from huggingface_agents_langgraph.experiments import normalize_experiment
from huggingface_agents_langgraph.model_trials import MODEL_PAIRS, trial_config
from huggingface_agents_langgraph.run_tracking import RunTrace, current_trace


def test_inventory_does_not_load_models_or_expose_local_paths(monkeypatch):
    requests = []

    def request(endpoint):
        requests.append(endpoint)
        return {
            "data": [
                {
                    "id": model_server.SHARED_MODEL,
                    "path": "private-path",
                    "status": {"value": "unloaded"},
                }
            ]
        }

    monkeypatch.setattr(model_server, "model_request", request)
    models = model_server.model_inventory()
    assert requests == ["/models"]
    assert models[0]["vision"] is True
    assert models[0]["state"] == "unloaded"
    assert "path" not in models[0]


def test_already_loaded_model_does_not_trigger_another_load(monkeypatch):
    monkeypatch.setattr(
        model_server,
        "model_inventory",
        lambda: [
            {
                "model_id": "same",
                "state": "loaded",
            }
        ],
    )
    monkeypatch.setattr(
        model_server, "model_request", lambda *_a, **_k: pytest.fail("Unexpected load")
    )
    assert model_server.ensure_model("same") >= 0


def test_model_loading_waits_until_router_reports_residency(monkeypatch):
    states = iter(["unloaded", "loading", "loaded"])
    monkeypatch.setattr(
        model_server,
        "model_inventory",
        lambda: [
            {
                "model_id": "next",
                "state": next(states),
            }
        ],
    )
    requests = []
    monkeypatch.setattr(
        model_server, "model_request", lambda *args: requests.append(args)
    )
    monkeypatch.setattr(model_server, "sleep", lambda _seconds: None)
    assert model_server.ensure_model("next") >= 0
    assert requests == [
        ("/models/load", {"model": "next"}, model_server.MODEL_LOAD_TIMEOUT_SECONDS)
    ]


def test_incomplete_download_cannot_start_inference(monkeypatch):
    monkeypatch.setattr(
        model_server,
        "model_inventory",
        lambda: [
            {
                "model_id": "pending",
                "state": "incomplete",
            }
        ],
    )
    with pytest.raises(RuntimeError, match="download"):
        model_server.ensure_model("pending")


def test_sleeping_instance_is_stopped_before_explicit_reload(monkeypatch):
    states = iter(["sleeping", "sleeping", "unloaded", "loading", "loaded"])
    events = []

    def inventory():
        state = next(states)
        events.append(state)
        return [{"model_id": "asleep", "state": state}]

    monkeypatch.setattr(
        model_server,
        "model_inventory",
        inventory,
    )
    requests = []

    def request(*args):
        requests.append(args)
        events.append(args[0])

    monkeypatch.setattr(model_server, "model_request", request)
    monkeypatch.setattr(model_server, "sleep", lambda _seconds: None)
    model_server.ensure_model("asleep")
    assert [request[0] for request in requests] == ["/models/unload", "/models/load"]
    assert events.index("unloaded") < events.index("/models/load")


def test_reload_stops_when_the_asynchronous_unload_exceeds_its_budget(monkeypatch):
    from itertools import count

    monkeypatch.setattr(model_server, "MODEL_LOAD_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(model_server, "perf_counter", count().__next__)
    monkeypatch.setattr(
        model_server,
        "model_inventory",
        lambda: [{"model_id": "asleep", "state": "sleeping"}],
    )
    requests = []
    monkeypatch.setattr(
        model_server, "model_request", lambda *args: requests.append(args[0])
    )
    with pytest.raises(TimeoutError, match="requested state"):
        model_server.ensure_model("asleep")
    assert requests == ["/models/unload"]


def test_loading_instance_is_waited_for_without_duplicate_load(monkeypatch):
    states = iter(["loading", "loaded"])
    monkeypatch.setattr(
        model_server,
        "model_inventory",
        lambda: [{"model_id": "pending", "state": next(states)}],
    )
    monkeypatch.setattr(
        model_server, "model_request", lambda *_args: pytest.fail("Duplicate load")
    )
    model_server.ensure_model("pending")


def test_router_start_bounds_prompt_cache_and_serializes_model_residency(monkeypatch):
    import sys

    calls = []
    monkeypatch.setattr(sys, "argv", ["model_server", "serve", "--cache-ram", "512"])
    monkeypatch.setattr(model_server.shutil, "which", lambda _name: "llama")
    monkeypatch.setattr(
        model_server.subprocess, "call", lambda args: calls.append(args) or 0
    )
    with pytest.raises(SystemExit) as stopped:
        model_server.main()
    assert stopped.value.code == 0
    args = calls[0]
    assert args[args.index("--models-max") + 1] == "1"
    assert args[args.index("--cache-ram") + 1] == "512"
    assert args[args.index("--ctx-size") + 1] == "16384"
    assert args[args.index("--sleep-idle-seconds") + 1] == "300"


def test_v31_records_selected_vision_model():
    config = normalize_experiment(
        {
            "pipeline_version": "3.1",
            "vision_model": {
                "provider": "configured",
                "model_id": model_server.SHARED_MODEL,
            },
        }
    )
    assert config["vision_model"]["model_id"] == model_server.SHARED_MODEL


def test_native_vision_uses_multimodal_api_without_transformers(monkeypatch):
    Image = pytest.importorskip("PIL.Image")
    requests = []
    monkeypatch.setattr(
        llm,
        "chat_completion",
        lambda messages, **params: (
            requests.append((messages, params)) or "Observed image facts"
        ),
    )
    monkeypatch.setattr(
        multimedia_processing._vision_pipeline_manager,
        "use",
        lambda: pytest.fail("Transformers should not be loaded"),
    )
    config = normalize_experiment(
        {
            "pipeline_version": "3.1",
            "vision_model": {
                "provider": "configured",
                "model_id": model_server.SHARED_MODEL,
            },
        }
    )
    token = current_trace.set(RunTrace(experiment=config))
    try:
        answer = multimedia_processing._run_vision_model(
            Image.new("RGB", (24, 24)), "What is visible?"
        )
    finally:
        current_trace.reset(token)
    assert answer == "Observed image facts"
    messages, parameters = requests[0]
    assert parameters["model"] == config["vision_model"]
    assert parameters["thinking"] is False
    assert messages[0]["content"][0]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,"
    )


def test_exclusive_client_preloads_and_traces_load_time(monkeypatch):
    monkeypatch.setattr(llm, "MODEL_SERVER_MODE", "exclusive")
    loaded = []
    monkeypatch.setattr(
        model_server, "ensure_model", lambda model_id: loaded.append(model_id) or 1.25
    )

    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(
        llm,
        "urlopen",
        lambda *_a, **_k: Response(
            json.dumps(
                {
                    "choices": [{"message": {"content": "value"}}],
                }
            ).encode()
        ),
    )
    trace = RunTrace()
    token = current_trace.set(trace)
    try:
        llm.chat_completion(
            [{"role": "user", "content": "Task"}],
            model={
                "provider": "configured",
                "model_id": "selected",
            },
        )
    finally:
        current_trace.reset(token)
    assert loaded == ["selected"]
    assert trace.calls[0]["model_load_seconds"] == 1.25


def test_exclusive_mode_rejects_uncoordinated_ollama_models(monkeypatch):
    monkeypatch.setattr(llm, "MODEL_SERVER_MODE", "exclusive")
    with pytest.raises(ValueError, match="router"):
        llm.chat_completion(
            [{"role": "user", "content": "Task"}],
            model={
                "provider": "ollama",
                "model_id": "another-service",
            },
        )


def test_model_trials_change_models_without_changing_pipeline_settings():
    configs = [trial_config(variant) for variant in MODEL_PAIRS]
    fixed = [
        {
            key: value
            for key, value in config.items()
            if key not in {"name", "model", "vision_model"}
        }
        for config in configs
    ]
    assert all(config == fixed[0] for config in fixed)


@pytest.mark.parametrize("seed", [-1, 2**32, True, "42"])
def test_invalid_sampling_seeds_are_rejected(seed):
    with pytest.raises(ValueError, match="seed"):
        normalize_experiment({"pipeline_version": "3.1", "seed": seed})


@pytest.mark.parametrize(
    ("profile", "thinking", "temperature"),
    [("controlled", False, 0.7), ("controlled", True, 0.6), ("author", True, 1.0)],
)
def test_sampling_recipe_is_recorded_in_effective_request(
    monkeypatch, profile, thinking, temperature
):
    monkeypatch.setattr(llm, "MODEL_SERVER_MODE", "single")

    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(
        llm,
        "urlopen",
        lambda *_a, **_k: Response(b'{"choices":[{"message":{"content":"ok"}}]}'),
    )
    config = trial_config("shared") | {"sampling_profile": profile}
    trace = RunTrace(experiment=config)
    token = current_trace.set(trace)
    try:
        llm.chat_completion(
            [{"role": "user", "content": "Task"}],
            model=config["model"],
            thinking=thinking,
        )
    finally:
        current_trace.reset(token)
    request = trace.calls[0]["request"]
    assert request["temperature"] == temperature
    assert request["seed"] == 42
    assert request["top_p"] == (0.95 if thinking else 0.8)
    assert request["chat_template_kwargs"]["enable_thinking"] is thinking
