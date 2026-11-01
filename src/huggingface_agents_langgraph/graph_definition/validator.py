"""Static validation of agent definitions.

The validator proves structural properties (known components, complete branches,
reachability, paths to END) and reports whether required state fields are
guaranteed, merely possible, or never produced. It cannot prove that a cycle
terminates or which branch a routing decision will pick at runtime, so it never
claims either.
"""

from collections import deque
from collections.abc import Collection, Iterable, Mapping

from huggingface_agents_langgraph.graph_definition.contracts import NodeContract
from huggingface_agents_langgraph.graph_definition.diagnostics import (
    Diagnostic,
    Severity,
    ValidationReport,
)
from huggingface_agents_langgraph.graph_definition.registry import NodeRegistry
from huggingface_agents_langgraph.graph_definition.routing_registry import (
    RoutingRegistry,
)
from huggingface_agents_langgraph.graph_definition.schema import (
    SPECIAL_TERMINALS,
    START_TERMINALS,
    AgentDefinition,
)
from huggingface_agents_langgraph.state import AgentState

END = "__end__"
END_TERMINALS = SPECIAL_TERMINALS - START_TERMINALS
_SEVERITY_ORDER: dict[Severity, int] = {"error": 0, "warning": 1, "info": 2}

Successors = dict[str, set[str]]


def _normalize_target(target: str) -> str:
    return END if target in END_TERMINALS else target


class GraphValidator:
    """Analyze an ``AgentDefinition`` against the registered components."""

    def __init__(
        self,
        node_registry: NodeRegistry,
        routing_registry: RoutingRegistry,
        *,
        initial_fields: Collection[str] | None = None,
        state_fields: Collection[str] | None = None,
        state_types: Collection[str] | None = None,
    ) -> None:
        self._nodes = node_registry
        self._routing = routing_registry
        self._initial_fields = frozenset(
            AgentState.__required_keys__ if initial_fields is None else initial_fields
        )
        self._state_fields = frozenset(
            AgentState.__annotations__ if state_fields is None else state_fields
        )
        self._state_types = frozenset(
            {AgentState.__name__} if state_types is None else state_types
        )

    def validate(self, definition: AgentDefinition) -> ValidationReport:
        """Return all findings for the definition, ordered deterministically."""
        diagnostics: list[Diagnostic] = []
        if definition.state_type not in self._state_types:
            diagnostics.append(
                Diagnostic(
                    "UNKNOWN_STATE_TYPE",
                    "error",
                    f"State type '{definition.state_type}' is not supported.",
                    details={"state_type": definition.state_type},
                )
            )
        contracts = self._known_contracts(definition, diagnostics)
        successors = self._check_edges(definition, diagnostics)

        reachable = self._reachable(definition.initial_node, successors)
        can_end = self._can_reach_end(successors)
        for node in definition.nodes:
            if node.id not in reachable:
                diagnostics.append(
                    Diagnostic(
                        "UNREACHABLE_NODE",
                        "error",
                        f"Node '{node.id}' cannot be reached from "
                        f"'{definition.initial_node}'.",
                        node_id=node.id,
                    )
                )
            elif node.id not in can_end:
                diagnostics.append(
                    Diagnostic(
                        "NO_PATH_TO_END",
                        "error",
                        f"Node '{node.id}' has no path to END.",
                        node_id=node.id,
                    )
                )
        diagnostics.extend(self._cycle_diagnostics(reachable, successors, can_end))
        diagnostics.extend(
            self._availability_diagnostics(
                definition.initial_node, reachable, successors, contracts
            )
        )
        diagnostics.extend(self._state_field_diagnostics(contracts))
        return ValidationReport(diagnostics=tuple(sorted(diagnostics, key=_sort_key)))

    def _known_contracts(
        self, definition: AgentDefinition, diagnostics: list[Diagnostic]
    ) -> dict[str, NodeContract]:
        contracts: dict[str, NodeContract] = {}
        for node in definition.nodes:
            if self._nodes.has(node.implementation_id):
                contracts[node.id] = self._nodes.get_contract(node.implementation_id)
            else:
                diagnostics.append(
                    Diagnostic(
                        "UNKNOWN_IMPLEMENTATION",
                        "error",
                        f"Node '{node.id}' uses unregistered implementation "
                        f"'{node.implementation_id}'.",
                        node_id=node.id,
                        details={"implementation_id": node.implementation_id},
                    )
                )
        return contracts

    def _check_edges(
        self, definition: AgentDefinition, diagnostics: list[Diagnostic]
    ) -> Successors:
        successors: Successors = {node.id: set() for node in definition.nodes}
        direct_count: dict[str, int] = {}
        conditional_count: dict[str, int] = {}

        for edge in definition.edges:
            if edge.source in START_TERMINALS:
                self._check_start_edge(edge, definition.initial_node, diagnostics)
                continue
            if edge.edge_type == "direct":
                direct_count[edge.source] = direct_count.get(edge.source, 0) + 1
                successors[edge.source].add(_normalize_target(edge.target or ""))
            else:
                conditional_count[edge.source] = (
                    conditional_count.get(edge.source, 0) + 1
                )
                successors[edge.source].update(
                    _normalize_target(t) for t in edge.conditional_targets.values()
                )
                self._check_branches(edge, diagnostics)

        for source in sorted(set(direct_count) | set(conditional_count)):
            direct = direct_count.get(source, 0)
            conditional = conditional_count.get(source, 0)
            if direct + conditional > 1:
                diagnostics.append(
                    Diagnostic(
                        "OUTGOING_EDGE_CONFLICT",
                        "error",
                        f"Node '{source}' has {direct} direct and {conditional} "
                        "conditional outgoing edges; exactly one is supported.",
                        node_id=source,
                        details={"direct": direct, "conditional": conditional},
                    )
                )
        return successors

    @staticmethod
    def _check_start_edge(edge, initial_node: str, diagnostics: list[Diagnostic]):
        if edge.edge_type == "conditional":
            message = "Conditional edges from START are not supported."
        elif edge.target != initial_node:
            message = (
                f"START edge targets '{edge.target}' but initial_node is "
                f"'{initial_node}'."
            )
        else:
            return
        diagnostics.append(
            Diagnostic("START_EDGE_MISMATCH", "error", message, edge_source=edge.source)
        )

    def _check_branches(self, edge, diagnostics: list[Diagnostic]) -> None:
        strategy_id = edge.routing_strategy or ""
        if not self._routing.has(strategy_id):
            diagnostics.append(
                Diagnostic(
                    "UNKNOWN_ROUTING_STRATEGY",
                    "error",
                    f"Edge from '{edge.source}' uses unregistered routing "
                    f"strategy '{strategy_id}'.",
                    edge_source=edge.source,
                    details={"routing_strategy": strategy_id},
                )
            )
            return
        expected = self._routing.get(strategy_id).outputs
        declared = frozenset(edge.conditional_targets)
        if expected != declared:
            diagnostics.append(
                Diagnostic(
                    "BRANCH_LABELS_MISMATCH",
                    "error",
                    f"Branches of '{edge.source}' do not match strategy "
                    f"'{strategy_id}'.",
                    edge_source=edge.source,
                    details={
                        "routing_strategy": strategy_id,
                        "missing": sorted(expected - declared),
                        "unexpected": sorted(declared - expected),
                    },
                )
            )

    @staticmethod
    def _reachable(entry: str, successors: Successors) -> set[str]:
        seen = {entry}
        queue = deque([entry])
        while queue:
            for target in successors.get(queue.popleft(), ()):
                if target != END and target not in seen:
                    seen.add(target)
                    queue.append(target)
        return seen

    @staticmethod
    def _can_reach_end(successors: Successors) -> set[str]:
        predecessors: dict[str, set[str]] = {}
        for source, targets in successors.items():
            for target in targets:
                predecessors.setdefault(target, set()).add(source)
        seen: set[str] = set()
        queue = deque(predecessors.get(END, ()))
        while queue:
            node = queue.popleft()
            if node not in seen:
                seen.add(node)
                queue.extend(predecessors.get(node, ()))
        return seen

    @staticmethod
    def _cycle_diagnostics(
        reachable: set[str], successors: Successors, can_end: set[str]
    ) -> list[Diagnostic]:
        graph = {
            node: {t for t in successors[node] if t in reachable} for node in reachable
        }
        diagnostics = []
        for component in _strongly_connected_components(graph):
            is_cycle = len(component) > 1 or any(
                node in graph[node] for node in component
            )
            if is_cycle and component & can_end:
                nodes = sorted(component)
                diagnostics.append(
                    Diagnostic(
                        "CYCLE_DETECTED",
                        "info",
                        f"Cycle through {nodes}; termination depends on runtime "
                        "budgets and is not proven statically.",
                        node_id=nodes[0],
                        details={"nodes": nodes},
                    )
                )
        return diagnostics

    def _availability_diagnostics(
        self,
        entry: str,
        reachable: set[str],
        successors: Successors,
        contracts: Mapping[str, NodeContract],
    ) -> list[Diagnostic]:
        nodes = sorted(reachable)
        predecessors: dict[str, set[str]] = {node: set() for node in nodes}
        for source in nodes:
            for target in successors[source]:
                if target in predecessors:
                    predecessors[target].add(source)
        guaranteed_in, possible_in = _field_availability(
            entry, nodes, predecessors, contracts, self._initial_fields
        )

        diagnostics = []
        for node in nodes:
            contract = contracts.get(node)
            if contract is None:
                continue
            for field_name in sorted(contract.required_inputs):
                if field_name in guaranteed_in[node]:
                    continue
                if field_name in possible_in[node]:
                    diagnostics.append(
                        Diagnostic(
                            "REQUIRED_INPUT_NOT_GUARANTEED",
                            "warning",
                            f"Node '{node}' requires '{field_name}', which is "
                            "produced on some paths but not guaranteed on all.",
                            node_id=node,
                            details={"field": field_name},
                        )
                    )
                else:
                    diagnostics.append(
                        Diagnostic(
                            "REQUIRED_INPUT_UNAVAILABLE",
                            "error",
                            f"Node '{node}' requires '{field_name}', which no "
                            "path produces.",
                            node_id=node,
                            details={"field": field_name},
                        )
                    )
        return diagnostics

    def _state_field_diagnostics(
        self, contracts: Mapping[str, NodeContract]
    ) -> list[Diagnostic]:
        diagnostics = []
        for node in sorted(contracts):
            contract = contracts[node]
            unknown = (contract.all_inputs | contract.all_outputs) - self._state_fields
            diagnostics.extend(
                Diagnostic(
                    "UNKNOWN_STATE_FIELD",
                    "error",
                    f"Contract of '{node}' references unknown state field "
                    f"'{field_name}'.",
                    node_id=node,
                    details={"field": field_name},
                )
                for field_name in sorted(unknown)
            )
        return diagnostics


def _field_availability(
    entry: str,
    nodes: list[str],
    predecessors: Mapping[str, set[str]],
    contracts: Mapping[str, NodeContract],
    initial_fields: frozenset[str],
) -> tuple[dict[str, frozenset[str]], dict[str, frozenset[str]]]:
    """Forward dataflow to a fixed point: fields guaranteed and possible on entry."""
    universe = set(initial_fields)
    for contract in contracts.values():
        universe |= contract.all_inputs | contract.all_outputs

    def outputs(node: str, attribute: str) -> frozenset[str]:
        contract = contracts.get(node)
        return getattr(contract, attribute) if contract else frozenset()

    guaranteed_out = {node: frozenset(universe) for node in nodes}
    possible_out: dict[str, frozenset[str]] = {node: frozenset() for node in nodes}
    guaranteed_in: dict[str, frozenset[str]] = {}
    possible_in: dict[str, frozenset[str]] = {}

    changed = True
    while changed:
        changed = False
        for node in nodes:
            must = initial_fields if node == entry else frozenset(universe)
            may = initial_fields if node == entry else frozenset()
            for pred in predecessors[node]:
                must = must & guaranteed_out[pred]
                may = may | possible_out[pred]
            new_must = must | outputs(node, "guaranteed_outputs")
            new_may = may | outputs(node, "all_outputs")
            guaranteed_in[node], possible_in[node] = must, may
            if new_must != guaranteed_out[node] or new_may != possible_out[node]:
                guaranteed_out[node], possible_out[node] = new_must, new_may
                changed = True
    return guaranteed_in, possible_in


def _strongly_connected_components(graph: Mapping[str, Iterable[str]]):
    """Tarjan's algorithm; returns components as sets of node ids."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[set[str]] = []

    def visit(node: str) -> None:
        index[node] = low[node] = len(index)
        stack.append(node)
        on_stack.add(node)
        for target in sorted(graph[node]):
            if target not in index:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], index[target])
        if low[node] == index[node]:
            component: set[str] = set()
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.add(member)
                if member == node:
                    break
            components.append(component)

    for node in sorted(graph):
        if node not in index:
            visit(node)
    return components


def _sort_key(diagnostic: Diagnostic) -> tuple:
    return (
        _SEVERITY_ORDER[diagnostic.severity],
        diagnostic.code,
        diagnostic.node_id or "",
        diagnostic.edge_source or "",
        str(diagnostic.details.get("field", "")),
    )
