"""
Phase 12 - Jurisdiction Firewall (docs/PHASE_12_JURISDICTION_FIREWALL.md).

Determines, deterministically and explainably, which evidence-jurisdiction
values a request is permitted to draw from, and provides a
machine-checkable filter that structurally prevents incompatible-
jurisdiction Evidence from ever being treated as allowed. Sits between
Phase 11 (formulation classification) and Phase 5-7 (retrieval) in the
intended pipeline - never re-implements either. No LLM, no IP/physical-
location-based inference, no network, no legal determination anywhere in
this package.
"""
