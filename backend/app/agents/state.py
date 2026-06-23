"""LangGraph agent state definition for the RAG pipeline."""

from typing import TypedDict


class AgentState(TypedDict):
    """State threaded through every node of the RAG agent graph."""

    query: str                    # Latest user message (last entry in messages)
    messages: list[dict]          # Full conversation history as list[LLMMessage]
    has_documents: bool           # Whether the user has at least one ready document
    route: str                    # Routing decision: llm_only | retrieval | web_search | both
    retrieved_chunks: list[dict]  # [{text, filename, distance}] from pgvector
    web_results: list[dict]       # [{title, url, content}] from Tavily
    answer: str                   # Final synthesized answer
    sources: str                  # Which tools were used: llm_only | retrieval | web_search | both
    input_tokens: int             # Prompt token count from the synthesis LLM call
    output_tokens: int            # Completion token count from the synthesis LLM call
