"""Archive the V2 source and local experiment evidence without credentials."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from uuid import UUID

from huggingface_agents_langgraph.pipeline_versions import (
    V2_REFERENCE_ID,
    V2_REFERENCE_NAME,
    V2_REFERENCE_REVISION,
)


def verify_archive(directory: Path) -> dict:
    """Verify every archived file against the manifest's SHA-256 digest."""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["sha256"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Archive member is outside the baseline directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Baseline integrity check failed: {name}")
    return manifest


def archive_reference(repository: Path, runtime: Path) -> Path:
    """Freeze source and original records; never overwrite an existing archive."""
    directory = runtime / "baselines" / "v2-reference"
    if (directory / "manifest.json").exists():
        verify_archive(directory)
        return directory

    experiment_path = runtime / "experiments" / f"{V2_REFERENCE_ID}.json"
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    answers = experiment["answers"]
    if experiment["id"] != V2_REFERENCE_ID or len(answers) != 20:
        raise ValueError("The V2 reference must contain its twenty original answers")
    records = {f"experiments/{experiment_path.name}": experiment_path.read_bytes()}
    for answer in answers:
        run_id = str(UUID(answer["run_id"]))
        path = runtime / "runs" / f"{run_id}.json"
        data = path.read_bytes()
        run = json.loads(data)
        if (
            run["id"] != run_id
            or run["pipeline_version"] != "2"
            or run["task"]["task_id"] != answer["task_id"]
        ):
            raise ValueError("A reference trace does not match the V2 experiment")
        records[f"runs/{path.name}"] = data

    directory.mkdir(parents=True, exist_ok=True)
    source = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repository.resolve().as_posix()}",
            "archive",
            "--format=zip",
            V2_REFERENCE_REVISION,
        ],
        cwd=repository,
        capture_output=True,
        check=True,
        timeout=30,
    ).stdout
    records["source.zip"] = source
    for name, data in records.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"Refusing to replace an existing baseline file: {name}")
        path.write_bytes(data)
    manifest = {
        "name": V2_REFERENCE_NAME,
        "experiment_id": V2_REFERENCE_ID,
        "pipeline_version": "2",
        "source_revision": V2_REFERENCE_REVISION,
        "config": experiment["config"],
        "score": experiment.get("score"),
        "local_score": experiment.get("local_score"),
        "average_duration_seconds": experiment.get("average_duration_seconds"),
        "sha256": {
            name: hashlib.sha256(data).hexdigest() for name, data in records.items()
        },
        "limitations": [
            "Weights, media, dataset caches and server binaries are not archived.",
            "Unrecorded historical settings cannot be inferred from current defaults.",
            "Credentials and environment files are not included.",
        ],
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    verify_archive(directory)
    return directory


def main() -> None:
    """Create or verify the reference archive without running the agent."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--runtime", type=Path, default=Path(".runtime"))
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    directory = args.runtime / "baselines" / "v2-reference"
    if args.verify:
        verify_archive(directory)
    else:
        directory = archive_reference(args.repository, args.runtime)
    print(f"Verified V2 reference: {directory}")


if __name__ == "__main__":
    main()
