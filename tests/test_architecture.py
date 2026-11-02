"""Dependency rules between the packages of the backend.

Hexagonal layering without formal ports: each package may import only what is
listed in ``ALLOWED``. The rules are enforced here instead of with abstract
interfaces, which keeps the V3.1 runtime untouched. Fix an exception and remove it
from ``KNOWN_VIOLATIONS``: the list only ever shrinks.
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
KNOWN_CYCLES: set[frozenset[str]] = set()

# Edges that break a rule today. Fix one and remove it here: the list only ever shrinks.
KNOWN_VIOLATIONS: set[tuple[str, str]] = {}

# Shared by every layer: settings and per-run tracing.
KERNEL = {"config", "tracing"}

# Top-level package -> the top-level packages (or modules) it may import.
ALLOWED: dict[str, set[str]] = {
    "domain": {"domain"},
    "adapters": {"adapters", "domain", "model_server"},
    "pipeline": {"pipeline", "adapters", "domain", "model_server"},
    "studio": {"studio", "pipeline", "adapters", "domain"},
    "graph_definition": {"graph_definition", "studio", "domain"},
    "application": {
        "application",
        "pipeline",
        "adapters",
        "domain",
        "graph_definition",
    },
}

# Pure data and rules: no model, network, file or HTTP code behind them.
PURE_MODULES = {
    "domain.state",
    "domain.pipeline_versions",
    "domain.experiment_comparison",
    "graph_definition.schema",
    "graph_definition.contracts",
    "graph_definition.params",
    "graph_definition.diagnostics",
}

# Components the declarative registry points at: they must not import it back.
COMPONENT_MODULES = {
    "studio.llm_roles",
    "studio.tool_components",
    "studio.tool_library",
}


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
    assert "adapters.records" in GRAPH["application.batteries"]


def test_nothing_depends_on_an_entry_point():
    offenders = [
        f"{source} -> {target}"
        for source, targets in GRAPH.items()
        for target in targets
        if target in ENTRY_POINTS and source not in ENTRY_POINTS
    ]
    assert offenders == []


def test_each_package_only_imports_what_it_may():
    offenders = [
        f"{source} -> {target}"
        for source, targets in GRAPH.items()
        if _top(source) in ALLOWED
        for target in targets
        if _top(target) not in ALLOWED[_top(source)] | KERNEL
        and (source, target) not in KNOWN_VIOLATIONS
    ]
    assert offenders == []


@pytest.mark.parametrize("source", sorted(PURE_MODULES))
def test_pure_modules_stay_pure(source):
    infrastructure = {"adapters", "pipeline", "application", "studio", "api"}
    extra = {t for t in GRAPH.get(source, set()) if _top(t) in infrastructure}
    assert extra == set(), f"{source} imports {sorted(extra)}"


def test_components_do_not_import_the_declarative_layer():
    offenders = [
        f"{source} -> {target}"
        for source in COMPONENT_MODULES
        for target in GRAPH.get(source, set())
        if _top(target) == "graph_definition"
    ]
    assert offenders == []


def test_the_registry_mechanism_does_not_know_the_components():
    """The registry holds registrations; the components catalogues depend on it."""
    mechanism = {"graph_definition.registry", "graph_definition.authorization"}
    offenders = [
        f"{source} -> {target}"
        for source in mechanism
        for target in GRAPH.get(source, set())
        if target.startswith("graph_definition.components")
    ]
    assert offenders == []


def test_the_version_store_does_not_know_validation_or_layouts():
    """Versions are stored on their own; validation and layouts build on the store."""
    forbidden = {"application.architecture_service", "application.architecture_layouts"}
    imported = GRAPH.get("application.architecture_store", set())
    assert imported & forbidden == set()
    assert not any(
        target.startswith("graph_definition.components") for target in imported
    )


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
