"""Closed whitelist of the callables a declared node may be bound to.

Nothing is imported by name from user data: a registration points at one of the
(module, attribute) pairs below, and anything else is refused.
"""

from collections.abc import Callable
from typing import Any

# Exact whitelist of approved internal node implementations
AUTHORIZED_CALLABLES: frozenset[tuple[str, str]] = frozenset(
    {
        ("huggingface_agents_langgraph.pipeline.preprocessing", "preprocessing"),
        ("huggingface_agents_langgraph.pipeline.attachments", "attachment_resolver"),
        ("huggingface_agents_langgraph.pipeline.routing", "router"),
        ("huggingface_agents_langgraph.pipeline.code_processing", "code_processing"),
        (
            "huggingface_agents_langgraph.pipeline.spreadsheet_processing",
            "spreadsheet_processing",
        ),
        (
            "huggingface_agents_langgraph.pipeline.document_processing",
            "document_processing",
        ),
        (
            "huggingface_agents_langgraph.pipeline.multimedia_processing",
            "multimedia_processing",
        ),
        ("huggingface_agents_langgraph.pipeline.web_research", "web_research"),
        ("huggingface_agents_langgraph.pipeline.research", "review"),
        ("huggingface_agents_langgraph.pipeline.research", "research_action"),
        ("huggingface_agents_langgraph.pipeline.reasoning", "reasoning"),
        (
            "huggingface_agents_langgraph.pipeline.answer_production",
            "answer_production",
        ),
    }
)

# Builders and handlers of the Studio components (LLM roles and tool components),
# which are not part of the V3.1 pipeline.
AUTHORIZED_ROLE_BUILDERS: frozenset[tuple[str, str]] = frozenset(
    {
        ("huggingface_agents_langgraph.studio.tool_components", "build_tool_node"),
        ("huggingface_agents_langgraph.studio.tool_components", "build_web_search"),
        (
            "huggingface_agents_langgraph.studio.tool_components",
            "build_wikipedia_search",
        ),
        ("huggingface_agents_langgraph.studio.tool_components", "build_calculator"),
        ("huggingface_agents_langgraph.studio.tool_components", "transcribe_audio"),
        ("huggingface_agents_langgraph.studio.tool_components", "describe_image"),
        ("huggingface_agents_langgraph.studio.llm_roles", "build_planner"),
        ("huggingface_agents_langgraph.studio.llm_roles", "build_verifier"),
        ("huggingface_agents_langgraph.studio.llm_roles", "build_reflect"),
        ("huggingface_agents_langgraph.studio.llm_roles", "build_self_consistency"),
    }
)


def resolve_authorized_callable(module_name: str, attr_name: str) -> Callable[..., Any]:
    """Safe internal resolver for pre-approved internal node functions only.

    NOTE: Resolving these base functions directly provides the pure node callables,
    not the recovery and tracing wrappers (_recover_acquisition, traced_node) applied
    in graph.py.
    """
    import importlib

    if (module_name, attr_name) not in AUTHORIZED_CALLABLES | AUTHORIZED_ROLE_BUILDERS:
        raise PermissionError(
            "Unauthorized module attribute resolution attempt: "
            f"'{module_name}.{attr_name}'"
        )
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)
