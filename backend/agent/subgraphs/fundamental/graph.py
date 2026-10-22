from langgraph.graph import StateGraph, START, END
from agent import schemas

from .nodes import (
    search_documents,
    search_web,
    unify_documents,
    relevance_check,
    query_rewrite,
    make_fundamental_summary,
    route_relevance,
)

def build_fundamental_graph():
    builder = StateGraph(schemas.FundamentalState)

    builder.add_node("search_documents", search_documents)
    builder.add_node("unify_documents", unify_documents)
    builder.add_node("search_web", search_web)
    builder.add_node("relevance_check", relevance_check)
    builder.add_node("query_rewrite", query_rewrite)
    builder.add_node("fundamental_summary", make_fundamental_summary)

    builder.add_edge(START, "search_documents")
    builder.add_edge(START, "search_web")

    builder.add_edge(["search_documents", "search_web"], "unify_documents")

    builder.add_edge(["unify_documents"], "relevance_check")

    builder.add_conditional_edges(
        "relevance_check",
        route_relevance,
        {"relevance": "fundamental_summary", "no_relevance": "query_rewrite"},
    )

    builder.add_edge("query_rewrite", "search_web")
    builder.add_edge("query_rewrite", "search_documents")


    builder.add_edge("fundamental_summary", END)

    return builder.compile()