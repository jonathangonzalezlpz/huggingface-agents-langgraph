"""Configurable components that call the model: planner, verifier, reflection, vote."""

from huggingface_agents_langgraph.graph_definition.authorization import (
    resolve_authorized_callable,
)
from huggingface_agents_langgraph.graph_definition.contracts import NodeContract
from huggingface_agents_langgraph.graph_definition.params import ParamSpec
from huggingface_agents_langgraph.graph_definition.registry import NodeRegistry


def register_llm_roles(registry: NodeRegistry) -> None:
    """Configurable roles that call the model; none of them is part of V3.1."""

    def builder(name: str):
        return lambda params: resolve_authorized_callable(
            "huggingface_agents_langgraph.studio.llm_roles", name
        )(params)

    registry.register(
        "llm_planner",
        metadata={"category": "planning"},
        contract=NodeContract(
            required_inputs=frozenset({"question"}),
            optional_inputs=frozenset({"research_notes"}),
            guaranteed_outputs=frozenset({"plan", "research_notes"}),
        ),
        builder=builder("build_planner"),
        params=(
            ParamSpec("max_steps", "integer", default=4, minimum=1, maximum=8),
            ParamSpec("max_tokens", "integer", default=400, minimum=64, maximum=2048),
        ),
        description="Breaks the question into a short plan the next nodes can follow.",
    )
    registry.register(
        "llm_verifier",
        metadata={"category": "verification"},
        contract=NodeContract(
            required_inputs=frozenset({"question", "draft_answer"}),
            optional_inputs=frozenset({"evidence", "revision_count"}),
            guaranteed_outputs=frozenset({"verdict"}),
        ),
        builder=builder("build_verifier"),
        params=(
            ParamSpec("max_revisions", "integer", default=1, minimum=0, maximum=5),
            ParamSpec(
                "strictness", "enum", default="strict", choices=("strict", "lenient")
            ),
            ParamSpec("max_tokens", "integer", default=300, minimum=64, maximum=1024),
        ),
        description="Judges the draft answer and decides whether it needs revising.",
    )
    registry.register(
        "llm_reflect",
        metadata={"category": "verification"},
        contract=NodeContract(
            required_inputs=frozenset({"question", "draft_answer", "verdict"}),
            optional_inputs=frozenset({"evidence", "revision_count"}),
            guaranteed_outputs=frozenset({"draft_answer", "revision_count"}),
        ),
        builder=builder("build_reflect"),
        params=(
            ParamSpec("max_tokens", "integer", default=1024, minimum=128, maximum=4096),
            ParamSpec("thinking", "boolean", default=False),
        ),
        description="Revises the draft answer using the verifier's critique.",
    )
    registry.register(
        "self_consistency",
        metadata={"category": "reasoning"},
        contract=NodeContract(
            required_inputs=frozenset({"question"}),
            optional_inputs=frozenset({"evidence", "research_notes"}),
            guaranteed_outputs=frozenset({"draft_answer", "candidates"}),
        ),
        builder=builder("build_self_consistency"),
        params=(
            ParamSpec("n", "integer", default=3, minimum=1, maximum=7),
            ParamSpec("temperature", "number", default=0.7, minimum=0.0, maximum=1.5),
            ParamSpec("max_tokens", "integer", default=600, minimum=128, maximum=4096),
        ),
        description="Samples several answers in turn and keeps the majority vote.",
    )
