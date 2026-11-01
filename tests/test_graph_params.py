"""Per-node parameters: typed specs, serialization, validation and compilation."""

import pytest

from huggingface_agents_langgraph.architecture_store import content_sha256
from huggingface_agents_langgraph.graph_definition import (
    AgentDefinition,
    EdgeDefinition,
    GraphCompiler,
    NodeContract,
    NodeDefinition,
    NodeRegistry,
    RoutingRegistry,
)
from huggingface_agents_langgraph.graph_definition.catalog import build_catalog
from huggingface_agents_langgraph.graph_definition.definitions import (
    create_gaia_v31_definition,
)
from huggingface_agents_langgraph.graph_definition.params import (
    ParamError,
    ParamSpec,
)
from huggingface_agents_langgraph.graph_definition.validator import GraphValidator

# Pinned before parameters existed: adding them must not change saved versions.
BUILTIN_V31_HASH = "e42d786d3179bdc42045947dfea1e459c265398f8189ed33fa5308674cfdeb44"

TASK = {"task_id": "t", "question": "q", "file_name": ""}


class TestParamSpec:
    def test_integer_is_checked_against_its_range(self):
        spec = ParamSpec("n", "integer", default=3, minimum=1, maximum=5)
        assert spec.validate(2) == 2
        for bad in (0, 6, 1.5, "2", True):
            with pytest.raises(ParamError):
                spec.validate(bad)

    def test_number_accepts_integers_and_floats_but_not_nan(self):
        spec = ParamSpec("t", "number", default=0.0, minimum=0.0, maximum=2.0)
        assert spec.validate(1) == 1
        assert spec.validate(0.5) == 0.5
        for bad in (-0.1, 2.1, float("nan"), "1", True):
            with pytest.raises(ParamError):
                spec.validate(bad)

    def test_boolean_must_be_a_real_boolean(self):
        spec = ParamSpec("flag", "boolean", default=False)
        assert spec.validate(True) is True
        with pytest.raises(ParamError):
            spec.validate(1)

    def test_enum_only_takes_declared_choices(self):
        spec = ParamSpec("mode", "enum", default="a", choices=("a", "b"))
        assert spec.validate("b") == "b"
        with pytest.raises(ParamError):
            spec.validate("c")

    def test_string_and_text_have_a_length_cap(self):
        short = ParamSpec("q", "string", default="", max_length=5)
        assert short.validate("abc") == "abc"
        with pytest.raises(ParamError):
            short.validate("abcdef")
        with pytest.raises(ParamError):
            short.validate(3)
        text = ParamSpec("prompt", "text", default="", max_length=10)
        with pytest.raises(ParamError):
            text.validate("x" * 11)

    def test_a_spec_must_be_consistent_with_itself(self):
        with pytest.raises(ValueError):
            ParamSpec("x", "enum", default="a")  # no choices
        with pytest.raises(ValueError):
            ParamSpec("x", "integer", default=10, minimum=1, maximum=5)
        with pytest.raises(ValueError):
            ParamSpec("x", "weird", default=1)
        with pytest.raises(ValueError):
            ParamSpec("", "boolean", default=True)

    def test_round_trips_through_json(self):
        spec = ParamSpec("mode", "enum", default="a", choices=("a", "b"), required=True)
        assert ParamSpec.from_dict(spec.to_dict()) == spec


class TestNodeDefinitionParams:
    def test_params_are_serialized_only_when_present(self):
        plain = NodeDefinition("n", "impl")
        assert "params" not in plain.to_dict()
        tuned = NodeDefinition("n", "impl", params={"n": 3})
        assert tuned.to_dict()["params"] == {"n": 3}
        assert NodeDefinition.from_dict(tuned.to_dict()) == tuned

    def test_params_must_be_json(self):
        with pytest.raises(ValueError):
            NodeDefinition("n", "impl", params={"n": object()})

    def test_the_builtin_version_keeps_its_hash(self):
        assert content_sha256(create_gaia_v31_definition()) == BUILTIN_V31_HASH

    def test_different_params_give_different_versions(self):
        def build(value):
            return AgentDefinition(
                "1",
                "a",
                "AgentState",
                "n",
                (NodeDefinition("n", "impl", params={"n": value}),),
                (EdgeDefinition("n", "__end__"),),
            )

        assert content_sha256(build(1)) != content_sha256(build(2))


def _registry(calls):
    registry = NodeRegistry()

    def build(params):
        def run(state):
            calls.append(dict(params))
            return {"draft_answer": f"n={params['n']}:{params['mode']}"}

        return run

    registry.register(
        "tunable",
        NodeContract(required_inputs={"question"}, guaranteed_outputs={"draft_answer"}),
        builder=build,
        params=(
            ParamSpec("n", "integer", default=2, minimum=1, maximum=9),
            ParamSpec("mode", "enum", default="fast", choices=("fast", "slow")),
            ParamSpec("label", "string", default="", required=True, max_length=8),
        ),
    )
    registry.register(
        "plain",
        NodeContract(required_inputs={"question"}, guaranteed_outputs={"draft_answer"}),
        handler=lambda state: {"draft_answer": "plain"},
    )
    return registry


def _definition(**params):
    return AgentDefinition(
        "1",
        "tuned",
        "AgentState",
        "t",
        (NodeDefinition("t", "tunable", params=params),),
        (EdgeDefinition("t", "__end__"),),
    )


def _codes(definition, registry=None):
    validator = GraphValidator(registry or _registry([]), RoutingRegistry())
    return [d.code for d in validator.validate(definition).diagnostics]


class TestRegistration:
    def test_defaults_are_filled_in_when_building(self):
        calls = []
        registration = _registry(calls).get_registration("tunable")
        registration.build_handler({"label": "x"})({"question": "q"})
        assert calls == [{"n": 2, "mode": "fast", "label": "x"}]

    def test_the_resolved_params_are_available_without_building(self):
        registration = _registry([]).get_registration("tunable")
        assert registration.resolve_params({"n": 5, "label": "x"}) == {
            "n": 5,
            "mode": "fast",
            "label": "x",
        }

    def test_params_are_refused_by_a_component_without_specs(self):
        registration = _registry([]).get_registration("plain")
        with pytest.raises(ParamError):
            registration.resolve_params({"n": 1})

    def test_a_plain_component_builds_its_handler_as_before(self):
        registration = _registry([]).get_registration("plain")
        assert registration.build_handler({})({"question": "q"}) == {
            "draft_answer": "plain"
        }

    def test_a_builder_needs_specs_to_be_meaningful(self):
        registry = NodeRegistry()
        with pytest.raises(ValueError):
            registry.register(
                "bad", NodeContract(), builder=lambda params: lambda state: {}
            )

    def test_a_registration_needs_exactly_one_way_to_run(self):
        registry = NodeRegistry()
        with pytest.raises(ValueError):
            registry.register("none", NodeContract())
        with pytest.raises(ValueError):
            registry.register(
                "two",
                NodeContract(),
                handler=lambda state: {},
                builder=lambda params: lambda state: {},
                params=(ParamSpec("n", "boolean", default=True),),
            )


class TestValidation:
    def test_valid_params_raise_nothing(self):
        assert _codes(_definition(n=3, mode="slow", label="ok")) == []

    def test_a_required_param_without_a_default_must_be_given(self):
        assert "MISSING_PARAM" in _codes(_definition(n=3))

    def test_unknown_params_are_reported(self):
        codes = _codes(_definition(label="ok", color="red"))
        assert "UNKNOWN_PARAM" in codes

    def test_invalid_values_are_reported_with_the_node_and_param(self):
        report = GraphValidator(_registry([]), RoutingRegistry()).validate(
            _definition(n=99, label="ok")
        )
        finding = next(d for d in report.diagnostics if d.code == "INVALID_PARAM_VALUE")
        assert finding.severity == "error"
        assert finding.node_id == "t"
        assert finding.details["param"] == "n"

    def test_params_on_a_component_without_specs_are_unknown(self):
        definition = AgentDefinition(
            "1",
            "x",
            "AgentState",
            "p",
            (NodeDefinition("p", "plain", params={"n": 1}),),
            (EdgeDefinition("p", "__end__"),),
        )
        assert "UNKNOWN_PARAM" in _codes(definition)


class TestCompilation:
    def test_the_node_runs_with_its_own_params(self):
        calls = []
        compiler = GraphCompiler(_registry(calls), RoutingRegistry())
        graph = compiler.compile(_definition(n=4, mode="slow", label="ok"))
        result = graph.invoke(dict(TASK))
        assert result["draft_answer"] == "n=4:slow"
        assert calls == [{"n": 4, "mode": "slow", "label": "ok"}]

    def test_two_nodes_of_one_component_keep_separate_params(self):
        calls = []
        definition = AgentDefinition(
            "1",
            "twice",
            "AgentState",
            "a",
            (
                NodeDefinition("a", "tunable", params={"n": 1, "label": "a"}),
                NodeDefinition("b", "tunable", params={"n": 7, "label": "b"}),
            ),
            (EdgeDefinition("a", "b"), EdgeDefinition("b", "__end__")),
        )
        GraphCompiler(_registry(calls), RoutingRegistry()).compile(definition).invoke(
            dict(TASK)
        )
        assert [c["n"] for c in calls] == [1, 7]

    def test_invalid_params_stop_compilation(self):
        from huggingface_agents_langgraph.graph_definition import GraphCompilationError

        compiler = GraphCompiler(_registry([]), RoutingRegistry())
        with pytest.raises(GraphCompilationError):
            compiler.compile(_definition(n=99, label="ok"))


class TestCatalog:
    def test_components_list_their_param_specs(self):
        catalog = build_catalog(
            _registry([]),
            RoutingRegistry(),
            state_types=["AgentState"],
            state_fields=["question"],
            initial_fields=["question"],
        )
        nodes = {node["implementation_id"]: node for node in catalog["nodes"]}
        assert nodes["plain"]["params"] == []
        tunable = {spec["name"]: spec for spec in nodes["tunable"]["params"]}
        assert tunable["n"] == {
            "name": "n",
            "kind": "integer",
            "default": 2,
            "required": False,
            "minimum": 1,
            "maximum": 9,
        }
        assert tunable["mode"]["choices"] == ["fast", "slow"]
        assert tunable["label"]["required"] is True
        assert tunable["label"]["max_length"] == 8


class TestRunRecord:
    def test_the_compiler_reports_the_resolved_params_per_node(self):
        compiler = GraphCompiler(_registry([]), RoutingRegistry())
        resolved = compiler.resolved_params(_definition(n=4, label="ok"))
        assert resolved == {"t": {"n": 4, "mode": "fast", "label": "ok"}}

    def test_nodes_without_specs_are_left_out(self):
        definition = AgentDefinition(
            "1",
            "x",
            "AgentState",
            "p",
            (NodeDefinition("p", "plain"),),
            (EdgeDefinition("p", "__end__"),),
        )
        compiler = GraphCompiler(_registry([]), RoutingRegistry())
        assert compiler.resolved_params(definition) == {}

    def test_the_selected_graph_records_them_in_the_run_description(
        self, monkeypatch, tmp_path
    ):
        from huggingface_agents_langgraph import graph_selection, run_tracking
        from huggingface_agents_langgraph.architecture_store import save_architecture

        monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))
        monkeypatch.setattr(
            graph_selection, "create_gaia_v3_registry", lambda: _registry([])
        )
        saved = save_architecture(_definition(n=6, label="rec"))
        _graph, info = graph_selection.select_graph({"architecture": saved["id"]})
        assert info["node_params"] == {"t": {"n": 6, "mode": "fast", "label": "rec"}}

    def test_a_version_without_params_adds_nothing_to_the_description(self):
        from huggingface_agents_langgraph.architecture_store import BUILTIN_V31_ID
        from huggingface_agents_langgraph.graph_selection import select_graph

        _graph, info = select_graph({"architecture": BUILTIN_V31_ID})
        assert "node_params" not in info
