"""Tests for static validation of agent definitions."""

from dataclasses import replace

import pytest

from huggingface_agents_langgraph.graph_definition import (
    AgentDefinition,
    EdgeDefinition,
    NodeContract,
    NodeDefinition,
    NodeRegistry,
)
from huggingface_agents_langgraph.graph_definition.definitions import (
    create_gaia_v31_definition,
)
from huggingface_agents_langgraph.graph_definition.registry import (
    create_gaia_v3_registry,
)
from huggingface_agents_langgraph.graph_definition.routing_registry import (
    RoutingRegistry,
    RoutingStrategy,
    create_gaia_v31_routing_registry,
)
from huggingface_agents_langgraph.graph_definition.validator import GraphValidator

END = "__end__"
STATE_FIELDS = frozenset({"question", "x", "y", "z"})


def _registry(**contracts: NodeContract) -> NodeRegistry:
    registry = NodeRegistry()
    for name, contract in contracts.items():
        registry.register(name, contract=contract, handler=lambda state: {})
    return registry


def _routing() -> RoutingRegistry:
    routing = RoutingRegistry()
    routing.register(RoutingStrategy("pick", outputs={"left", "right"}))
    return routing


def _validator(registry=None, initial_fields=frozenset({"question"})):
    registry = registry or _registry(a=NodeContract(), b=NodeContract())
    return GraphValidator(
        registry,
        _routing(),
        initial_fields=initial_fields,
        state_fields=STATE_FIELDS,
    )


def _definition(nodes, edges, initial_node=None):
    return AgentDefinition(
        schema_version="4.0",
        architecture_id="test",
        state_type="AgentState",
        initial_node=initial_node or nodes[0],
        nodes=tuple(NodeDefinition(id=n, implementation_id=n) for n in nodes),
        edges=tuple(edges),
    )


def _direct(source, target):
    return EdgeDefinition(source=source, target=target)


def _pick(source, left, right, strategy="pick", **extra):
    targets = {"left": left, "right": right}
    targets.update(extra)
    return EdgeDefinition(
        source=source,
        edge_type="conditional",
        routing_strategy=strategy,
        conditional_targets=targets,
    )


def _codes(report, severity=None):
    return [d.code for d in report.diagnostics if severity in (None, d.severity)]


class TestStructure:
    def test_valid_linear_graph_has_no_diagnostics(self):
        report = _validator().validate(
            _definition(["a", "b"], [_direct("a", "b"), _direct("b", END)])
        )
        assert report.is_valid
        assert report.diagnostics == ()

    def test_unknown_implementation(self):
        validator = _validator(_registry(a=NodeContract()))
        report = validator.validate(
            _definition(["a", "b"], [_direct("a", "b"), _direct("b", END)])
        )
        assert _codes(report, "error") == ["UNKNOWN_IMPLEMENTATION"]
        assert report.errors[0].node_id == "b"

    def test_unknown_routing_strategy(self):
        report = _validator().validate(
            _definition(
                ["a", "b"],
                [_pick("a", "b", END, strategy="nope"), _direct("b", END)],
            )
        )
        assert "UNKNOWN_ROUTING_STRATEGY" in _codes(report, "error")

    def test_incomplete_branches_are_reported(self):
        edge = EdgeDefinition(
            source="a",
            edge_type="conditional",
            routing_strategy="pick",
            conditional_targets={"left": "b"},
        )
        report = _validator().validate(
            _definition(["a", "b"], [edge, _direct("b", END)])
        )
        mismatch = [d for d in report.errors if d.code == "BRANCH_LABELS_MISMATCH"]
        assert len(mismatch) == 1
        assert list(mismatch[0].details["missing"]) == ["right"]
        assert mismatch[0].edge_source == "a"

    def test_unknown_branches_are_reported(self):
        edge = _pick("a", "b", END, other="b")
        report = _validator().validate(
            _definition(["a", "b"], [edge, _direct("b", END)])
        )
        mismatch = [d for d in report.errors if d.code == "BRANCH_LABELS_MISMATCH"]
        assert list(mismatch[0].details["unexpected"]) == ["other"]

    def test_start_edge_to_initial_node_is_accepted(self):
        report = _validator().validate(
            _definition(
                ["a", "b"],
                [_direct("__start__", "a"), _direct("a", "b"), _direct("b", END)],
            )
        )
        assert report.is_valid

    def test_start_edge_to_other_node_is_rejected(self):
        report = _validator().validate(
            _definition(
                ["a", "b"],
                [_direct("__start__", "b"), _direct("a", "b"), _direct("b", END)],
            )
        )
        assert "START_EDGE_MISMATCH" in _codes(report, "error")

    def test_conditional_edge_from_start_is_rejected(self):
        report = _validator().validate(
            _definition(
                ["a", "b"],
                [_pick("__start__", "a", "b"), _direct("a", END), _direct("b", END)],
            )
        )
        assert "START_EDGE_MISMATCH" in _codes(report, "error")

    def test_two_direct_edges_from_one_node_conflict(self):
        report = _validator().validate(
            _definition(
                ["a", "b"],
                [_direct("a", "b"), _direct("a", END), _direct("b", END)],
            )
        )
        assert "OUTGOING_EDGE_CONFLICT" in _codes(report, "error")

    def test_direct_plus_conditional_conflict(self):
        report = _validator().validate(
            _definition(
                ["a", "b"],
                [_direct("a", "b"), _pick("a", "b", END), _direct("b", END)],
            )
        )
        assert "OUTGOING_EDGE_CONFLICT" in _codes(report, "error")


class TestReachability:
    def test_unreachable_node(self):
        report = _validator().validate(
            _definition(["a", "b"], [_direct("a", END), _direct("b", END)])
        )
        unreachable = [d for d in report.errors if d.code == "UNREACHABLE_NODE"]
        assert [d.node_id for d in unreachable] == ["b"]

    def test_dead_end_has_no_path_to_end(self):
        report = _validator().validate(_definition(["a", "b"], [_direct("a", "b")]))
        no_path = [d for d in report.errors if d.code == "NO_PATH_TO_END"]
        assert sorted(d.node_id for d in no_path) == ["a", "b"]

    def test_cycle_without_exit_has_no_path_to_end(self):
        report = _validator().validate(
            _definition(["a", "b"], [_direct("a", "b"), _direct("b", "a")])
        )
        assert "NO_PATH_TO_END" in _codes(report, "error")

    def test_cycle_with_exit_is_informational_only(self):
        report = _validator().validate(
            _definition(
                ["a", "b"],
                [_direct("a", "b"), _pick("b", "a", END)],
            )
        )
        assert report.is_valid
        cycles = [d for d in report.infos if d.code == "CYCLE_DETECTED"]
        assert len(cycles) == 1
        assert list(cycles[0].details["nodes"]) == ["a", "b"]

    def test_self_loop_is_a_cycle(self):
        report = _validator().validate(_definition(["a"], [_pick("a", "a", END)]))
        assert report.is_valid
        assert _codes(report, "info") == ["CYCLE_DETECTED"]


class TestFieldAvailability:
    def test_input_from_initial_state_is_guaranteed(self):
        registry = _registry(a=NodeContract(required_inputs={"question"}))
        report = _validator(registry).validate(_definition(["a"], [_direct("a", END)]))
        assert report.diagnostics == ()

    def test_input_never_produced_is_an_error(self):
        registry = _registry(a=NodeContract(required_inputs={"x"}))
        report = _validator(registry).validate(_definition(["a"], [_direct("a", END)]))
        assert _codes(report) == ["REQUIRED_INPUT_UNAVAILABLE"]
        assert report.errors[0].details["field"] == "x"

    def test_input_produced_upstream_is_guaranteed(self):
        registry = _registry(
            a=NodeContract(guaranteed_outputs={"x"}),
            b=NodeContract(required_inputs={"x"}),
        )
        report = _validator(registry).validate(
            _definition(["a", "b"], [_direct("a", "b"), _direct("b", END)])
        )
        assert report.diagnostics == ()

    def test_optional_output_is_not_guaranteed(self):
        registry = _registry(
            a=NodeContract(optional_outputs={"x"}),
            b=NodeContract(required_inputs={"x"}),
        )
        report = _validator(registry).validate(
            _definition(["a", "b"], [_direct("a", "b"), _direct("b", END)])
        )
        assert _codes(report) == ["REQUIRED_INPUT_NOT_GUARANTEED"]
        assert report.is_valid

    def test_field_produced_on_one_branch_only_is_a_warning(self):
        registry = _registry(
            a=NodeContract(),
            b=NodeContract(guaranteed_outputs={"x"}),
            c=NodeContract(),
            d=NodeContract(required_inputs={"x"}),
        )
        report = _validator(registry).validate(
            _definition(
                ["a", "b", "c", "d"],
                [
                    _pick("a", "b", "c"),
                    _direct("b", "d"),
                    _direct("c", "d"),
                    _direct("d", END),
                ],
            )
        )
        assert _codes(report) == ["REQUIRED_INPUT_NOT_GUARANTEED"]
        assert report.warnings[0].node_id == "d"

    def test_field_produced_on_every_branch_is_guaranteed(self):
        registry = _registry(
            a=NodeContract(),
            b=NodeContract(guaranteed_outputs={"x"}),
            c=NodeContract(guaranteed_outputs={"x"}),
            d=NodeContract(required_inputs={"x"}),
        )
        report = _validator(registry).validate(
            _definition(
                ["a", "b", "c", "d"],
                [
                    _pick("a", "b", "c"),
                    _direct("b", "d"),
                    _direct("c", "d"),
                    _direct("d", END),
                ],
            )
        )
        assert report.diagnostics == ()

    def test_loop_does_not_make_loop_body_output_guaranteed_at_entry(self):
        registry = _registry(
            a=NodeContract(required_inputs={"x"}),
            b=NodeContract(guaranteed_outputs={"x"}),
        )
        report = _validator(registry).validate(
            _definition(["a", "b"], [_direct("a", "b"), _pick("b", "a", END)])
        )
        assert _codes(report, "warning") == ["REQUIRED_INPUT_NOT_GUARANTEED"]
        assert report.warnings[0].node_id == "a"

    def test_loop_body_output_is_guaranteed_after_the_loop_node(self):
        registry = _registry(
            a=NodeContract(guaranteed_outputs={"x"}),
            b=NodeContract(required_inputs={"x"}),
        )
        report = _validator(registry).validate(
            _definition(["a", "b"], [_direct("a", "b"), _pick("b", "a", END)])
        )
        assert _codes(report, "error") == []
        assert _codes(report, "warning") == []

    def test_contract_field_missing_from_state_is_an_error(self):
        registry = _registry(a=NodeContract(guaranteed_outputs={"unknown_field"}))
        report = _validator(registry).validate(_definition(["a"], [_direct("a", END)]))
        assert _codes(report, "error") == ["UNKNOWN_STATE_FIELD"]

    def test_initial_fields_are_configurable(self):
        registry = _registry(a=NodeContract(required_inputs={"y"}))
        definition = _definition(["a"], [_direct("a", END)])
        assert not _validator(registry).validate(definition).is_valid
        assert (
            _validator(registry, frozenset({"question", "y"}))
            .validate(definition)
            .is_valid
        )


def test_report_is_deterministic():
    registry = _registry(a=NodeContract(required_inputs={"x", "y"}))
    definition = _definition(["a"], [_direct("a", END)])
    first = _validator(registry).validate(definition)
    second = _validator(registry).validate(definition)
    assert first == second
    assert [d.details["field"] for d in first.errors] == ["x", "y"]


class TestGaiaV31:
    @staticmethod
    def _validate(definition):
        return GraphValidator(
            create_gaia_v3_registry(), create_gaia_v31_routing_registry()
        ).validate(definition)

    def test_v31_definition_has_no_errors(self):
        report = self._validate(create_gaia_v31_definition())
        assert report.is_valid, report.errors

    def test_v31_warnings_are_the_known_attachment_limitation(self):
        report = self._validate(create_gaia_v31_definition())
        assert {(d.code, d.node_id, d.details["field"]) for d in report.warnings} == {
            ("REQUIRED_INPUT_NOT_GUARANTEED", node, "file_path")
            for node in (
                "code_processing",
                "spreadsheet_processing",
                "document_processing",
                "multimedia_processing",
            )
        }

    def test_v31_review_research_cycle_is_preserved(self):
        report = self._validate(create_gaia_v31_definition())
        cycles = [d for d in report.infos if d.code == "CYCLE_DETECTED"]
        assert len(cycles) == 1
        assert list(cycles[0].details["nodes"]) == ["research_action", "review"]

    @pytest.mark.parametrize(
        ("mutation", "expected"),
        [
            ("drop_final_edge", "NO_PATH_TO_END"),
            ("drop_router_branch", "BRANCH_LABELS_MISMATCH"),
            ("drop_research_exit", "NO_PATH_TO_END"),
            ("drop_review_solve", "UNREACHABLE_NODE"),
        ],
    )
    def test_mutations_are_detected(self, mutation, expected):
        definition = create_gaia_v31_definition()
        edges = list(definition.edges)
        if mutation == "drop_final_edge":
            edges = [e for e in edges if e.source != "answer_production"]
        elif mutation == "drop_router_branch":
            router = next(e for e in edges if e.source == "router")
            targets = dict(router.conditional_targets)
            del targets["web"]
            edges[edges.index(router)] = replace(router, conditional_targets=targets)
        elif mutation == "drop_research_exit":
            review = next(e for e in edges if e.source == "review")
            edges[edges.index(review)] = replace(
                review,
                conditional_targets={
                    "act": "research_action",
                    "solve": "research_action",
                },
            )
        else:
            edges = [e for e in edges if e.source != "review"]
            edges.append(_direct("review", "research_action"))
        mutated = replace(definition, edges=tuple(edges))
        report = self._validate(mutated)
        assert expected in _codes(report, "error")


class TestStateType:
    def test_unknown_state_type_is_an_error(self):
        definition = replace(
            _definition(["a"], [_direct("a", END)]), state_type="OtherState"
        )
        report = _validator(_registry(a=NodeContract())).validate(definition)
        assert _codes(report, "error") == ["UNKNOWN_STATE_TYPE"]
        assert report.errors[0].details["state_type"] == "OtherState"

    def test_state_types_are_configurable(self):
        definition = replace(
            _definition(["a"], [_direct("a", END)]), state_type="OtherState"
        )
        validator = GraphValidator(
            _registry(a=NodeContract()),
            _routing(),
            initial_fields=frozenset({"question"}),
            state_fields=STATE_FIELDS,
            state_types={"OtherState"},
        )
        assert validator.validate(definition).diagnostics == ()
