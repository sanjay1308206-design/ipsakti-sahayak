"""
Phase 14 - Multilingual Delivery (docs/PHASE_14_MULTILINGUAL_DELIVERY.md).

Wraps BOTH ends of the pipeline: input-side script detection and
meaning-preserving Unicode canonicalization (preservation.py), and
output-side translated delivery of an already-produced GroundedResponse
(Phase 10) + SafetyDecision (Phase 13) (delivery.py). Never re-implements
classification, jurisdiction routing, citation validation, generation, or
safety policy - it only reads those trusted objects and wraps them.

CORE INVARIANT: translation must never alter the identity of the
underlying evidence or citation, and must never override a Phase 12
jurisdiction decision, a Phase 13 safety decision, or a Phase 10
grounding status. Language is never jurisdiction. Script is never
language. No LLM, no network, no credentials assumed anywhere in this
package - a Bhashini/live-translation adapter is explicitly deferred.
"""
