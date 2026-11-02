"""Run paired feature ablations and a combined pipeline evaluation."""

import argparse
import json
from uuid import uuid4

from huggingface_agents_langgraph.adapters.records import read_record
from huggingface_agents_langgraph.application.experiment_run import (
    run_experiment,
    variant_config,
)
from huggingface_agents_langgraph.domain.experiments import IMPROVEMENTS
from huggingface_agents_langgraph.domain.pipeline_versions import V2_REFERENCE_ID


def main() -> None:
    """Run actual ablations on the frozen question set without official submission."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=["baseline", "combined", *IMPROVEMENTS],
        default=["baseline", *IMPROVEMENTS, "combined"],
    )
    parser.add_argument("--group-id", default=str(uuid4()))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--resume", help="UUID of a partially completed experiment")
    parser.add_argument(
        "--architecture",
        help="Stored architecture version (or builtin:gaia_v31) to compile and run",
    )
    args = parser.parse_args()
    reference = read_record("experiments", V2_REFERENCE_ID)
    if not 1 <= args.limit <= 20:
        parser.error("limit must be between 1 and 20")
    tasks = reference["answers"][: args.limit]
    if args.resume:
        record = read_record("experiments", args.resume)
        run_experiment(
            tasks,
            record["config"],
            group_id=record["evaluation_group_id"],
            record=record,
        )
        return
    for variant in args.variants:
        result = run_experiment(
            tasks,
            variant_config(reference["config"], variant, args.architecture),
            group_id=args.group_id,
        )
        print(
            json.dumps(
                {
                    "experiment_id": result["id"],
                    "variant": variant,
                    "metrics": result["metrics"],
                    "score": result.get("local_score"),
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
