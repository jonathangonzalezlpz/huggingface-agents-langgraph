"""The frontend demo fixture must mirror what the real backend returns."""

import json
from pathlib import Path

from huggingface_agents_langgraph.demo_data import build_demo_data

DEMO_FILE = (
    Path(__file__).parents[1]
    / "frontend"
    / "src"
    / "adapters"
    / "memory"
    / "demo-data.json"
)


def test_demo_data_contains_the_builtin_pipeline_catalog_and_validation():
    data = build_demo_data()
    assert set(data) == {"catalog", "architecture", "validation"}
    assert data["architecture"]["id"] == "builtin:gaia_v31"
    assert data["architecture"]["read_only"] is True
    assert data["validation"]["is_valid"] is True
    assert len(data["catalog"]["nodes"]) == 16


def test_committed_demo_fixture_is_current():
    committed = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
    assert committed == build_demo_data(), (
        "Regenerate with: uv run python -m huggingface_agents_langgraph.demo_data"
    )
