"""LangGraph RAG agent — graph construction and public run_agent entrypoint."""

import logging
from collections.abc import AsyncIterator
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.data_agent_node import run_data_analysis
from app.agents.nodes import retrieval_node, router_node, synthesis_node, websearch_node
from app.agents.state import AgentState
from app.core.exceptions import LLMProviderError, RateLimitError
from app.services.llm_service import LLMMessage

logger = logging.getLogger(__name__)

# Status messages keyed by node name (matches graph.add_node() keys).
_NODE_STATUS: dict[str, str] = {
    "router": "🤔 Thinking…",
    "retrieval": "🔍 Searching your documents…",
    "websearch": "🌐 Searching the web…",
    "data_analysis": "📊 Analysing your data…",
    "synthesis": "✍️ Writing response…",
}


async def data_analysis_node(state: AgentState, config: RunnableConfig) -> dict:
    """Run the data analysis pipeline and store the structured result in state."""
    db: AsyncSession = config["configurable"]["db"]
    user_id: UUID = config["configurable"]["user_id"]

    result = await run_data_analysis(
        db=db,
        user_id=user_id,
        user_query=state["query"],
        conversation_history=state["messages"],
    )
    return {"data_analysis_result": result}


def _build_graph() -> StateGraph:
    """Compile the RAG agent graph.

    Graph topology:
        router → retrieval     → [websearch] → synthesis → END
               → websearch     → synthesis   → END
               → synthesis     → END                        (llm_only)
               → data_analysis → synthesis   → END
    """
    graph: StateGraph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("websearch", websearch_node)
    graph.add_node("data_analysis", data_analysis_node)
    graph.add_node("synthesis", synthesis_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        lambda state: state["route"],
        {
            "llm_only": "synthesis",
            "retrieval": "retrieval",
            "web_search": "websearch",
            "both": "retrieval",
            "data_analysis": "data_analysis",
        },
    )

    graph.add_conditional_edges(
        "retrieval",
        lambda state: "websearch" if state["route"] == "both" else "synthesis",
        {
            "websearch": "websearch",
            "synthesis": "synthesis",
        },
    )

    graph.add_edge("websearch", "synthesis")
    graph.add_edge("data_analysis", "synthesis")
    graph.add_edge("synthesis", END)

    return graph.compile()


def _initial_state(messages: list[LLMMessage]) -> AgentState:
    """Build a clean initial AgentState from a conversation history."""
    return AgentState(
        query=messages[-1]["content"],
        messages=list(messages),
        has_documents=False,
        route="llm_only",
        retrieved_chunks=[],
        web_results=[],
        answer="",
        sources="llm_only",
        input_tokens=0,
        output_tokens=0,
        data_analysis_result=None,
    )


# Compiled once at import time — stateless graph reused across all requests.
_agent_graph = _build_graph()


async def run_agent(
    db: AsyncSession,
    user_id: UUID,
    messages: list[LLMMessage],
) -> tuple[str, str, int, int, dict | None]:
    """
    Run the RAG agent for a single conversation turn.

    Args:
        db: AsyncSession scoped to the current request.
        user_id: Authenticated user — all retrieval is scoped to this ID.
        messages: Full conversation history including the current user message.

    Returns:
        (answer, sources, input_tokens, output_tokens, data_analysis_result)
        sources is one of: "llm_only" | "retrieval" | "web_search" | "both" | "data_analysis".
        data_analysis_result is the structured query result dict, or None.
    """
    result = await _agent_graph.ainvoke(
        _initial_state(messages),
        config={"configurable": {"db": db, "user_id": user_id}},
    )

    return (
        result["answer"],
        result["sources"],
        result.get("input_tokens", 0),
        result.get("output_tokens", 0),
        result.get("data_analysis_result"),
    )


async def stream_agent_events(
    db: AsyncSession,
    user_id: UUID,
    messages: list[LLMMessage],
) -> AsyncIterator[dict]:
    """
    Stream RAG agent events for Server-Sent Events consumption.

    Yields dicts with the following shapes:
        {"type": "status",  "content": str}   — node transition status message
        {"type": "token",   "content": str}   — individual LLM token from synthesis
        {"type": "final",   "answer": str, "sources": str,
         "input_tokens": int, "output_tokens": int,
         "data_analysis_result": dict | None}  — after graph completes
        {"type": "error",   "content": str, "error_type": str, ...}  — on LLM error

    The caller (streaming endpoint) serialises these to SSE format and
    emits the final "done" event after storing the answer in the database.
    RateLimitError and LLMProviderError are caught here and surfaced as error events
    so the SSE caller never stores a failed message in the DB.
    """
    synthesis_active = False
    accumulated_answer = ""
    final_sources = "llm_only"
    final_input_tokens = 0
    final_output_tokens = 0
    final_data_analysis: dict | None = None

    try:
        async for event in _agent_graph.astream_events(
            _initial_state(messages),
            config={"configurable": {"db": db, "user_id": user_id}},
            version="v2",
        ):
            event_type: str = event.get("event", "")
            event_name: str = event.get("name", "")

            # Node start → send a status message to the client.
            if event_type == "on_chain_start" and event_name in _NODE_STATUS:
                yield {"type": "status", "content": _NODE_STATUS[event_name]}
                if event_name == "synthesis":
                    synthesis_active = True

            # Individual LLM token — only stream from synthesis, not the router.
            elif event_type == "on_chat_model_stream" and synthesis_active:
                chunk = event.get("data", {}).get("chunk")
                if chunk is not None:
                    content = str(chunk.content) if hasattr(chunk, "content") else ""
                    if content:
                        accumulated_answer += content
                        yield {"type": "token", "content": content}

            # Capture data_analysis_result from the data_analysis node output.
            elif event_type == "on_chain_end" and event_name == "data_analysis":
                output = event.get("data", {}).get("output") or {}
                final_data_analysis = output.get("data_analysis_result")

            # Synthesis node finished → capture final sources label and token counts.
            elif event_type == "on_chain_end" and event_name == "synthesis":
                output = event.get("data", {}).get("output") or {}
                final_sources = output.get("sources", "llm_only")
                final_input_tokens = output.get("input_tokens", 0) or 0
                final_output_tokens = output.get("output_tokens", 0) or 0
                # Fallback: if tokens were never emitted, grab the full answer from output.
                if not accumulated_answer:
                    accumulated_answer = output.get("answer", "")
                synthesis_active = False

    except RateLimitError as exc:
        logger.warning("stream_agent_events: rate limit — %s", exc)
        yield {
            "type": "error",
            "content": str(exc),
            "error_type": "rate_limit",
            "provider": exc.provider,
        }
        return

    except LLMProviderError as exc:
        logger.error("stream_agent_events: provider error — %s", exc)
        yield {
            "type": "error",
            "content": str(exc),
            "error_type": "provider_error",
            "provider": exc.provider,
        }
        return

    yield {
        "type": "final",
        "answer": accumulated_answer,
        "sources": final_sources,
        "input_tokens": final_input_tokens,
        "output_tokens": final_output_tokens,
        "data_analysis_result": final_data_analysis,
    }
