"""LangGraph node implementations for the RAG pipeline.

Four nodes: router → retrieval and/or websearch → synthesis.
Dependencies (db session, user_id) are passed via LangGraph RunnableConfig
so they never appear in serialisable state.
"""

import logging
import re
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import AgentState
from app.core.config import settings
from app.core.exceptions import LLMProviderError, RateLimitError
from app.services import retrieval_service
from app.services.cache import delete_cached, get_cached, set_cached
from app.services.embedding_service import get_embedding_provider
from app.services.llm_factory import get_router_llm, get_synthesis_llm

logger = logging.getLogger(__name__)

_VALID_ROUTES = frozenset({"llm_only", "retrieval", "web_search", "both", "data_analysis"})

_ROUTER_PROMPT = """You are a query router for a RAG assistant. Decide which tool(s) to use.

Routing options:
- "llm_only": General knowledge answerable from training data. No recent events, no user documents required.
- "retrieval": The answer likely exists in the user's uploaded documents (user HAS documents available). Use for domain-specific, private, or uploaded content.
- "web_search": Requires current/real-time information — news, prices, live data, recent events, weather, stock prices, anything after training cutoff.
- "both": Needs the user's documents AND real-time web information together.
- "data_analysis": The query is about analysing data, numbers, statistics, trends, averages, totals, counts, charts, SQL queries, database questions, or anything that requires querying structured data files or connected databases.

User has uploaded documents available: {has_docs}
User query: {query}

Respond with exactly one word — one of: llm_only, retrieval, web_search, both, data_analysis"""

_SYNTHESIS_SYSTEM = (
    "You are a knowledgeable assistant. Answer the user's question using the provided context. "
    "If context is provided, use it to give accurate, specific answers and cite sources where helpful. "
    "If no context is provided, answer from your general knowledge. Be concise and direct."
)


def _wrap_llm_exception(exc: Exception, provider_hint: str = "LLM") -> None:
    """Convert a bare exception to RateLimitError or LLMProviderError and re-raise."""
    error_str = str(exc)
    if (
        "429" in error_str
        or "RESOURCE_EXHAUSTED" in error_str
        or "quota" in error_str.lower()
        or "rate limit" in error_str.lower()
    ):
        retry_match = re.search(r"retry.*?(\d+)", error_str, re.IGNORECASE)
        retry_after = int(retry_match.group(1)) if retry_match else None
        raise RateLimitError("Gemini", retry_after) from exc
    raise LLMProviderError(provider_hint, error_str[:200]) from exc


async def router_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Determine routing for the current query.

    Checks if the user has ready documents, then makes a lightweight LLM call
    to classify the query into one of five routing options.
    """
    db: AsyncSession = config["configurable"]["db"]
    user_id: UUID = config["configurable"]["user_id"]

    cache_k = f"doc_count:{user_id}"
    cached = await get_cached(cache_k)
    if cached is not None:
        has_docs = cached["count"] > 0
    else:
        count = await retrieval_service.count_ready_documents(db, user_id)
        await set_cached(cache_k, {"count": count}, ttl=60)
        has_docs = count > 0

    llm = get_router_llm()
    prompt = _ROUTER_PROMPT.format(has_docs=has_docs, query=state["query"])
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
    except (RateLimitError, LLMProviderError):
        raise
    except Exception as exc:
        _wrap_llm_exception(exc)

    route = str(response.content).strip().lower()
    if route not in _VALID_ROUTES:
        route = "retrieval" if has_docs else "llm_only"

    logger.info(
        "agent.router: route=%s has_docs=%s query=%r", route, has_docs, state["query"][:80]
    )
    return {"has_documents": has_docs, "route": route}


async def retrieval_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Embed the query and run pgvector cosine-similarity search over the user's chunks.

    Scoped exclusively to the current user's document_chunks — never cross-user.
    """
    db: AsyncSession = config["configurable"]["db"]
    user_id: UUID = config["configurable"]["user_id"]

    embedding_provider = get_embedding_provider()
    query_embedding = await embedding_provider.embed_query(state["query"])

    chunks = await retrieval_service.similarity_search(db, user_id, query_embedding, top_k=5)
    logger.info("agent.retrieval: found %d chunks for user %s", len(chunks), user_id)

    return {"retrieved_chunks": chunks}


async def websearch_node(state: AgentState, config: RunnableConfig) -> dict:
    """Call the Tavily API to retrieve real-time web results for the query."""
    try:
        from tavily import AsyncTavilyClient  # local import — optional dependency

        client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
        response = await client.search(query=state["query"], max_results=5)
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
            }
            for r in response.get("results", [])
        ]
    except Exception:
        logger.exception("agent.websearch: Tavily search failed")
        results = []

    logger.info("agent.websearch: returned %d results", len(results))
    return {"web_results": results}


async def synthesis_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Combine retrieved context with conversation history and generate a final answer.

    Builds a context block from document chunks, web results, and/or data analysis
    results, prepends it as a system message, then calls the LLM with the full
    chat history.

    For LangChain-native LLMs (Gemini): uses astream so individual tokens are
    captured by stream_agent_events via on_chat_model_stream events.
    For CloudflareLLM: uses ainvoke (no per-token streaming — the full answer is
    captured from the on_chain_end event in stream_agent_events).
    """

    # Build context block from whichever tools ran
    context_parts: list[str] = []

    data_result = state.get("data_analysis_result")

    if data_result and "error" not in data_result:
        columns = data_result.get("columns", [])
        rows = data_result.get("rows", [])
        row_count = data_result.get("row_count", 0)
        total_row_count = data_result.get("total_row_count", row_count)

        display_rows = rows[:50]
        header = " | ".join(str(c) for c in columns)
        table_lines = "\n".join(
            " | ".join(str(cell) for cell in row) for row in display_rows
        )

        if total_row_count > row_count:
            row_note = f"{row_count} rows shown of {total_row_count} total — truncated to 500"
        elif len(display_rows) < row_count:
            row_note = f"showing first {len(display_rows)} of {row_count} rows"
        else:
            row_note = f"{row_count} rows"

        context_parts.append(
            f"## Data analysis result:\n"
            f"SQL executed: {data_result['sql']}\n"
            f"Query result ({row_note}):\n"
            f"{header}\n"
            f"{table_lines}\n\n"
            f"You are a data analyst. The user has already seen the full data table. "
            f"DO NOT list or repeat any rows, values, or numbers from the table. "
            f"Instead write exactly 2 sentences maximum: "
            f"Sentence 1: The single most important finding (highest, lowest, biggest gap, "
            f"dominant category, etc.) with one specific number as evidence. "
            f"Sentence 2: A pattern, trend, or business implication from the data. "
            f"Be specific. Be concise. No bullet points. No preamble like 'According to...' "
            f"or 'The query result shows...'. Start directly with the insight."
        )
    elif data_result and data_result.get("error") == "no_sources":
        context_parts.append(
            "## Data sources:\n"
            "The user has no data files or connections yet. "
            "Suggest they upload a file or add a connection in the Data Sources page."
        )

    if state["retrieved_chunks"]:
        doc_lines = "\n\n".join(
            f"[Source: {chunk['filename']}]\n{chunk['text']}"
            for chunk in state["retrieved_chunks"]
        )
        context_parts.append(f"## From uploaded documents:\n{doc_lines}")

    if state["web_results"]:
        web_lines = "\n\n".join(
            f"[{r['title']}] {r['url']}\n{r['content']}"
            for r in state["web_results"]
            if r["content"]
        )
        if web_lines:
            context_parts.append(f"## From web search:\n{web_lines}")

    lc_messages: list[Any] = [SystemMessage(content=_SYNTHESIS_SYSTEM)]

    if context_parts:
        context_block = "\n\n---\n\n".join(context_parts)
        lc_messages.append(
            SystemMessage(content=f"Use the following context to answer:\n\n{context_block}")
        )

    for msg in state["messages"]:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        else:
            lc_messages.append(AIMessage(content=msg["content"]))

    llm = get_synthesis_llm()
    answer_parts: list[str] = []
    input_tokens = 0
    output_tokens = 0

    from app.services.cloudflare_llm import CloudflareLLM

    if isinstance(llm, CloudflareLLM):
        # Cloudflare doesn't support per-token streaming via LangGraph events.
        # The full answer is captured from the on_chain_end event in stream_agent_events.
        try:
            response = await llm.ainvoke(lc_messages)
        except (RateLimitError, LLMProviderError):
            raise
        except Exception as exc:
            _wrap_llm_exception(exc, "Cloudflare Workers AI")
        answer_parts.append(str(response.content))
    else:
        # LangChain-native models (Gemini): stream tokens so SSE sees on_chat_model_stream.
        try:
            async for chunk in llm.astream(lc_messages, config=config):
                if chunk.content:
                    answer_parts.append(str(chunk.content))
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    input_tokens = chunk.usage_metadata.get("input_tokens", 0) or 0
                    output_tokens = chunk.usage_metadata.get("output_tokens", 0) or 0
        except (RateLimitError, LLMProviderError):
            raise
        except Exception as exc:
            _wrap_llm_exception(exc)

    answer = "".join(answer_parts)

    # Determine final sources label
    has_docs = bool(state["retrieved_chunks"])
    has_web = bool(state["web_results"])
    has_data = bool(data_result and "error" not in data_result)
    if has_data:
        sources = "data_analysis"
    elif has_docs and has_web:
        sources = "both"
    elif has_docs:
        sources = "retrieval"
    elif has_web:
        sources = "web_search"
    else:
        sources = "llm_only"

    logger.info(
        "agent.synthesis: sources=%s answer_len=%d tokens=(%d in / %d out)",
        sources, len(answer), input_tokens, output_tokens,
    )
    return {
        "answer": answer,
        "sources": sources,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
