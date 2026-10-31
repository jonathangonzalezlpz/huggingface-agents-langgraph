"""Manage local llama.cpp models without waking them during status polling."""

import argparse
import json
import shutil
import subprocess
from time import perf_counter, sleep
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from huggingface_agents_langgraph.config import (
    LLM_BASE_URL,
    MODEL_CACHE_RAM_MIB,
    MODEL_LOAD_TIMEOUT_SECONDS,
)

TEXT_REFERENCE = "Qwen/Qwen3-8B-GGUF:Q5_K_M"
TEXT_LARGE = "Qwen/Qwen3-14B-GGUF:Q5_K_M"
VISION_LARGE = "Qwen/Qwen3-VL-8B-Instruct-GGUF:Q4_K_M"
SHARED_MODEL = "unsloth/Qwen3.5-9B-GGUF:Q5_K_M"
SHARED_MODEL_HIGH_PRECISION = "unsloth/Qwen3.5-9B-GGUF:Q8_0"
VISION_MODELS = {VISION_LARGE, SHARED_MODEL, SHARED_MODEL_HIGH_PRECISION}


def server_root() -> str:
    parsed = urlsplit(LLM_BASE_URL)
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/").removesuffix("/v1"),
            "",
            "",
        )
    )


def model_request(
    endpoint: str, payload: dict | None = None, timeout: float = 3
) -> dict:
    """Call the local router management API; never issue a generation request."""
    request = Request(server_root() + endpoint)
    if payload is not None:
        request = Request(
            server_root() + endpoint,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def model_inventory() -> list[dict]:
    """Return safe model metadata; listing models does not load their weights."""
    try:
        models = model_request("/models").get("data", [])
    except (OSError, URLError, ValueError):
        return []
    return [
        {
            "model_id": item["id"],
            "provider": "configured",
            "state": item.get("status", {}).get("value", "unknown"),
            "vision": "image"
            in item.get("architecture", {}).get("input_modalities", [])
            or item["id"] in VISION_MODELS,
        }
        for item in models
        if isinstance(item.get("id"), str)
    ]


def ensure_model(model_id: str) -> float:
    """Load a selected model explicitly and return observed wall time."""
    models = model_inventory()
    selected = next((model for model in models if model["model_id"] == model_id), None)
    if selected is None:
        raise ValueError(f"Model is not available in the local router: {model_id}")
    if selected["state"] in {"downloading", "incomplete"}:
        raise RuntimeError(f"Model download is not complete: {model_id}")
    started = perf_counter()
    deadline = started + MODEL_LOAD_TIMEOUT_SECONDS
    if selected["state"] not in {"loaded", "ready"}:
        if selected["state"] == "sleeping":
            model_request(
                "/models/unload", {"model": model_id}, MODEL_LOAD_TIMEOUT_SECONDS
            )
            _wait_for_model_state(model_id, {"unloaded"}, deadline)
        if selected["state"] != "loading":
            model_request(
                "/models/load", {"model": model_id}, MODEL_LOAD_TIMEOUT_SECONDS
            )
        _wait_for_model_state(model_id, {"loaded", "ready"}, deadline)
    return perf_counter() - started


def _wait_for_model_state(model_id: str, states: set[str], deadline: float) -> None:
    while perf_counter() < deadline:
        current = next(
            (item for item in model_inventory() if item["model_id"] == model_id), {}
        )
        if current.get("state") in states:
            return
        sleep(0.2)
    raise TimeoutError(f"Model did not reach the requested state: {model_id}")


def gpu_memory() -> dict:
    """Read device memory through the driver without allocating CUDA buffers."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        name, *measurements = result.stdout.splitlines()[0].split(",")
        used, total, utilization = [int(item.strip()) for item in measurements]
        return {
            "name": name.strip(),
            "used_mib": used,
            "total_mib": total,
            "utilization_percent": utilization,
        }
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return {}


def main() -> None:
    """Start an exclusive router or manage its public model downloads."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["serve", "download", "status"])
    parser.add_argument(
        "--models", nargs="+", default=[SHARED_MODEL, TEXT_LARGE, VISION_LARGE]
    )
    parser.add_argument("--context", type=int, default=16384)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--cache-ram", type=int, default=MODEL_CACHE_RAM_MIB)
    parser.add_argument("--sleep-idle-seconds", type=int, default=300)
    args = parser.parse_args()
    if args.cache_ram < -1:
        parser.error("cache-ram must be -1 or nonnegative")
    if args.command == "serve":
        executable = shutil.which("llama")
        if executable is None:
            parser.error("llama.cpp is not installed")
        raise SystemExit(
            subprocess.call(
                [
                    executable,
                    "serve",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.port),
                    "--models-max",
                    "1",
                    "--ctx-size",
                    str(args.context),
                    "--parallel",
                    "1",
                    "--sleep-idle-seconds",
                    str(args.sleep_idle_seconds),
                    "--cache-ram",
                    str(args.cache_ram),
                    "--no-webui",
                ]
            )
        )
    if args.command == "download":
        for model in args.models:
            print(
                json.dumps(
                    {
                        "model": model,
                        "request": model_request("/models", {"model": model}, 15),
                    }
                ),
                flush=True,
            )
    else:
        print(json.dumps({"models": model_inventory(), "gpu": gpu_memory()}, indent=2))


if __name__ == "__main__":
    main()
