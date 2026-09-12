"""
Structural boundary and deterministic splitting rules
(docs/PHASE_04_LEGAL_AWARE_CHUNKING.md Sections E, H, I, J, K).

Pure functions only - no I/O, no provenance assembly (that lives in
chunker.py). Operates directly on ingestion.models.Block/Page objects,
never re-deriving or guessing structure Phase 3 did not already detect.
"""

from __future__ import annotations

SECTION_SEPARATOR = "\n\n"  # fixed join separator between distinct blocks' text in one chunk


def flatten_blocks(pages: list) -> list:
    """
    Flatten every block across every page into one reading-order list.

    Safe because ingestion.extractors assigns `sequence` as a single
    monotonically increasing counter across the whole document (including
    across PDF page boundaries) - see docs/PHASE_03_LEGAL_STRUCTURE_EXTRACTION.md
    Section 8. This function trusts, but also verifies, that invariant.
    """
    blocks = [block for page in pages for block in page.blocks]
    sequences = [b.sequence for b in blocks]
    if sequences != sorted(sequences):
        raise ValueError(
            "Phase 3 output blocks are not in monotonically increasing sequence order; "
            "Phase 4 relies on this Phase 3 invariant and will not guess an ordering"
        )
    return blocks


def iter_section_groups(blocks: list):
    """
    Partition an ordered block list into (heading_block_or_None, [blocks]) groups.

    A new group starts at every HEADING block. Blocks appearing before the
    first heading (if any) form a leading group with heading=None - Phase 4
    never invents a heading to cover a document/section with no detected
    heading (docs/PHASE_04_LEGAL_AWARE_CHUNKING.md Section F/I).
    """
    current_heading = None
    current_group: list = []
    for block in blocks:
        if block.block_type == "HEADING":
            if current_group:
                yield (current_heading, current_group)
            current_heading = block
            current_group = [block]
        else:
            current_group.append(block)
    if current_group:
        yield (current_heading, current_group)


def split_text_preserving_all_characters(text: str, max_size: int) -> list:
    """
    Split `text` into pieces of at most `max_size` Unicode code points each,
    preferring to break at a whitespace boundary but always guaranteeing
    forward progress (a pathological run with no whitespace falls back to a
    hard slice at exactly max_size).

    Invariant (tested directly, docs Section 21): "".join(pieces) == text,
    always, exactly - these are contiguous, non-overlapping slices of the
    original string. No normalization, trimming, or rewriting occurs here.
    """
    if max_size <= 0:
        raise ValueError(f"max_size must be a positive integer, got {max_size}")
    if len(text) <= max_size:
        return [text] if text else []

    pieces = []
    remaining = text
    while len(remaining) > max_size:
        window = remaining[:max_size]
        split_at = max_size
        for i in range(max_size - 1, 0, -1):
            if window[i].isspace():
                split_at = i + 1  # keep the whitespace char with the earlier piece
                break
        pieces.append(remaining[:split_at])
        remaining = remaining[split_at:]
    if remaining:
        pieces.append(remaining)
    return pieces


def render_table_row(row: list) -> str:
    return " | ".join(row)


def render_table_rows(rows: list) -> str:
    return "\n".join(render_table_row(row) for row in rows)


def split_table_rows(rows: list, max_size: int) -> list:
    """
    Group whole table rows into row-groups whose flattened rendering is at
    most `max_size` code points, without ever splitting inside a single row
    (docs/PHASE_04_LEGAL_AWARE_CHUNKING.md Section I: "split deterministically
    only if the representation permits it without losing row/column meaning").

    If a single row's own rendering exceeds max_size, that row becomes its
    own group unsplit (a documented size exception - row/column meaning
    cannot be preserved by splitting inside a row, so it is not attempted).
    Returns a non-empty list of row-groups (each a list[list[str]]); an
    empty `rows` input returns a single empty group so callers always get
    at least one piece.
    """
    if max_size <= 0:
        raise ValueError(f"max_size must be a positive integer, got {max_size}")
    if not rows:
        return [[]]

    groups = []
    current: list = []
    current_size = 0
    for row in rows:
        rendered_len = len(render_table_row(row))
        added_len = rendered_len + (1 if current else 0)  # +1 for the newline joiner
        if current and current_size + added_len > max_size:
            groups.append(current)
            current = []
            current_size = 0
            added_len = rendered_len
        current.append(row)
        current_size += added_len
    if current:
        groups.append(current)
    return groups
