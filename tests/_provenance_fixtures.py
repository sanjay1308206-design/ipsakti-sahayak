"""
Phase 3 test-support module: shared synthetic provenance-record builder for
tests/test_phase_03_*.py.

SYNTHETIC TEST FIXTURE GENERATOR ONLY - every record built here sets
synthetic=True and uses an obviously-fake document_id. Not a test module
itself (no test_ prefix) - pytest will not collect it.
"""

from __future__ import annotations


def make_provenance(content_hash: str, **overrides) -> dict:
    record = {
        "document_id": "SYNTHETIC-DOC-0001",
        "source_family_id": "SF-01",
        "jurisdiction": "INDIA",
        "content_hash": content_hash,
        "admission_status": "ADMIT",
        "synthetic": True,
    }
    record.update(overrides)
    return record
