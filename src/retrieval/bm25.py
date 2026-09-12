"""
Standard Okapi BM25 scoring (docs/PHASE_05_BM25_BASELINE.md Section G).

score(D, Q) = sum over query terms t of:
    idf(t) * (tf(t, D) * (k1 + 1)) / (tf(t, D) + k1 * (1 - b + b * |D| / avgdl))

idf(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))

The "+1 inside the log" IDF variant (rather than the classic
Robertson-Sparck-Jones ln((N-df+0.5)/(df+0.5))) is a deliberate,
documented choice: it guarantees idf(t) > 0 for every term at every
document frequency, so no query term can ever *subtract* from a score or
require a separate negative-IDF epsilon branch. This keeps scoring
strictly non-negative and simpler to test deterministically, at the cost
of slightly compressing the discriminating power of extremely common
terms - a documented, revisitable trade-off, not a claim of optimality
[ENGINEERING RECOMMENDATION].

Pure functions only - no I/O, no index-building here (see index.py).
"""

from __future__ import annotations

import math


def idf(total_document_count: int, document_frequency: int) -> float:
    if document_frequency <= 0:
        return 0.0
    return math.log(1 + (total_document_count - document_frequency + 0.5) / (document_frequency + 0.5))


def score_chunk(
    query_terms: list,
    term_frequencies: dict,
    document_length: int,
    average_document_length: float,
    term_document_frequency: dict,
    total_document_count: int,
    k1: float,
    b: float,
) -> float:
    """BM25 score of one chunk against a tokenized query. Returns 0.0 when no query term matches."""
    score = 0.0
    for term in query_terms:
        tf = term_frequencies.get(term, 0)
        if tf == 0:
            continue
        df = term_document_frequency.get(term, 0)
        if df == 0:
            continue
        term_idf = idf(total_document_count, df)
        length_norm = (
            document_length / average_document_length if average_document_length > 0 else 0.0
        )
        denominator = tf + k1 * (1 - b + b * length_norm)
        score += term_idf * (tf * (k1 + 1)) / denominator
    return score
