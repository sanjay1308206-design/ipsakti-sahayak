"""
BM25 index build/query orchestration (docs/PHASE_05_BM25_BASELINE.md
Sections H, I, J, K, L, M).

build_index(): the only way to construct a Bm25Index. Consumes a list of
real chunking.models.Chunk objects (the actual in-memory Phase 4 output),
never a serialized JSON dict, never raw text.

query(): the only way to retrieve. Never mutates the index; running it
repeatedly against the same index and query text is guaranteed to produce
identical RetrievalResponse objects (docs Section N).

Never downloads anything. Never embeds. Never reranks. Never generates.
"""

from __future__ import annotations

from collections import Counter

from chunking.models import Chunk

from .bm25 import score_chunk
from .identity import compute_index_signature
from .models import Bm25Config, Bm25Index, RetrievalResponse, RetrievalResult
from .tokenizer import tokenize


def _validate_chunks(chunks: list) -> None:
    if not isinstance(chunks, list):
        raise TypeError(f"build_index expects a list of Chunk objects, got {type(chunks).__name__}")
    for chunk in chunks:
        if not isinstance(chunk, Chunk):
            raise TypeError(f"build_index expects chunking.models.Chunk objects, got {type(chunk).__name__}")


def build_index(chunks: list, config: Bm25Config = None) -> Bm25Index:
    _validate_chunks(chunks)
    if config is None:
        config = Bm25Config()

    chunk_ids = [c.chunk_id for c in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("build_index requires unique chunk_id values - found a duplicate")

    document_lengths = []
    term_frequencies = []
    chunk_provenance = []
    document_frequency: dict = {}

    for chunk in chunks:
        tokens = tokenize(chunk.text)
        tf = dict(Counter(tokens))
        term_frequencies.append(tf)
        document_lengths.append(len(tokens))
        for term in tf:
            document_frequency[term] = document_frequency.get(term, 0) + 1
        chunk_provenance.append(
            {
                "document_id": chunk.document_id,
                "source_family_id": chunk.source_family_id,
                "jurisdiction": chunk.jurisdiction,
                "content_hash": chunk.content_hash,
                "synthetic": chunk.synthetic,
                "page_numbers": list(chunk.page_numbers),
                "block_ids": list(chunk.block_ids),
                "text": chunk.text,
            }
        )

    chunk_count = len(chunks)
    average_document_length = (sum(document_lengths) / chunk_count) if chunk_count else 0.0
    signature = compute_index_signature(config.signature, chunk_ids, [c.content_hash for c in chunks])

    return Bm25Index(
        config=config,
        chunk_count=chunk_count,
        average_document_length=average_document_length,
        chunk_ids=chunk_ids,
        document_lengths=document_lengths,
        term_document_frequency=document_frequency,
        term_frequencies=term_frequencies,
        chunk_provenance=chunk_provenance,
        signature=signature,
    )


def query(index: Bm25Index, query_text: str, top_k: int) -> RetrievalResponse:
    if not isinstance(index, Bm25Index):
        raise TypeError(f"query expects a retrieval.models.Bm25Index, got {type(index).__name__}")
    if not isinstance(query_text, str):
        raise TypeError(f"query expects query_text to be str, got {type(query_text).__name__}")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError(f"top_k must be a positive integer, got {top_k!r}")

    query_terms = tokenize(query_text)

    if index.chunk_count == 0 or not query_terms:
        return RetrievalResponse(
            query=query_text,
            normalized_query_tokens=query_terms,
            top_k=top_k,
            index_signature=index.signature,
            results=[],
        )

    scored = []
    for internal_id in range(index.chunk_count):
        score = score_chunk(
            query_terms=query_terms,
            term_frequencies=index.term_frequencies[internal_id],
            document_length=index.document_lengths[internal_id],
            average_document_length=index.average_document_length,
            term_document_frequency=index.term_document_frequency,
            total_document_count=index.chunk_count,
            k1=index.config.k1,
            b=index.config.b,
        )
        if score > 0.0:
            scored.append((score, index.chunk_ids[internal_id], internal_id))

    # Deterministic tie-break (docs/PHASE_05_BM25_BASELINE.md Section J):
    # descending score, then ascending chunk_id - never insertion order,
    # never a random/unstable comparison.
    scored.sort(key=lambda item: (-item[0], item[1]))
    top = scored[: top_k]

    results = []
    for rank, (score, chunk_id, internal_id) in enumerate(top, start=1):
        prov = index.chunk_provenance[internal_id]
        results.append(
            RetrievalResult(
                rank=rank,
                chunk_id=chunk_id,
                score=score,
                document_id=prov["document_id"],
                source_family_id=prov["source_family_id"],
                jurisdiction=prov["jurisdiction"],
                content_hash=prov["content_hash"],
                synthetic=prov["synthetic"],
                page_numbers=prov["page_numbers"],
                block_ids=prov["block_ids"],
                chunk_text=prov["text"],
            )
        )

    return RetrievalResponse(
        query=query_text,
        normalized_query_tokens=query_terms,
        top_k=top_k,
        index_signature=index.signature,
        results=results,
    )
