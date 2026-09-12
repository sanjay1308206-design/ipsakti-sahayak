"""
Generic retrieval evaluation metrics, shared by Phase 5 (BM25,
docs/PHASE_05_BM25_BASELINE.md Section P) and Phase 6 (dense/FAISS,
docs/PHASE_06_MULTILINGUAL_DENSE_RETRIEVAL.md Section Q). Pure functions
only - no dataset, no benchmark harness, no regulatory content here. The
synthetic benchmarks themselves (queries + known relevant chunk_ids) live
in tests/test_phase_0{5,6}_evaluation.py, since they are test/measurement
fixtures for these baselines, not a production evaluation harness -
Phase 16 ("Evaluation & Red-Team Benchmark") owns the full evaluation
harness across all retrieval/classification/safety dimensions.

These metrics are standard information-retrieval definitions, not
project-specific inventions - [OFFICIAL SOURCE: standard IR literature,
"external research" as commonly defined, e.g. Manning/Raghavan/Schutze
"Introduction to Information Retrieval"].
"""

from __future__ import annotations


def precision_at_k(retrieved_chunk_ids: list, relevant_chunk_ids: set, k: int) -> float:
    """Fraction of the top-k retrieved chunk_ids that are relevant. 0.0 when k<=0 or nothing retrieved."""
    if k <= 0:
        return 0.0
    top_k = retrieved_chunk_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for cid in top_k if cid in relevant_chunk_ids)
    return hits / len(top_k)


def recall_at_k(retrieved_chunk_ids: list, relevant_chunk_ids: set, k: int) -> float:
    """Fraction of all known-relevant chunk_ids found within the top-k retrieved. 0.0 when there are none relevant."""
    if not relevant_chunk_ids:
        return 0.0
    top_k = retrieved_chunk_ids[:k] if k > 0 else []
    hits = sum(1 for cid in top_k if cid in relevant_chunk_ids)
    return hits / len(relevant_chunk_ids)


def reciprocal_rank(retrieved_chunk_ids: list, relevant_chunk_ids: set) -> float:
    """1/(rank of the first relevant chunk_id, 1-based), or 0.0 if none of the retrieved chunk_ids are relevant."""
    for position, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in relevant_chunk_ids:
            return 1.0 / position
    return 0.0


def mean_reciprocal_rank(query_results: list) -> float:
    """
    Mean Reciprocal Rank over several queries. `query_results` is a list of
    (retrieved_chunk_ids, relevant_chunk_ids) pairs. 0.0 for an empty list
    of queries (nothing to average).
    """
    if not query_results:
        return 0.0
    scores = [reciprocal_rank(retrieved, relevant) for retrieved, relevant in query_results]
    return sum(scores) / len(scores)
