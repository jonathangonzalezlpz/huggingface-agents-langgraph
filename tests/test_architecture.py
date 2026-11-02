"""Dependency rules between the modules of the package.

These are the boundaries that already hold today. They are not the final layering:
they exist so a refactor (or a new feature) cannot quietly add a dependency in the
wrong direction. Tighten them as modules move into their layers.
"""

import ast
from collections import defaultdict
from pathlib import Path

import pytest

PACKAGE = "huggingface_agents_langgraph"
ROOT = Path(__file__).resolve().parents[1] / "src" / PACKAGE

# Entry points: they use everything and nothing may depend on them.
ENTRY_POINTS = {"web_app", "cli", "__main__"}

# What may still depend on each other in a cycle. Fix it and remove the entry.
KNOWN_CYCLES = {frozenset({"experiments", "run_tracking"})}

# Edges that break a rule today. Fix one and remove it here: the list only ever shrinks.
# experiment_comparison reaches into the CLI runner only for ``timing_summary``, which
# belongs in a pure metrics module.
KNOWN_VIOLATIONS = {("experiment_comparison", "experiment_runner")}

# The declarative layer describes graphs; it must not reach into infrastructure.
DECLARATIVE_MAY_IMPORT = {"state", "run_tracking", "tool_library"}

# Pure data and rules: no model, network, file or HTTP code behind them.
PURE_MODULES = {
    "state",
    "pipeline_versions",
    "experiment_comparison",
    "graph_definition.schema",
    "graph_definition.contracts",
    "graph_definition.params",
    "graph_definition.diagnostics",
}
INFRASTRUCTURE = {
    "llm",
    "web_research",
    "multimedia_processing",
    "model_server",
    "attachments",
    "web_app",
    "cli",
    "batteries",
    "experiment_runner",
}

# Components the declarative registry points at: they must not import it back.
COMPONENT_MODULES = {"llm_roles", "tool_components", "tool_library"}


def _module_name(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _modules() -> dict[str, Path]:
    return {_module_name(path): path for path in sorted(ROOT.rglob("*.py"))}


def _imports() -> dict[str, set[str]]:
    """For each module, the package modules it imports (including lazy imports)."""
    modules = _modules()
    graph: dict[str, set[str]] = defaultdict(set)
    for name, path in modules.items():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            candidates: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == PACKAGE or node.module.startswith(PACKAGE + "."):
                    base = node.module.removeprefix(PACKAGE).lstrip(".")
                    candidates.append(base)
                    candidates += [
                        f"{base}.{alias.name}".lstrip(".") for alias in node.names
                    ]
            elif isinstance(node, ast.Import):
                candidates += [
                    alias.name.removeprefix(PACKAGE).lstrip(".")
                    for alias in node.names
                    if alias.name.startswith(PACKAGE)
                ]
            for candidate in candidates:
                known = [
                    m
                    for m in modules
                    if candidate == m or candidate.startswith(m + ".")
                ]
                if known:
                    target = max(known, key=len)
                    if target != name:
                        graph[name].add(target)
    return graph


GRAPH = _imports()


def _top(module: str) -> str:
    return module.split(".")[0]


def test_the_analysis_sees_the_package():
    assert len(_modules()) > 40
    assert "run_tracking" in GRAPH["batteries"]


def test_nothing_depends_on_an_entry_point():
    offenders = [
        f"{source} -> {target}"
        for source, targets in GRAPH.items()
        for target in targets
        if target in ENTRY_POINTS and source not in ENTRY_POINTS
    ]
    assert offenders == []


def test_the_declarative_layer_only_reaches_what_it_must():
    offenders = [
        f"{source} -> {target}"
        for source, targets in GRAPH.items()
        if _top(source) == "graph_definition"
        for target in targets
        if _top(target) != "graph_definition" and target not in DECLARATIVE_MAY_IMPORT
    ]
    assert offenders == []


def test_pure_modules_do_not_import_infrastructure():
    offenders = [
        (source, target)
        for source in PURE_MODULES
        for target in GRAPH.get(source, set())
        if _top(target) in INFRASTRUCTURE
    ]
    assert set(offenders) <= KNOWN_VIOLATIONS, set(offenders) - KNOWN_VIOLATIONS


@pytest.mark.parametrize("source", sorted(PURE_MODULES - {"state"}))
def test_the_data_core_does_not_depend_on_runtime_tracking(source):
    # ``state`` is the only module every layer shares; the others stay free of tracing.
    allowed = {"state", "experiments", "pipeline_versions"}
    extra = {
        target
        for target in GRAPH.get(source, set())
        if _top(target) not in {"graph_definition", *allowed}
        and (source, target) not in KNOWN_VIOLATIONS
    }
    assert extra == set(), f"{source} imports {sorted(extra)}"


def test_components_do_not_import_the_declarative_layer():
    offenders = [
        f"{source} -> {target}"
        for source in COMPONENT_MODULES
        for target in GRAPH.get(source, set())
        if _top(target) == "graph_definition"
    ]
    assert offenders == []


def _cycles() -> set[frozenset[str]]:
    found: set[frozenset[str]] = set()
    for source, targets in GRAPH.items():
        for target in targets:
            if source in GRAPH.get(target, set()):
                found.add(frozenset({source, target}))
    return found


def test_no_new_import_cycles():
    assert _cycles() <= KNOWN_CYCLES, _cycles() - KNOWN_CYCLES


def test_known_cycles_are_still_real():
    """A fixed cycle must be removed from the list, so the list only ever shrinks."""
    assert KNOWN_CYCLES <= _cycles()


def test_known_violations_are_still_real():
    for source, target in KNOWN_VIOLATIONS:
        assert target in GRAPH.get(source, set()), f"{source} -> {target} is fixed"
