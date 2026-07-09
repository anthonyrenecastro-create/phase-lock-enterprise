"""LangChain/LlamaIndex integration example for Phase-Lock gateway.

This script demonstrates where drift stabilization is inserted in a RAG flow:
1) build retrieval context
2) compute/update metrics and embedding
3) call /v1/stabilize
4) choose policy action (pass/clamp/retry/fallback-model/human-review)
"""

from __future__ import annotations

from typing import Any

from phase_lock_sdk import PhaseLockClient


def build_metric_window(raw_scores: list[float]) -> list[float]:
    if len(raw_scores) >= 24:
        return raw_scores[-24:]
    padded = list(raw_scores)
    while len(padded) < 24:
        padded.append(raw_scores[-1] if raw_scores else 0.0)
    return padded


def stabilize_query(
    client: PhaseLockClient,
    tenant_id: str,
    request_id: str,
    text: str,
    embedding: list[float],
    retrieval_scores: list[float],
) -> dict[str, Any]:
    metric_window = build_metric_window(retrieval_scores)
    return client.stabilize(
        tenant_id=tenant_id,
        request_id=request_id,
        text=text,
        embedding=embedding,
        metric_window=metric_window,
        metadata={"source": "rag-pipeline", "step_cap": 96},
    )


def policy_route(actions: list[str]) -> str:
    if "human-review" in actions:
        return "route:human-review"
    if "fallback-model" in actions:
        return "route:fallback-model"
    if "retry" in actions:
        return "route:retry"
    if "clamp" in actions:
        return "route:clamp"
    return "route:pass"


def langchain_style_example() -> None:
    """Pseudo-flow for LangChain Runnable graph integration."""
    client = PhaseLockClient(base_url="http://127.0.0.1:8000", api_key="replace-me")
    query = "Summarize current churn anomalies"
    embedding = [0.03, -0.02, 0.06, 0.01]
    retriever_scores = [0.62, 0.58, 0.55, 0.61, 0.47, 0.53, 0.65, 0.6]

    out = stabilize_query(
        client=client,
        tenant_id="acme",
        request_id="langchain-001",
        text=query,
        embedding=embedding,
        retrieval_scores=retriever_scores,
    )

    decision = policy_route(out["actions"])
    print("langchain decision:", decision, "drift:", out["drift_score"])


def llamaindex_style_example() -> None:
    """Pseudo-flow for LlamaIndex QueryEngine post-retrieval hook."""
    client = PhaseLockClient(base_url="http://127.0.0.1:8000", api_key="replace-me")
    query = "What changed in payment-failure root causes this week?"
    embedding = [0.01, 0.02, -0.05, 0.04]
    retriever_scores = [0.42, 0.4, 0.38, 0.36, 0.49, 0.44, 0.41, 0.37]

    out = stabilize_query(
        client=client,
        tenant_id="acme",
        request_id="llamaindex-001",
        text=query,
        embedding=embedding,
        retrieval_scores=retriever_scores,
    )

    decision = policy_route(out["actions"])
    print("llamaindex decision:", decision, "risk:", out["risk_level"])


if __name__ == "__main__":
    # These examples are intentionally framework-light to keep repo dependencies minimal.
    # Integrate at the post-retrieval / pre-generation middleware step.
    langchain_style_example()
    llamaindex_style_example()
