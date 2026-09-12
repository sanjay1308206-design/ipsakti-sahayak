"""
Phase 11 - Formulation Classification Engine
(docs/PHASE_11_FORMULATION_CLASSIFICATION.md).

Reads raw/structured caller input and assigns Phase 1's ALREADY-FIXED
taxonomy values (config/domain_taxonomy.yaml), then evaluates Phase 1's
ALREADY-FIXED decision tree (config/regulatory_decision_tree.yaml) over
them to reach one of the four closed terminal states (KNOWN/UNKNOWN/
AMBIGUOUS/NEEDS_EVIDENCE). Deterministic, explainable, no LLM, no network,
no external retrieval anywhere in this package. Does not decide
jurisdiction firewall routing (Phase 12), does not score confidence
(Phase 13), and issues no legal conclusion.
"""
