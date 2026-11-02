"""An experiment's code identity follows the Python sources, not the built interface."""

from huggingface_agents_langgraph.application import experiment_run


def test_a_rebuilt_interface_does_not_change_the_code_identity():
    before = experiment_run.source_identity()["source_sha256"]
    bundle = experiment_run.Path(experiment_run.__file__).parents[1] / "static"
    probe = bundle / "app" / "assets" / "probe-identity-test.js"
    probe.parent.mkdir(parents=True, exist_ok=True)
    try:
        probe.write_text("export const built = Date.now();", encoding="utf-8")
        assert experiment_run.source_identity()["source_sha256"] == before
    finally:
        probe.unlink(missing_ok=True)
