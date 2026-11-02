"""The canonical V3.1 components, as the runtime graph in ``graph.py`` compiles them.

Contracts describe the effective, observable behaviour of each node, considering
the recovery wrapper of the acquisition nodes and the tracing wrapper of all.
"""

from huggingface_agents_langgraph.graph_definition.authorization import (
    resolve_authorized_callable,
)
from huggingface_agents_langgraph.graph_definition.contracts import NodeContract
from huggingface_agents_langgraph.graph_definition.registry import NodeRegistry


def _register_input_nodes(registry: NodeRegistry) -> None:
    """Preprocessing, attachment resolution and routing."""
    # Preprocessing
    registry.register(
        "preprocessing",
        metadata={"category": "input"},
        contract=NodeContract(
            required_inputs=frozenset({"question"}),
            guaranteed_outputs=frozenset({"question"}),
        ),
        resolver=lambda: resolve_authorized_callable(
            "huggingface_agents_langgraph.preprocessing", "preprocessing"
        ),
        description="Normalizes whitespace and prepares question string.",
    )

    # Attachment Resolver
    registry.register(
        "attachment_resolver",
        metadata={"category": "input"},
        contract=NodeContract(
            required_inputs=frozenset({"file_name"}),
            optional_inputs=frozenset({"task_id"}),
            guaranteed_outputs=frozenset({"file_path"}),
        ),
        resolver=lambda: resolve_authorized_callable(
            "huggingface_agents_langgraph.attachments", "attachment_resolver"
        ),
        description="Resolves and verifies physical existence of attachment.",
    )

    # Router
    registry.register(
        "router",
        metadata={"category": "input"},
        contract=NodeContract(
            required_inputs=frozenset({"question", "file_name"}),
            optional_inputs=frozenset({"file_path"}),
            guaranteed_outputs=frozenset({"route"}),
        ),
        resolver=lambda: resolve_authorized_callable(
            "huggingface_agents_langgraph.routing", "router"
        ),
        description="Deterministic extension-based router with LLM fallback.",
    )


def _register_acquisition_nodes(registry: NodeRegistry) -> None:
    """The five nodes that gather evidence for a route."""
    # Acquisition Nodes (Wrapped by _recover_acquisition in graph.py):
    # If acquisition succeeds, produces evidence. If it raises an error,
    # the wrapper catches it and returns research_notes without evidence.
    # Therefore neither output is unconditionally guaranteed on its own.
    acquisition_contract = NodeContract(
        required_inputs=frozenset({"question", "file_path"}),
        guaranteed_outputs=frozenset(),
        optional_outputs=frozenset({"evidence", "research_notes"}),
    )

    # Code Processing
    registry.register(
        "code_processing",
        recover_errors=True,
        metadata={"category": "acquisition"},
        contract=acquisition_contract,
        resolver=lambda: resolve_authorized_callable(
            "huggingface_agents_langgraph.code_processing", "code_processing"
        ),
        description="Static inspection or sandboxed execution of Python code.",
    )

    # Spreadsheet Processing
    registry.register(
        "spreadsheet_processing",
        recover_errors=True,
        metadata={"category": "acquisition"},
        contract=acquisition_contract,
        resolver=lambda: resolve_authorized_callable(
            "huggingface_agents_langgraph.spreadsheet_processing",
            "spreadsheet_processing",
        ),
        description="Tabular data extraction and structured analysis.",
    )

    # Document Processing
    registry.register(
        "document_processing",
        recover_errors=True,
        metadata={"category": "acquisition"},
        contract=acquisition_contract,
        resolver=lambda: resolve_authorized_callable(
            "huggingface_agents_langgraph.document_processing",
            "document_processing",
        ),
        description="PDF text extraction with relevance filtering.",
    )

    # Multimedia Processing
    registry.register(
        "multimedia_processing",
        recover_errors=True,
        metadata={"category": "acquisition"},
        contract=acquisition_contract,
        resolver=lambda: resolve_authorized_callable(
            "huggingface_agents_langgraph.multimedia_processing",
            "multimedia_processing",
        ),
        description="Audio transcription, sound classification, and VLM inspection.",
    )

    # Web Research (file_path is optional)
    registry.register(
        "web_research",
        recover_errors=True,
        metadata={"category": "acquisition"},
        contract=NodeContract(
            required_inputs=frozenset({"question"}),
            optional_inputs=frozenset({"file_path"}),
            guaranteed_outputs=frozenset(),
            optional_outputs=frozenset({"evidence", "research_notes"}),
        ),
        resolver=lambda: resolve_authorized_callable(
            "huggingface_agents_langgraph.web_research", "web_research"
        ),
        description="Search engine and encyclopedia retrieval.",
    )


def _register_research_nodes(registry: NodeRegistry) -> None:
    """The review loop that decides what to research next."""
    # Review
    registry.register(
        "review",
        metadata={"category": "research"},
        contract=NodeContract(
            required_inputs=frozenset({"question"}),
            optional_inputs=frozenset(
                {"evidence", "research_action", "action_history", "research_steps"}
            ),
            guaranteed_outputs=frozenset({"research_action"}),
            optional_outputs=frozenset({"research_notes"}),
        ),
        resolver=lambda: resolve_authorized_callable(
            "huggingface_agents_langgraph.research", "review"
        ),
        description="Iterative review loop deciding the next research action.",
    )

    # Research Action
    registry.register(
        "research_action",
        metadata={"category": "research"},
        contract=NodeContract(
            required_inputs=frozenset({"question", "research_action"}),
            optional_inputs=frozenset({"evidence", "action_history", "research_steps"}),
            guaranteed_outputs=frozenset(
                {
                    "evidence",
                    "action_history",
                    "research_steps",
                    "research_notes",
                }
            ),
            optional_outputs=frozenset({"source_links"}),
        ),
        resolver=lambda: resolve_authorized_callable(
            "huggingface_agents_langgraph.research", "research_action"
        ),
        description="Dispatches and executes the action chosen by the review node.",
    )


def _register_answer_nodes(registry: NodeRegistry) -> None:
    """Reasoning and the final answer."""
    # Reasoning
    registry.register(
        "reasoning",
        metadata={"category": "reasoning"},
        contract=NodeContract(
            required_inputs=frozenset({"question"}),
            optional_inputs=frozenset({"evidence", "research_notes"}),
            guaranteed_outputs=frozenset({"draft_answer"}),
            optional_outputs=frozenset({"reasoning_warnings"}),
        ),
        resolver=lambda: resolve_authorized_callable(
            "huggingface_agents_langgraph.reasoning", "reasoning"
        ),
        description="Synthesizes evidence to produce a reasoning draft answer.",
    )

    # Answer Production
    registry.register(
        "answer_production",
        metadata={"category": "output"},
        contract=NodeContract(
            required_inputs=frozenset({"question", "draft_answer"}),
            guaranteed_outputs=frozenset({"submitted_answer", "answer_warnings"}),
            optional_outputs=frozenset(),
        ),
        resolver=lambda: resolve_authorized_callable(
            "huggingface_agents_langgraph.answer_production",
            "answer_production",
        ),
        description="Formats concise final answer adhering to GAIA conventions.",
    )


def create_gaia_v3_registry() -> NodeRegistry:
    """Create a registry pre-loaded with the canonical V3.1 node contracts."""
    registry = NodeRegistry()
    _register_input_nodes(registry)
    _register_acquisition_nodes(registry)
    _register_research_nodes(registry)
    _register_answer_nodes(registry)
    return registry
