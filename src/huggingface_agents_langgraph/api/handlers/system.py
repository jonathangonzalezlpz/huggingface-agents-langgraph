"""What the backend can run right now: status of the services and the models."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import urlopen

from huggingface_agents_langgraph.api.http import Request, Response, ok
from huggingface_agents_langgraph.api.router import Router
from huggingface_agents_langgraph.config import LLM_BASE_URL, MODEL_SERVER_MODE
from huggingface_agents_langgraph.llm import get_available_models
from huggingface_agents_langgraph.model_server import gpu_memory, model_inventory
from huggingface_agents_langgraph.multimedia_processing import (
    get_gpu_status,
    get_multimedia_model_status,
)
from huggingface_agents_langgraph.resource_tracking import host_memory

LLM_NAME = "LLM razonador"
PROBE_TIMEOUT_SECONDS = 2
NOT_READY = {"downloading", "incomplete"}


def _is_exclusive() -> bool:
    return MODEL_SERVER_MODE == "exclusive"


def get_llm_status() -> dict[str, str]:
    """Probe llama.cpp without sending a request that could wake the model."""
    parsed = urlsplit(LLM_BASE_URL)
    root_path = parsed.path.rstrip("/").removesuffix("/v1")
    server_url = urlunsplit((parsed.scheme, parsed.netloc, root_path, "", "")).rstrip(
        "/"
    )

    try:
        with urlopen(f"{server_url}/health", timeout=PROBE_TIMEOUT_SECONDS) as response:
            health_status = response.status
    except HTTPError as error:
        state = "loading" if error.code == 503 else "unavailable"
        return {"state": state, "name": LLM_NAME}
    except (URLError, TimeoutError, OSError):
        return {"state": "unavailable", "name": LLM_NAME}

    try:
        with urlopen(f"{server_url}/props", timeout=PROBE_TIMEOUT_SECONDS) as response:
            properties = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        state = "ready" if health_status == 200 else "loading"
        return {"state": state, "name": LLM_NAME}
    return {
        "state": "sleeping" if properties.get("is_sleeping") else "ready",
        "name": LLM_NAME,
    }


def _exclusive_cards(inventory: list[dict]) -> list[dict]:
    """The cards shown for the exclusive router and the CPU-side multimedia models."""
    cards = [
        {
            "name": "LLM / VLM" if model["vision"] else LLM_NAME,
            "model": model["model_id"],
            "state": model["state"],
        }
        for model in inventory
    ] or [{"name": "Router LLM / VLM", "state": "unavailable"}]
    media = [
        item | {"name": item["name"] + " · CPU"}
        for item in get_multimedia_model_status()
    ]
    return [*cards, *media]


def get_status(request: Request) -> Response:
    inventory = model_inventory() if _is_exclusive() else []
    status = {
        "llm": get_llm_status()
        if not _is_exclusive()
        else {
            "state": "ready" if inventory else "unavailable",
            "name": "Router · GPU exclusiva",
        },
        "gpu": get_gpu_status(),
        "host_memory": host_memory(),
        "multimedia_models": get_multimedia_model_status(),
    }
    if _is_exclusive():
        status |= {
            "model_cards": _exclusive_cards(inventory),
            "gpu_memory": gpu_memory(),
            "gpu_policy": "exclusive",
        }
    return ok(status)


def get_models(request: Request) -> Response:
    inventory = model_inventory() if _is_exclusive() else []
    ready = {item["model_id"] for item in inventory if item["state"] not in NOT_READY}
    models = get_available_models()
    if _is_exclusive():
        models = [
            model
            for model in models
            if model["provider"] == "configured" and model["model_id"] in ready
        ]
    vision = [
        {"provider": "configured", "model_id": item["model_id"]}
        for item in inventory
        if item["vision"] and item["model_id"] in ready
    ]
    return ok({"models": models, "vision_models": vision})


def register(router: Router) -> None:
    router.add("GET", "/api/status")(get_status)
    router.add("GET", "/api/models")(get_models)
