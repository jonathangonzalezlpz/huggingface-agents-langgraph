"""StateGraph construction for the LangGraph workflow."""

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from huggingface_agents_langgraph.answer_production import answer_production
from huggingface_agents_langgraph.attachments import attachment_resolver
from huggingface_agents_langgraph.code_processing import code_processing
from huggingface_agents_langgraph.preprocessing import preprocessing
from huggingface_agents_langgraph.reasoning import reasoning
from huggingface_agents_langgraph.routing import router
from huggingface_agents_langgraph.state import AgentState


def _route_after_preprocessing(
    state: AgentState,
) -> Literal["resolve_attachment", "skip_attachment"]:
    """Choose whether the workflow needs to resolve an attachment."""
    if state["file_name"].strip():
        return "resolve_attachment"
    return "skip_attachment"


def _route_after_router(state: AgentState) -> Literal["code", "finish"]:
    """Send supported Python tasks to code processing."""
    if state.get("route") == "code":
        return "code"
    return "finish"


def build_state_graph() -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    """Build and compile the preprocessing, attachment, and routing workflow."""
    graph = StateGraph(AgentState)

    graph.add_node("preprocessing", preprocessing)
    graph.add_node("attachment_resolver", attachment_resolver)
    graph.add_node("router", router)
    graph.add_node("code_processing", code_processing)
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
        {"code": "code_processing", "finish": END},
    )
    graph.add_edge("code_processing", "reasoning")
    graph.add_edge("reasoning", "answer_production")
    graph.add_edge("answer_production", END)

    return graph.compile()
