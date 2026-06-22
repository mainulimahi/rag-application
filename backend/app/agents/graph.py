"""LangGraph RAG agent — graph construction and public run_agent entrypoint."""

import logging
from uuid import UUID

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes import retrieval_node, router_node, synthesis_node, websearch_node
from app.agents.state import AgentState
from app.services.llm_service import LLMMessage

logger = logging.getLogger(__name__)


def _build_graph() -> StateGraph:
    """Compile the RAG agent graph.

    Graph topology:
        router → retrieval → [websearch] → synthesis → END
               → websearch  → synthesis → END
               → synthesis  → END          (llm_only)
    """
    graph: StateGraph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("websearch", websearch_node)
    graph.add_node("synthesis", synthesis_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        lambda state: state["route"],
        {
            "llm_only": "synthesis",
            "retrieval": "retrieval",
            "web_search": "websearch",
            "both": "retrieval",  # retrieval first, then websearch
        },
    )

    # After retrieval: if route is "both" continue to websearch; else synthesise
    graph.add_conditional_edges(
        "retrieval",
        lambda state: "websearch" if state["route"] == "both" else "synthesis",
        {
            "websearch": "websearch",
            "synthesis": "synthesis",
        },
    )

    graph.add_edge("websearch", "synthesis")
    graph.add_edge("synthesis", END)

    return graph.compile()


# Compiled once at import time — stateless graph reused across all requests.
_agent_graph = _build_graph()


async def run_agent(
    db: AsyncSession,
    user_id: UUID,
    messages: list[LLMMessage],
) -> tuple[str, str]:
    """
    Run the RAG agent for a single conversation turn.

    Args:
        db: AsyncSession scoped to the current request.
        user_id: Authenticated user — all retrieval is scoped to this ID.
        messages: Full conversation history including the current user message.

    Returns:
        (answer, sources) where sources is one of:
        "llm_only" | "retrieval" | "web_search" | "both".
    """
    query = messages[-1]["content"]

    initial_state: AgentState = {
        "query": query,
        "messages": list(messages),
        "has_documents": False,
        "route": "llm_only",
        "retrieved_chunks": [],
        "web_results": [],
        "answer": "",
        "sources": "llm_only",
    }

    result = await _agent_graph.ainvoke(
        initial_state,
        config={"configurable": {"db": db, "user_id": user_id}},
    )

    return result["answer"], result["sources"]
