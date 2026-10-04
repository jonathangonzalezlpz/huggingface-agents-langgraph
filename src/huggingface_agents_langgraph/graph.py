"""StateGraph construction for the LangGraph workflow."""

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from huggingface_agents_langgraph.attachments import attachment_resolver
from huggingface_agents_langgraph.preprocessing import preprocessing
from huggingface_agents_langgraph.routing import router
from huggingface_agents_langgraph.state import AgentState


def _route_after_preprocessing(
    state: AgentState,
) -> Literal["resolve_attachment", "skip_attachment"]:
    """Choose whether the workflow needs to resolve an attachment."""
    if state["file_name"].strip():
        return "resolve_attachment"
    return "skip_attachment"


def build_state_graph() -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    """Build and compile the preprocessing, attachment, and routing workflow."""
    graph = StateGraph(AgentState)

    graph.add_node("preprocessing", preprocessing)
    graph.add_node("attachment_resolver", attachment_resolver)
    graph.add_node("router", router)

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
    graph.add_edge("router", END)

    return graph.compile()
