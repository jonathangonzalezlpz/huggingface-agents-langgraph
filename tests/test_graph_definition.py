"""Tests for GAIA Agent V4 declarative graph contracts and registry."""

from dataclasses import FrozenInstanceError

import pytest

from huggingface_agents_langgraph.graph_definition import (
    AgentDefinition,
    EdgeDefinition,
    NodeContract,
    NodeDefinition,
    NodeRegistry,
)
from huggingface_agents_langgraph.graph_definition.registry import (
    _resolve_module_attr,
    create_gaia_v3_registry,
)


class TestNodeContract:
    def test_contract_defaults(self):
        contract = NodeContract()
        assert contract.required_inputs == frozenset()
        assert contract.optional_inputs == frozenset()
        assert contract.guaranteed_outputs == frozenset()
        assert contract.optional_outputs == frozenset()
        assert contract.all_inputs == frozenset()
        assert contract.all_outputs == frozenset()

    def test_contract_immutability(self):
        contract = NodeContract(required_inputs=frozenset({"question"}))
        with pytest.raises(FrozenInstanceError):
            contract.required_inputs = frozenset({"other"})  # type: ignore

    def test_contract_rejects_overlapping_inputs(self):
        with pytest.raises(
            ValueError, match="cannot be both required and optional inputs"
        ):
            NodeContract(
                required_inputs=frozenset({"question"}),
                optional_inputs=frozenset({"question"}),
            )

    def test_contract_rejects_overlapping_outputs(self):
        with pytest.raises(
            ValueError, match="cannot be both guaranteed and optional outputs"
        ):
            NodeContract(
                guaranteed_outputs=frozenset({"evidence"}),
                optional_outputs=frozenset({"evidence"}),
            )

    def test_validate_inputs(self):
        contract = NodeContract(
            required_inputs=frozenset({"question", "file_path"}),
            optional_inputs=frozenset({"task_id"}),
        )
        # Missing both
        assert contract.validate_inputs({}) == ["file_path", "question"]
        # Missing one
        assert contract.validate_inputs({"question": "What is this?"}) == ["file_path"]
        # Satisfied
        assert (
            contract.validate_inputs({"question": "test", "file_path": "test.pdf"})
            == []
        )
        # Satisfied from set
        assert contract.validate_inputs({"question", "file_path"}) == []

    def test_contract_serialization_roundtrip(self):
        original = NodeContract(
            required_inputs=frozenset({"question", "file_path"}),
            optional_inputs=frozenset({"task_id"}),
            guaranteed_outputs=frozenset({"evidence"}),
            optional_outputs=frozenset({"research_notes"}),
        )
        serialized = original.to_dict()
        assert serialized == {
            "required_inputs": ["file_path", "question"],
            "optional_inputs": ["task_id"],
            "guaranteed_outputs": ["evidence"],
            "optional_outputs": ["research_notes"],
        }
        reconstructed = NodeContract.from_dict(serialized)
        assert reconstructed == original


class TestEdgeDefinition:
    def test_direct_edge_valid(self):
        edge = EdgeDefinition(source="node_a", target="node_b")
        assert edge.source == "node_a"
        assert edge.target == "node_b"
        assert edge.edge_type == "direct"
        assert edge.routing_strategy is None
        assert edge.conditional_targets == {}

    def test_direct_edge_invalid_target(self):
        with pytest.raises(ValueError, match="must have a valid target"):
            EdgeDefinition(source="node_a", target="")

    def test_direct_edge_cannot_have_conditional_fields(self):
        with pytest.raises(
            ValueError,
            match="cannot have routing_strategy or conditional_targets",
        ):
            EdgeDefinition(
                source="node_a",
                target="node_b",
                routing_strategy="some_strategy",
            )

    def test_conditional_edge_valid(self):
        edge = EdgeDefinition(
            source="router",
            edge_type="conditional",
            routing_strategy="route_by_type",
            conditional_targets={"doc": "doc_proc", "code": "code_proc"},
        )
        assert edge.edge_type == "conditional"
        assert edge.routing_strategy == "route_by_type"
        assert edge.conditional_targets == {
            "doc": "doc_proc",
            "code": "code_proc",
        }

    def test_conditional_edge_cannot_have_direct_target(self):
        with pytest.raises(ValueError, match="must not specify a direct target"):
            EdgeDefinition(
                source="router",
                target="node_b",
                edge_type="conditional",
                routing_strategy="strat",
                conditional_targets={"a": "b"},
            )

    def test_conditional_edge_requires_strategy_and_targets(self):
        with pytest.raises(ValueError, match="specify a routing_strategy"):
            EdgeDefinition(
                source="router",
                edge_type="conditional",
                conditional_targets={"a": "b"},
            )
        with pytest.raises(ValueError, match="declare at least one"):
            EdgeDefinition(
                source="router",
                edge_type="conditional",
                routing_strategy="strat",
            )

    def test_edge_serialization_roundtrip(self):
        direct = EdgeDefinition(source="a", target="b")
        assert EdgeDefinition.from_dict(direct.to_dict()) == direct

        conditional = EdgeDefinition(
            source="router",
            edge_type="conditional",
            routing_strategy="strat_a",
            conditional_targets={"opt1": "node1", "opt2": "node2"},
        )
        assert EdgeDefinition.from_dict(conditional.to_dict()) == conditional


class TestNodeDefinition:
    def test_node_definition_valid(self):
        node = NodeDefinition(
            id="preprocess_1",
            implementation_id="preprocessing",
            description="First step",
            metadata={"priority": 1},
        )
        assert node.id == "preprocess_1"
        assert node.implementation_id == "preprocessing"
        assert node.description == "First step"
        assert node.metadata == {"priority": 1}

    def test_node_definition_empty_id_rejected(self):
        with pytest.raises(ValueError, match="Node id cannot be empty"):
            NodeDefinition(id="", implementation_id="preprocessing")

    def test_node_definition_empty_implementation_id_rejected(self):
        with pytest.raises(
            ValueError, match="must reference a non-empty implementation_id"
        ):
            NodeDefinition(id="p1", implementation_id="")

    def test_node_serialization_roundtrip(self):
        node = NodeDefinition(
            id="review_loop",
            implementation_id="review",
            description="Reviews actions",
            metadata={"max_cycles": 4},
        )
        assert NodeDefinition.from_dict(node.to_dict()) == node


class TestAgentDefinition:
    def test_agent_definition_valid(self):
        agent = AgentDefinition(
            schema_version="4.0",
            architecture_id="linear_pipeline",
            state_type="AgentState",
            initial_node="node_a",
            nodes=(
                NodeDefinition(id="node_a", implementation_id="step_a"),
                NodeDefinition(id="node_b", implementation_id="step_b"),
            ),
            edges=(
                EdgeDefinition(source="node_a", target="node_b"),
                EdgeDefinition(source="node_b", target="__end__"),
            ),
            metadata={"author": "Antigravity"},
        )
        assert agent.schema_version == "4.0"
        assert agent.architecture_id == "linear_pipeline"
        assert len(agent.nodes) == 2
        assert len(agent.edges) == 2
        assert agent.get_node("node_a") is not None
        assert agent.get_node("non_existent") is None

    def test_agent_rejects_duplicate_node_ids(self):
        with pytest.raises(ValueError, match="Duplicate node id detected"):
            AgentDefinition(
                schema_version="4.0",
                architecture_id="test",
                state_type="AgentState",
                initial_node="node_a",
                nodes=(
                    NodeDefinition(id="node_a", implementation_id="impl_1"),
                    NodeDefinition(id="node_a", implementation_id="impl_2"),
                ),
            )

    def test_agent_rejects_unresolved_initial_node(self):
        with pytest.raises(ValueError, match="initial_node 'unknown' does not match"):
            AgentDefinition(
                schema_version="4.0",
                architecture_id="test",
                state_type="AgentState",
                initial_node="unknown",
                nodes=(NodeDefinition(id="node_a", implementation_id="impl_1"),),
            )

    def test_agent_rejects_invalid_edge_source(self):
        with pytest.raises(ValueError, match="Edge source 'ghost' does not match"):
            AgentDefinition(
                schema_version="4.0",
                architecture_id="test",
                state_type="AgentState",
                initial_node="node_a",
                nodes=(NodeDefinition(id="node_a", implementation_id="impl_1"),),
                edges=(EdgeDefinition(source="ghost", target="node_a"),),
            )

    def test_agent_rejects_invalid_edge_target(self):
        with pytest.raises(
            ValueError, match="Direct edge target 'ghost' does not match"
        ):
            AgentDefinition(
                schema_version="4.0",
                architecture_id="test",
                state_type="AgentState",
                initial_node="node_a",
                nodes=(NodeDefinition(id="node_a", implementation_id="impl_1"),),
                edges=(EdgeDefinition(source="node_a", target="ghost"),),
            )

    def test_agent_rejects_invalid_conditional_branch_target(self):
        with pytest.raises(
            ValueError,
            match="Conditional edge branch 'opt' target 'ghost' does not match",
        ):
            AgentDefinition(
                schema_version="4.0",
                architecture_id="test",
                state_type="AgentState",
                initial_node="node_a",
                nodes=(NodeDefinition(id="node_a", implementation_id="impl_1"),),
                edges=(
                    EdgeDefinition(
                        source="node_a",
                        edge_type="conditional",
                        routing_strategy="strat",
                        conditional_targets={"opt": "ghost"},
                    ),
                ),
            )

    def test_agent_serialization_roundtrip(self):
        agent = AgentDefinition(
            schema_version="4.0",
            architecture_id="gaia_v4_test",
            state_type="AgentState",
            initial_node="start_node",
            nodes=(
                NodeDefinition(id="start_node", implementation_id="preprocessing"),
                NodeDefinition(id="end_node", implementation_id="reasoning"),
            ),
            edges=(
                EdgeDefinition(source="start_node", target="end_node"),
                EdgeDefinition(source="end_node", target="END"),
            ),
            metadata={"version": 1},
        )
        serialized = agent.to_dict()
        reconstructed = AgentDefinition.from_dict(serialized)
        assert reconstructed == agent


class TestNodeRegistry:
    def test_registration_and_retrieval(self):
        registry = NodeRegistry()
        contract = NodeContract(
            required_inputs=frozenset({"input_a"}),
            guaranteed_outputs=frozenset({"output_b"}),
        )

        def mock_handler(state):
            return {"output_b": "value"}

        registry.register(
            "test_node",
            contract=contract,
            handler=mock_handler,
            description="Mock test node",
        )

        assert registry.has("test_node")
        assert registry.get_contract("test_node") == contract
        assert registry.resolve("test_node") is mock_handler
        assert registry.list_implementations() == ["test_node"]

    def test_duplicate_registration_rejected_unless_override(self):
        registry = NodeRegistry()
        contract = NodeContract()
        registry.register("node", contract=contract, handler=lambda s: s)

        with pytest.raises(KeyError, match="is already registered"):
            registry.register("node", contract=contract, handler=lambda s: s)

        # Allowed with override=True
        new_handler = lambda s: {"new": True}  # noqa: E731
        registry.register(
            "node",
            contract=contract,
            handler=new_handler,
            override=True,
        )
        assert registry.resolve("node") is new_handler

    def test_lazy_resolver_evaluation(self):
        registry = NodeRegistry()
        contract = NodeContract()
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return lambda s: {"result": call_count}

        registry.register("lazy_node", contract=contract, resolver=factory)
        # Registration does not invoke resolver
        assert call_count == 0
        handler = registry.resolve("lazy_node")
        assert call_count == 1
        assert callable(handler)

    def test_dependency_injection_isolation(self):
        registry_a = NodeRegistry()
        registry_b = NodeRegistry()

        contract = NodeContract()
        registry_a.register("node_x", contract=contract, handler=lambda s: s)
        assert registry_a.has("node_x")
        assert not registry_b.has("node_x")

    def test_unauthorized_module_resolution_rejected(self):
        with pytest.raises(PermissionError, match="Unauthorized module"):
            _resolve_module_attr("os", "system")

    def test_unwhitelisted_internal_attribute_resolution_rejected(self):
        with pytest.raises(PermissionError, match="Unauthorized module attribute"):
            _resolve_module_attr("huggingface_agents_langgraph.cli", "main")

    def test_gaia_v3_canonical_registry(self):
        registry = create_gaia_v3_registry()
        expected_nodes = [
            "answer_production",
            "attachment_resolver",
            "code_processing",
            "document_processing",
            "multimedia_processing",
            "preprocessing",
            "reasoning",
            "research_action",
            "review",
            "router",
            "spreadsheet_processing",
            "web_research",
        ]
        assert registry.list_implementations() == sorted(expected_nodes)

        # Verify contracts can be statically inspected without executing anything
        contract_prep = registry.get_contract("preprocessing")
        assert "question" in contract_prep.required_inputs
        assert "question" in contract_prep.guaranteed_outputs

        contract_router = registry.get_contract("router")
        assert "question" in contract_router.required_inputs
        assert "file_name" in contract_router.required_inputs
        assert "route" in contract_router.guaranteed_outputs

        # Test effective contracts considering wrappers and recovery paths
        contract_doc = registry.get_contract("document_processing")
        assert contract_doc.guaranteed_outputs == frozenset()
        assert "evidence" in contract_doc.optional_outputs
        assert "research_notes" in contract_doc.optional_outputs

        contract_action = registry.get_contract("research_action")
        assert "research_notes" in contract_action.guaranteed_outputs
        assert "evidence" in contract_action.guaranteed_outputs

        contract_reasoning = registry.get_contract("reasoning")
        assert "research_notes" in contract_reasoning.optional_inputs
        assert "evidence" in contract_reasoning.optional_inputs

        contract_ans = registry.get_contract("answer_production")
        assert "draft_answer" in contract_ans.required_inputs
        assert "submitted_answer" in contract_ans.guaranteed_outputs
        assert "answer_warnings" in contract_ans.guaranteed_outputs


class TestStabilizationPatch:
    def test_edge_conditional_targets_immutable(self):
        edge = EdgeDefinition(
            source="router",
            edge_type="conditional",
            routing_strategy="strat",
            conditional_targets={"a": "node_a"},
        )
        with pytest.raises(TypeError):
            edge.conditional_targets["a"] = "mutated"  # type: ignore

    def test_node_metadata_immutable(self):
        node = NodeDefinition(
            id="n1",
            implementation_id="preprocessing",
            metadata={"priority": 1, "nested": {"k": "v"}},
        )
        with pytest.raises(TypeError):
            node.metadata["priority"] = 2  # type: ignore

    def test_agent_metadata_immutable(self):
        agent = AgentDefinition(
            schema_version="4.0",
            architecture_id="arch",
            state_type="AgentState",
            initial_node="n1",
            nodes=(NodeDefinition(id="n1", implementation_id="preprocessing"),),
            metadata={"env": "prod"},
        )
        with pytest.raises(TypeError):
            agent.metadata["env"] = "dev"  # type: ignore

    def test_mutating_source_dict_does_not_mutate_definition(self):
        src_meta = {"key": "original", "list": [1, 2]}
        node = NodeDefinition(
            id="n1",
            implementation_id="preprocessing",
            metadata=src_meta,
        )
        src_meta["key"] = "modified_externally"
        src_meta["list"].append(3)
        assert node.metadata["key"] == "original"
        assert list(node.metadata["list"]) == [1, 2]

    def test_mutating_to_dict_does_not_mutate_definition(self):
        node = NodeDefinition(
            id="n1",
            implementation_id="preprocessing",
            metadata={"key": "original"},
        )
        data = node.to_dict()
        data["metadata"]["key"] = "tampered"
        assert node.metadata["key"] == "original"

    def test_node_definition_rejects_reserved_terminal_id(self):
        for reserved in ["START", "END", "__start__", "__end__"]:
            with pytest.raises(ValueError, match="reserved terminal name"):
                NodeDefinition(id=reserved, implementation_id="preprocessing")

    def test_metadata_must_be_json_serializable(self):
        class NonSerializable:
            pass

        with pytest.raises(ValueError, match="JSON-serializable"):
            NodeDefinition(
                id="n1",
                implementation_id="preprocessing",
                metadata={"obj": NonSerializable()},
            )

    def test_validate_inputs_semantics_presence_only(self):
        contract = NodeContract(
            required_inputs=frozenset({"question", "file_path"}),
            optional_inputs=frozenset({"task_id"}),
        )
        # 1. Key absent -> missing
        assert contract.validate_inputs({"question": "test"}) == ["file_path"]

        # 2. Key present with None -> considered present under key-presence semantics
        assert contract.validate_inputs({"question": "test", "file_path": None}) == []

        # 3. Key present with valid value -> present
        assert (
            contract.validate_inputs({"question": "test", "file_path": "doc.pdf"}) == []
        )

    def test_serialization_preserves_exact_declared_order(self):
        nodes = (
            NodeDefinition(id="b_node", implementation_id="b_impl"),
            NodeDefinition(id="a_node", implementation_id="a_impl"),
            NodeDefinition(id="c_node", implementation_id="c_impl"),
        )
        edges = (
            EdgeDefinition(source="b_node", target="a_node"),
            EdgeDefinition(source="a_node", target="c_node"),
            EdgeDefinition(source="c_node", target="END"),
        )
        agent = AgentDefinition(
            schema_version="4.0",
            architecture_id="order_test",
            state_type="AgentState",
            initial_node="b_node",
            nodes=nodes,
            edges=edges,
        )
        reconstructed = AgentDefinition.from_dict(agent.to_dict())
        assert [n.id for n in reconstructed.nodes] == [
            "b_node",
            "a_node",
            "c_node",
        ]
        assert [(e.source, e.target) for e in reconstructed.edges] == [
            ("b_node", "a_node"),
            ("a_node", "c_node"),
            ("c_node", "END"),
        ]


def _agent(**overrides):
    values = {
        "schema_version": "4.0",
        "architecture_id": "arch",
        "state_type": "AgentState",
        "initial_node": "n1",
        "nodes": (NodeDefinition(id="n1", implementation_id="preprocessing"),),
    }
    return AgentDefinition(**{**values, **overrides})


class TestStructuralValidation:
    @pytest.mark.parametrize("terminal", ["START", "END", "__start__", "__end__"])
    def test_initial_node_rejects_terminals(self, terminal):
        with pytest.raises(ValueError, match="initial_node"):
            _agent(initial_node=terminal)

    @pytest.mark.parametrize("terminal", ["START", "__start__"])
    def test_direct_edge_rejects_start_as_target(self, terminal):
        with pytest.raises(ValueError, match="START"):
            _agent(edges=(EdgeDefinition(source="n1", target=terminal),))

    @pytest.mark.parametrize("terminal", ["START", "__start__"])
    def test_conditional_branch_rejects_start_as_target(self, terminal):
        edge = EdgeDefinition(
            source="n1",
            edge_type="conditional",
            routing_strategy="strategy",
            conditional_targets={"back": terminal},
        )
        with pytest.raises(ValueError, match="START"):
            _agent(edges=(edge,))

    def test_start_remains_a_valid_edge_source(self):
        agent = _agent(edges=(EdgeDefinition(source="__start__", target="n1"),))
        assert agent.edges[0].source == "__start__"

    @pytest.mark.parametrize("key", ["", " ", "\t\n"])
    def test_conditional_rejects_blank_branch_keys(self, key):
        with pytest.raises(ValueError, match="branch key"):
            EdgeDefinition(
                source="n1",
                edge_type="conditional",
                routing_strategy="strategy",
                conditional_targets={key: "n2"},
            )

    def test_from_dict_rejects_blank_branch_keys(self):
        with pytest.raises(ValueError, match="branch key"):
            EdgeDefinition.from_dict(
                {
                    "source": "n1",
                    "edge_type": "conditional",
                    "routing_strategy": "strategy",
                    "conditional_targets": {" ": "n2"},
                }
            )

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_metadata_rejects_non_finite_numbers(self, value):
        with pytest.raises(ValueError, match="JSON-serializable"):
            NodeDefinition(id="n1", implementation_id="p", metadata={"v": value})
        with pytest.raises(ValueError, match="JSON-serializable"):
            _agent(metadata={"nested": [{"v": value}]})

    def test_metadata_accepts_finite_numbers(self):
        node = NodeDefinition(
            id="n1", implementation_id="p", metadata={"v": 1.5, "n": 0}
        )
        assert node.metadata["v"] == 1.5


class TestRecoverErrorsPolicy:
    ACQUISITION = {
        "code_processing",
        "spreadsheet_processing",
        "document_processing",
        "multimedia_processing",
        "web_research",
    }

    def test_default_is_not_recoverable(self):
        registry = NodeRegistry()
        registry.register("n", NodeContract(), handler=lambda state: {})
        assert registry.get_registration("n").recover_errors is False

    def test_registration_keeps_recover_errors(self):
        registry = NodeRegistry()
        registry.register(
            "n", NodeContract(), handler=lambda state: {}, recover_errors=True
        )
        assert registry.get_registration("n").recover_errors is True

    def test_v31_catalog_marks_exactly_the_acquisition_nodes(self):
        registry = create_gaia_v3_registry()
        recoverable = {
            name
            for name in registry.list_implementations()
            if registry.get_registration(name).recover_errors
        }
        assert recoverable == self.ACQUISITION

    def test_recoverable_nodes_declare_research_notes_as_optional_output(self):
        registry = create_gaia_v3_registry()
        for name in self.ACQUISITION:
            assert "research_notes" in registry.get_contract(name).all_outputs
