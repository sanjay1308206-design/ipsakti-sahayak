"""
Lexical tokenization/normalization baseline for BM25
(docs/PHASE_05_BM25_BASELINE.md Sections C/D/F).

A deliberately simple, deterministic, stdlib-only, script-agnostic
tokenizer - not a linguistically optimal tokenizer for any particular
language. Establishes a reproducible baseline; language-specific
morphology (stemming, compound splitting, script-specific segmentation)
is explicitly [DEFERRED] to a later, benchmark-justified phase.
"""

from __future__ import annotations

import unicodedata

TOKENIZER_POLICY_VERSION = "v1"

# [ENGINEERING RECOMMENDATION] A "word" character is any Unicode Letter
# (category L*), Number (N*), or combining Mark (M*), plus underscore.
# Category M* is essential, not optional: Devanagari/Tamil (and most other
# Brahmic-script) words are written as base letters (category Lo) combined
# with dependent vowel signs and the virama/halant (category Mn) - e.g.
# "aayurveda" in Devanagari alternates Lo/Mn/Lo/Mn/... character by
# character. Python's stdlib `re` module's `\w` deliberately excludes
# category M (it only covers str.isalnum(), which is L*/N* only), so a
# naive `\w+` regex silently fragments every Devanagari/Tamil word at each
# combining mark - a real, tested defect this tokenizer avoids by
# classifying per-character Unicode category directly instead of using
# `\w`. This is the one substantive difference from a "regex tokenizer"
# and is documented here precisely because it is easy to get subtly wrong.
_WORD_CATEGORY_PREFIXES = ("L", "N", "M")


def tokenize(text: str) -> list:
    """
    Deterministic tokenization: NFKC Unicode normalization -> lowercasing
    (a no-op for scripts without case, e.g. Devanagari/Tamil) -> a
    per-character Unicode-category scan that groups consecutive
    Letter/Number/Mark characters (plus "_") into one token, treating
    everything else (whitespace, punctuation, symbols) as a separator.

    Never mutates or returns the original `text`. Hyphens and punctuation
    are separators, not tokens (e.g. "well-known" -> ["well", "known"]) -
    a documented, deliberate simplification (docs/PHASE_05_BM25_BASELINE.md
    Section Q), not a claim of correct compound-word handling.
    """
    if not isinstance(text, str):
        raise TypeError(f"tokenize expects str, got {type(text).__name__}")

    normalized = unicodedata.normalize("NFKC", text).lower()

    tokens = []
    current = []
    for ch in normalized:
        if ch == "_" or unicodedata.category(ch)[0] in _WORD_CATEGORY_PREFIXES:
            current.append(ch)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens
