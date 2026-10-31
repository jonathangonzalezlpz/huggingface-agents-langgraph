"""Check the configuration emitted by the browser without requiring a browser."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("version", ["2", "3", "3.1"])
def test_frontend_preserves_selected_capabilities_models_and_improvements(version):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the frontend serialization check")
    source = (
        Path(__file__).parents[1] / "src/huggingface_agents_langgraph/frontend/app.js"
    ).read_text(encoding="utf-8")
    function = source[
        source.index("function getExperiment()") : source.index("function modelLabel(")
    ]
    context = {
        "activeExperimentSnapshot": None,
        "experimentName": {"value": "Custom", "dataset": {"forceDirect": "false"}},
        "experimentModel": {
            "value": json.dumps({"provider": "configured", "model_id": "reasoner"})
        },
        "experimentVisionModel": {
            "value": json.dumps({"provider": "configured", "model_id": "vision"})
        },
        "pipelineVersion": {"value": version},
        "capabilityInputs": [
            {"checked": True, "dataset": {"capability": "web"}},
            {"checked": False, "dataset": {"capability": "code"}},
        ],
        "improvementInputs": [
            {"checked": True, "dataset": {"improvement": "reasoning_control"}},
            {"checked": False, "dataset": {"improvement": "web_sources"}},
        ],
        "reasoningMode": {"value": "bounded"},
        "thinkingTokens": {"value": "512"},
        "solutionTokens": {"value": "1024"},
        "samplingProfile": {"value": "controlled"},
        "samplingSeed": {"value": "42"},
    }
    script = """
const vm = require('vm');
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const result = vm.runInNewContext(input.function + '; getExperiment()', input.context);
process.stdout.write(JSON.stringify(result));
"""
    output = subprocess.run(
        [node, "-e", script],
        input=json.dumps({"function": function, "context": context}),
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    config = json.loads(output.stdout)
    assert config["enabled_capabilities"] == ["web"]
    assert config["model"]["model_id"] == "reasoner"
    assert config["vision_model"]["model_id"] == "vision"
    assert config["improvements"] == ([] if version == "2" else ["reasoning_control"])
    assert config["seed"] == (42 if version == "3.1" else None)
