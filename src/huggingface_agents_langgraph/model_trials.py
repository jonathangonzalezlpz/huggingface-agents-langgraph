"""Compare local model choices with fixed pipeline settings and persisted results."""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from huggingface_agents_langgraph.config import MODEL_SERVER_MODE, RUNTIME_DIRECTORY
from huggingface_agents_langgraph.experiment_runner import (
    run_experiment,
    source_identity,
)
from huggingface_agents_langgraph.experiments import normalize_experiment
from huggingface_agents_langgraph.llm import chat_completion
from huggingface_agents_langgraph.model_server import (
    SHARED_MODEL,
    SHARED_MODEL_HIGH_PRECISION,
    TEXT_LARGE,
    TEXT_REFERENCE,
    VISION_LARGE,
    gpu_memory,
    model_inventory,
)
from huggingface_agents_langgraph.pipeline_versions import V2_REFERENCE_ID
from huggingface_agents_langgraph.run_tracking import (
    RunTrace,
    current_trace,
    read_record,
)

MODEL_PAIRS = {
    "control": (TEXT_REFERENCE, None),
    "reasoner": (SHARED_MODEL, None),
    "vision": (TEXT_REFERENCE, SHARED_MODEL),
    "shared": (SHARED_MODEL, SHARED_MODEL),
    "large": (TEXT_LARGE, SHARED_MODEL),
    "specialist": (SHARED_MODEL, VISION_LARGE),
    "precision": (SHARED_MODEL_HIGH_PRECISION, SHARED_MODEL_HIGH_PRECISION),
}
TEXT_PROBES = (
    ("Return only the capital of Italy.", "Rome"),
    (
        "Calculate (17 * 23) - 8. Return only the integer, with no explanation.",
        "383",
    ),
    (
        "Sort these words alphabetically: pear, apple, kiwi. "
        "Return only a comma-separated list.",
        "apple, kiwi, pear",
    ),
)


def trial_config(variant: str) -> dict:
    """Change only the model pair in an otherwise fixed V3.1 configuration."""
    reasoner, vision = MODEL_PAIRS[variant]
    return normalize_experiment(
        {
            "name": f"V3.1 · Modelos · {variant}",
            "pipeline_version": "3.1",
            "model": {"provider": "configured", "model_id": reasoner},
            "vision_model": {"provider": "configured", "model_id": vision}
            if vision
            else None,
            "sampling_profile": "controlled",
            "seed": 42,
            "reasoning_mode": "bounded",
            "thinking_tokens": 512,
            "solution_tokens": 1024,
            "improvements": [
                "reasoning_control",
                "answer_contract",
                "multimedia_tools",
                "calculation_tools",
            ],
        }
    )


def _probe(config: dict, messages: list[dict]) -> dict:
    trace = RunTrace(experiment=config)
    token = current_trace.set(trace)
    started = perf_counter()
    try:
        answer = chat_completion(
            messages, model=config["model"], max_tokens=128, thinking=False
        )
        result = {"answer": answer}
    except Exception as error:
        result = {"error": str(error)}
    finally:
        current_trace.reset(token)
    return result | {
        "duration_seconds": round(perf_counter() - started, 4),
        "load_seconds": sum(call.get("model_load_seconds", 0) for call in trace.calls),
        "server_timings": trace.calls[-1].get("response", {}).get("timings", {})
        if trace.calls
        else {},
        "gpu": gpu_memory(),
        "resident_models": [
            item["model_id"]
            for item in model_inventory()
            if item["state"] in {"loaded", "ready"}
        ],
    }


def run_smoke() -> dict:
    """Check text, native vision, and residency before committing to full batteries."""
    from PIL import Image, ImageDraw

    from huggingface_agents_langgraph.multimedia_processing import _run_vision_model

    record = {
        "created_at": datetime.now(UTC).isoformat(),
        "source_identity": source_identity(),
        "scope": "Synthetic compatibility checks; not a GAIA score",
        "text": [],
        "vision": [],
    }
    directory = Path(RUNTIME_DIRECTORY) / "v31-evaluation"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / "smoke.json"

    def save():
        destination.write_text(json.dumps(record, indent=2), encoding="utf-8")

    for model in (TEXT_REFERENCE, SHARED_MODEL, TEXT_LARGE):
        config = trial_config("control") | {
            "model": {"provider": "configured", "model_id": model}
        }
        for prompt, expected in TEXT_PROBES:
            result = _probe(config, [{"role": "user", "content": prompt}])
            result.update(model=model, prompt=prompt, expected=expected)
            result["correct"] = result.get("answer", "").strip() == expected
            record["text"].append(result)
            save()
            print(json.dumps(result), flush=True)
    image = Image.new("RGB", (512, 384), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 150, 200, 300), fill="red")
    draw.ellipse((300, 150, 450, 300), fill="blue")
    for model in (SHARED_MODEL, VISION_LARGE):
        config = trial_config("shared") | {
            "vision_model": {"provider": "configured", "model_id": model}
        }
        trace = RunTrace(experiment=config)
        token = current_trace.set(trace)
        started = perf_counter()
        try:
            result = {
                "answer": _run_vision_model(
                    image,
                    "Describe the shapes, their colors and their relative positions.",
                )
            }
        except Exception as error:
            result = {"error": str(error)}
        finally:
            current_trace.reset(token)
        result.update(
            model=model,
            duration_seconds=round(perf_counter() - started, 4),
            load_seconds=sum(call.get("model_load_seconds", 0) for call in trace.calls),
            server_timings=trace.calls[-1].get("response", {}).get("timings", {})
            if trace.calls
            else {},
            gpu=gpu_memory(),
            resident_models=[
                item["model_id"]
                for item in model_inventory()
                if item["state"] in {"loaded", "ready"}
            ],
        )
        record["vision"].append(result)
        save()
        print(json.dumps(result), flush=True)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["smoke", "evaluate"])
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=list(MODEL_PAIRS),
        default=["vision", "shared", "large", "specialist"],
    )
    parser.add_argument("--group-id", default="v31-native-models-20261030")
    parser.add_argument(
        "--name-prefix", help="Optional display name for this trial series"
    )
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if MODEL_SERVER_MODE != "exclusive":
        parser.error("Model comparisons require MODEL_SERVER_MODE=exclusive")
    if args.stage == "smoke":
        run_smoke()
        return
    if not 1 <= args.limit <= 20:
        parser.error("limit must be between 1 and 20")
    if len(args.variants) > 1:
        for variant in args.variants:
            command = [
                sys.executable,
                "-m",
                "huggingface_agents_langgraph.model_trials",
                "evaluate",
                "--variants",
                variant,
                "--group-id",
                args.group_id,
                "--limit",
                str(args.limit),
            ]
            if args.name_prefix:
                command.extend(["--name-prefix", args.name_prefix])
            subprocess.run(command, check=True)
        return
    tasks = read_record("experiments", V2_REFERENCE_ID)["answers"][: args.limit]
    for variant in args.variants:
        config = trial_config(variant)
        if args.name_prefix:
            config = normalize_experiment(
                config | {"name": f"{args.name_prefix} · {variant}"}
            )
        result = run_experiment(tasks, config, group_id=args.group_id)
        print(
            json.dumps(
                {
                    "id": result["id"],
                    "variant": variant,
                    "metrics": result["metrics"],
                    "score": result.get("local_score"),
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
