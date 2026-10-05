"""StateGraph construction for the LangGraph workflow."""

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from huggingface_agents_langgraph.answer_production import answer_production
from huggingface_agents_langgraph.attachments import attachment_resolver
from huggingface_agents_langgraph.code_processing import code_processing
from huggingface_agents_langgraph.document_processing import document_processing
from huggingface_agents_langgraph.multimedia_processing import multimedia_processing
from huggingface_agents_langgraph.preprocessing import preprocessing
from huggingface_agents_langgraph.reasoning import reasoning
from huggingface_agents_langgraph.routing import router
from huggingface_agents_langgraph.spreadsheet_processing import spreadsheet_processing
from huggingface_agents_langgraph.state import AgentState
from huggingface_agents_langgraph.web_research import web_research


def _route_after_preprocessing(
    state: AgentState,
) -> Literal["resolve_attachment", "skip_attachment"]:
    """Choose whether the workflow needs to resolve an attachment."""
    if state["file_name"].strip():
        return "resolve_attachment"
    return "skip_attachment"


def _route_after_router(
    state: AgentState,
) -> Literal[
    "code", "spreadsheet", "document", "multimedia", "web", "direct", "finish"
]:
    """Send tasks to a source-specific node or directly to reasoning."""
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


def build_state_graph() -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    """Build and compile the preprocessing, attachment, and routing workflow."""
    graph = StateGraph(AgentState)

    graph.add_node("preprocessing", preprocessing)
    graph.add_node("attachment_resolver", attachment_resolver)
    graph.add_node("router", router)
    graph.add_node("code_processing", code_processing)
    graph.add_node("spreadsheet_processing", spreadsheet_processing)
    graph.add_node("document_processing", document_processing)
    graph.add_node("multimedia_processing", multimedia_processing)
    graph.add_node("web_research", web_research)
    graph.add_node("reasoning", reasoning)
    graph.add_node("answer_production", answer_production)

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
            "direct": "reasoning",
            "finish": END,
        },
    )
    graph.add_edge("code_processing", "reasoning")
    graph.add_edge("spreadsheet_processing", "reasoning")
    graph.add_edge("document_processing", "reasoning")
    graph.add_edge("multimedia_processing", "reasoning")
    graph.add_edge("web_research", "reasoning")
    graph.add_edge("reasoning", "answer_production")
    graph.add_edge("answer_production", END)

    return graph.compile()
