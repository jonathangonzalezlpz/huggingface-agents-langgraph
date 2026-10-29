"""StateGraph construction for the LangGraph workflow."""

from functools import wraps
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from huggingface_agents_langgraph.answer_production import answer_production
from huggingface_agents_langgraph.attachments import attachment_resolver
from huggingface_agents_langgraph.code_processing import code_processing
from huggingface_agents_langgraph.document_processing import document_processing
from huggingface_agents_langgraph.experiments import (
    DEFAULT_EXPERIMENT,
    is_capability_enabled,
)
from huggingface_agents_langgraph.multimedia_processing import multimedia_processing
from huggingface_agents_langgraph.preprocessing import preprocessing
from huggingface_agents_langgraph.reasoning import reasoning
from huggingface_agents_langgraph.research import research_action, review
from huggingface_agents_langgraph.routing import capability_for_attachment, router
from huggingface_agents_langgraph.run_tracking import traced_node
from huggingface_agents_langgraph.spreadsheet_processing import spreadsheet_processing
from huggingface_agents_langgraph.state import AgentState
from huggingface_agents_langgraph.web_research import web_research


def _route_after_preprocessing(
    state: AgentState,
) -> Literal["resolve_attachment", "skip_attachment"]:
    """Choose whether the workflow needs to resolve an attachment."""
    experiment = state.get("experiment", DEFAULT_EXPERIMENT)
    if experiment["force_direct"]:
        return "skip_attachment"
    file_name = state["file_name"].strip()
    if file_name:
        capability = capability_for_attachment(file_name)
        if capability and not is_capability_enabled(experiment, capability):
            return "skip_attachment"
        return "resolve_attachment"
    return "skip_attachment"


def _route_after_router(
    state: AgentState,
) -> Literal[
    "code", "spreadsheet", "document", "multimedia", "web", "direct", "finish"
]:
    """Send tasks to a source-specific node or directly to reasoning."""
    experiment = state.get("experiment", DEFAULT_EXPERIMENT)
    if experiment["force_direct"]:
        return "direct"
    capability = {
        "code": "code",
        "spreadsheet": "spreadsheet",
        "document": "document",
        "multimedia": "multimedia",
        "web": "web",
        "wikipedia": "web",
    }.get(state.get("route", ""))
    if capability and not is_capability_enabled(experiment, capability):
        return "direct"
    if state.get("route") == "code":
        return "code"
    if state.get("route") == "spreadsheet":
        return "spreadsheet"
    if state.get("route") == "document":
        return "document"
    if state.get("route") == "multimedia":
        return "multimedia"
    if state.get("route") in {"web", "wikipedia"}:
        return "web"
    if state.get("route") == "direct":
        return "direct"
    return "finish"


def _recover_acquisition(function):
    @wraps(function)
    def wrapped(state):
        try:
            return traced_node(function)(state)
        except (ValueError, RuntimeError, OSError) as error:
            return {
                "research_notes": [
                    *state.get("research_notes", []),
                    f"{function.__name__}: {error}",
                ]
            }

    return wrapped


def _route_after_review(state: AgentState) -> Literal["act", "solve"]:
    return (
        "solve" if state.get("research_action", {}).get("action") == "finish" else "act"
    )


def build_state_graph() -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    """Build and compile the preprocessing, attachment, and routing workflow."""
    graph = StateGraph(AgentState)

    graph.add_node("preprocessing", traced_node(preprocessing))
    graph.add_node("attachment_resolver", traced_node(attachment_resolver))
    graph.add_node("router", traced_node(router))
    graph.add_node("code_processing", _recover_acquisition(code_processing))
    graph.add_node(
        "spreadsheet_processing", _recover_acquisition(spreadsheet_processing)
    )
    graph.add_node("document_processing", _recover_acquisition(document_processing))
    graph.add_node("multimedia_processing", _recover_acquisition(multimedia_processing))
    graph.add_node("web_research", _recover_acquisition(web_research))
    graph.add_node("review", traced_node(review))
    graph.add_node("research_action", traced_node(research_action))
    graph.add_node("reasoning", traced_node(reasoning))
    graph.add_node("answer_production", traced_node(answer_production))

    graph.add_edge(START, "preprocessing")
    graph.add_conditional_edges(
        "preprocessing",
        _route_after_preprocessing,
        {
            "resolve_attachment": "attachment_resolver",
            "skip_attachment": "router",
        },
    )
    graph.add_edge("attachment_resolver", "router")
    graph.add_conditional_edges(
        "router",
        _route_after_router,
        {
            "code": "code_processing",
            "spreadsheet": "spreadsheet_processing",
            "document": "document_processing",
            "multimedia": "multimedia_processing",
            "web": "web_research",
            "direct": "review",
            "finish": "review",
        },
    )
    for node in (
        "code_processing",
        "spreadsheet_processing",
        "document_processing",
        "multimedia_processing",
        "web_research",
    ):
        graph.add_edge(node, "review")
    graph.add_conditional_edges(
        "review", _route_after_review, {"act": "research_action", "solve": "reasoning"}
    )
    graph.add_edge("research_action", "review")
    graph.add_edge("reasoning", "answer_production")
    graph.add_edge("answer_production", END)

    return graph.compile()
