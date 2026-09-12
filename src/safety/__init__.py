"""
Phase 13 - Confidence + Safety + Abstention
(docs/PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md).

The project-wide safety/trust decision boundary: consumes Phase 11's
ClassificationResult, Phase 12's JurisdictionDecision, and Phase 10's
GroundedResponse (which itself already carries Phase 8/9's evidence and
citation-integrity signals forward) and returns a deterministic
SAFE_TO_PRESENT / ABSTAIN / ESCALATE decision. Never re-implements
classification, jurisdiction routing, citation validation, retrieval, or
generation. Never performs semantic entailment or issues legal advice.
No LLM, no network, no randomness anywhere in this package.
"""
