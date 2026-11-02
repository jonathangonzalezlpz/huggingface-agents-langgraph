"""Components that gather evidence with the vetted tools of ``tool_library``."""

from huggingface_agents_langgraph.graph_definition.authorization import (
    resolve_authorized_callable,
)
from huggingface_agents_langgraph.graph_definition.contracts import NodeContract
from huggingface_agents_langgraph.graph_definition.params import ParamSpec
from huggingface_agents_langgraph.graph_definition.registry import NodeRegistry


def register_tool_components(registry: NodeRegistry) -> None:
    """Components that add evidence with the vetted tools of ``tool_library``."""
    from huggingface_agents_langgraph.studio.tool_library import TOOLS

    module = "huggingface_agents_langgraph.studio.tool_components"

    def builder(name: str):
        return lambda params: resolve_authorized_callable(module, name)(params)

    gathering = {
        "optional_inputs": frozenset(
            {"evidence", "research_notes", "source_links", "draft_answer"}
        ),
        "optional_outputs": frozenset({"evidence", "research_notes", "source_links"}),
    }
    query = ParamSpec(
        "query",
        "string",
        default="",
        max_length=200,
    )
    registry.register(
        "tool_node",
        metadata={"category": "tools"},
        recover_errors=True,
        contract=NodeContract(required_inputs=frozenset({"question"}), **gathering),
        builder=builder("build_tool_node"),
        params=(
            ParamSpec("tool", "enum", default="web_search", choices=tuple(TOOLS)),
            ParamSpec(
                "input_from",
                "enum",
                default="question",
                choices=("question", "draft_answer", "text"),
            ),
            ParamSpec("text", "string", default="", max_length=200),
        ),
        description="Runs one vetted tool and adds what it finds to the evidence.",
    )
    registry.register(
        "web_search",
        metadata={"category": "tools"},
        recover_errors=True,
        contract=NodeContract(required_inputs=frozenset({"question"}), **gathering),
        builder=builder("build_web_search"),
        params=(query,),
        description="Searches the web with the question (or a fixed query).",
    )
    registry.register(
        "wikipedia_search",
        metadata={"category": "tools"},
        recover_errors=True,
        contract=NodeContract(required_inputs=frozenset({"question"}), **gathering),
        builder=builder("build_wikipedia_search"),
        params=(query,),
        description="Searches Wikipedia with the question (or a fixed query).",
    )
    registry.register(
        "calculator",
        metadata={"category": "tools"},
        recover_errors=True,
        contract=NodeContract(required_inputs=frozenset({"question"}), **gathering),
        builder=builder("build_calculator"),
        params=(
            ParamSpec("max_tokens", "integer", default=160, minimum=32, maximum=512),
        ),
        description="Has the model write one expression and evaluates it safely.",
    )
    media = {
        "required_inputs": frozenset({"question", "file_path"}),
        "optional_inputs": frozenset({"evidence", "research_notes", "source_links"}),
        "optional_outputs": frozenset({"evidence", "research_notes", "source_links"}),
    }
    registry.register(
        "transcribe_audio",
        metadata={"category": "acquisition"},
        recover_errors=True,
        contract=NodeContract(**media),
        resolver=lambda: resolve_authorized_callable(module, "transcribe_audio"),
        description="Transcribes the attached audio file.",
    )
    registry.register(
        "describe_image",
        metadata={"category": "acquisition"},
        recover_errors=True,
        contract=NodeContract(**media),
        resolver=lambda: resolve_authorized_callable(module, "describe_image"),
        description="Describes the attached image with the vision model.",
    )
