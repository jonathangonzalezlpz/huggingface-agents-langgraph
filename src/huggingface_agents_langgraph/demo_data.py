"""Fixture data for the Studio demo mode, generated from the real backend.

The demo never contains benchmark questions, answers or run records.
"""

import json
from pathlib import Path

from huggingface_agents_langgraph.architecture_store import (
    BUILTIN_V31_ID,
    get_architecture,
    get_catalog,
    validate_definition,
)

DEMO_FILE = (
    Path(__file__).parents[2]
    / "frontend"
    / "src"
    / "adapters"
    / "memory"
    / "demo-data.json"
)


def build_demo_data() -> dict:
    """Catalog, built-in architecture and its validation as the API returns them."""
    architecture = get_architecture(BUILTIN_V31_ID)
    return {
        "catalog": get_catalog(),
        "architecture": architecture,
        "validation": validate_definition(architecture["definition"]),
    }


def main() -> None:
    DEMO_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEMO_FILE.write_text(
        json.dumps(build_demo_data(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {DEMO_FILE}")


if __name__ == "__main__":
    main()
