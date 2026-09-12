# PHASE 12 — JURISDICTION FIREWALL

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 12 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_01_DOMAIN_TAXONOMY.md`, `docs\PHASE_02_AUTHORITY_MATRIX.md`, `docs\PHASE_11_FORMULATION_CLASSIFICATION.md`
Machine-readable counterpart: `config\jurisdiction_firewall_contract.yaml`
Implementation: `src\jurisdiction\models.py`, `policy.py`, `firewall.py`, `filtering.py`, `serialize.py`

**India evidence must not silently mix with international evidence.** Phase 2 already made jurisdiction a mandatory, explicit, per-document field so that "no future phase can build a merged index without actively discarding this metadata" (`docs\PHASE_02_AUTHORITY_MATRIX.md` Section 7). Phase 12 is that future phase's enforcement boundary — it does not invent a new jurisdiction concept; it deterministically decides, from already-established signals, which evidence-jurisdiction values a request may draw from, and provides a filter that structurally cannot be bypassed.

---

## A. Phase Objective

`[OFFICIAL SOURCE]` The Master Reference's Jurisdiction Firewall lock states plainly: *"India and international corpora should be separated at retrieval time, not merely mentioned in the prompt"* (`docs\MASTER_REFERENCE_LOCK.md` Section E). Phase 2 built the corpus-side half of this contract (jurisdiction as mandatory per-document metadata); Phase 12 builds the retrieval-time enforcement half — a deterministic `JurisdictionDecision` and a machine-checkable evidence filter that makes leakage structurally impossible, not merely discouraged.

## B. Scope

In scope: `JurisdictionDecision`/`EvidenceFilterResult`/`JurisdictionFirewallConfig` models; deterministic normalization of a request-side jurisdiction signal; a fixed, documented mapping from that signal onto a permitted subset of the evidence-side jurisdiction vocabulary; conflict/ambiguity handling between multiple signals; a fail-closed evidence-compatibility check and batch filter; deterministic serialization.

Out of scope (no code for any of these exists anywhere in `src\jurisdiction\`): formulation classification, any retrieval ranking algorithm (BM25/dense/RRF/reranking), evidence construction, citation validation, answer generation, a project-wide confidence engine, human escalation, translation, an API, a frontend, deployment, monitoring, or any legal/currentness determination.

## C. Non-Scope

`[ENGINEERING RECOMMENDATION]` Explicitly, Phase 12 does not: determine governing law, legal compliance, legal validity, patentability, infringement, regulatory approval, whether a product is legally permitted, or whether a particular authority has final legal competence. It also never determines whether a jurisdiction's law is *current* (Section V) — that is a separate source/versioning problem, deferred. Phase 12 answers exactly one question: *given this request, which evidence-jurisdiction values may be searched?*

## D. Existing Contracts Reused

`[OFFICIAL SOURCE]` Three files, reused verbatim, never redesigned or superseded:

1. `config\domain_taxonomy.yaml` `jurisdiction_inputs` (Phase 1) — the **request-side** vocabulary: `INDIA`, `INTERNATIONAL`, `BOTH`, `UNSPECIFIED`.
2. `config\authority_matrix.yaml` `valid_jurisdictions` (Phase 2) — the **evidence-side** vocabulary: `INDIA`, `INTERNATIONAL`, `NOT_APPLICABLE`, `OTHER_UNSPECIFIED`.
3. `config\classification_contract.yaml` / `classification.models.ClassificationResult.jurisdiction_input` (Phase 11) — the primary request-side signal Phase 12 consumes directly, never reconstructed from raw text.

## E. Jurisdiction Vocabulary

`[OFFICIAL SOURCE]` **This project already has two separate, non-interchangeable jurisdiction vocabularies — Phase 12 introduces no third.** `jurisdiction.models.REQUEST_JURISDICTION_VALUES` mirrors (1) above exactly; `jurisdiction.models.EVIDENCE_JURISDICTION_VALUES` mirrors (2) exactly (both cross-checked against their source YAML by `tests\test_phase_12_regression.py` for drift). `BOTH` is a legitimate *request-side* resolved value (Phase 1: "the question legitimately spans both") — no single Evidence object is ever tagged `BOTH`; `NOT_APPLICABLE` is Bhashini's (a non-evidence service adapter's) jurisdiction scope and should never appear on a real Evidence object either. Collapsing these two vocabularies together, or using one where the other belongs, would silently break the firewall — this is why they are named and validated completely separately throughout `src\jurisdiction\`.

## F. Jurisdiction States

`[OFFICIAL SOURCE]` Reused wholesale from Phase 1's closed vocabulary (`docs\PHASE_01_DOMAIN_TAXONOMY.md` Section H) — no parallel state system: `KNOWN`, `UNKNOWN`, `AMBIGUOUS`, `NEEDS_EVIDENCE`. Mapping, with every reason code independently reachable and tested:

| Scenario | State | Reason code |
|---|---|---|
| A single, well-formed signal normalizes successfully (India, international, or both agree) | `KNOWN` | `EXPLICIT_JURISDICTION_ACCEPTED` |
| No signal supplied, or `UNSPECIFIED` supplied | `UNKNOWN` | `JURISDICTION_UNKNOWN` |
| A signal is supplied but is not a member of the supported vocabulary (e.g. a specific country name) | `UNKNOWN` | `JURISDICTION_NOT_SUPPORTED` |
| A signal is the wrong type, or a caller-supplied evidence jurisdiction is empty/unrecognized | `UNKNOWN` | `JURISDICTION_METADATA_INVALID` |
| Two signals (explicit override + classification result) disagree after normalization | `AMBIGUOUS` | `JURISDICTION_AMBIGUOUS` |

`[ENGINEERING RECOMMENDATION]` **`NEEDS_EVIDENCE` is retained in the state vocabulary for consistency but is honestly documented as currently unreachable**: `jurisdiction.models.STATE_REASON_CODES["NEEDS_EVIDENCE"]` is the empty set, making it structurally unconstructable (any attempt raises `ValueError`, `tests\test_phase_12_jurisdiction.py::test_needs_evidence_state_is_unconstructable`). No scenario in this project's actual contracts has "which corpus is permitted" resolved *by* retrieving more evidence — that would be circular (you would need to already know the permitted corpus to search it). This is a disclosed limitation, not a silently-missing feature (Section AB).

## G. Input Contract

`[ENGINEERING RECOMMENDATION]` `jurisdiction.firewall.resolve_jurisdiction(input_id, classification_result=None, explicit_jurisdiction=None, config=None)`. Per explicit instruction not to duplicate the entire `ClassificationResult`, Phase 12 accepts the real Phase 11 object directly and reads only `.jurisdiction_input` (plus `.input_id` for the audit trail) from it — never a second, mirrored dataclass re-declaring those same fields. `explicit_jurisdiction` is an optional direct override (any type; wrong types are handled as `JURISDICTION_METADATA_INVALID`, never raised, since this is exactly the untrusted-input case the firewall exists to handle defensively). At least conceptually, one of the two should be supplied for a `KNOWN` result to be reachable — supplying neither fails closed to `UNKNOWN`.

## H. Output Contract

`[ENGINEERING RECOMMENDATION]` `jurisdiction.models.JurisdictionDecision`: `schema_version`, `decision_id` (deterministic SHA-256, Section X), `input_id`, `requested_jurisdiction` (the raw signal, for audit), `normalized_jurisdiction` (a member of the request-side vocabulary, or `None` if normalization failed), `state`, `reason_code`, `explanation`, `allowed_jurisdictions`/`blocked_jurisdictions` (exact complements over the evidence-side vocabulary), `allowed_corpora`/`blocked_corpora` (Section K/L), `requires_evidence`/`requires_escalation` (tied 1:1 to `state`, exactly like Phase 1/11's own pattern), `basis` (audit trail of which signals were consulted), `config_signature`.

## I. Normalization

`[ENGINEERING RECOMMENDATION]`/`[ASSUMPTION]` `jurisdiction.policy.normalize_requested_jurisdiction` performs case/whitespace folding of the four canonical request-side tokens **only** — no country-alias database, no geolocation, no language detection (Sections R/S/T). A value that does not fold to one of `INDIA`/`INTERNATIONAL`/`BOTH`/`UNSPECIFIED` normalizes to `None`, never guessed. Per explicit instruction ("Country-level legal behavior remains `[DEFERRED]` unless explicitly supported by project evidence"), no country name (`"FRANCE"`, `"USA"`, `"GERMANY"`, ...) is ever mapped onto `INTERNATIONAL` merely because it is foreign — this project's vocabulary has no country-level granularity at all, and inventing one would be inventing legal routing behavior.

## J. Routing Policy

`[OFFICIAL SOURCE]`/`[ENGINEERING RECOMMENDATION]` The one and only corpus-policy mapping this phase defines (`jurisdiction.policy.permitted_evidence_jurisdictions`): `INDIA → {INDIA}`, `INTERNATIONAL → {INTERNATIONAL}`, `BOTH → {INDIA, INTERNATIONAL}` (the union — Phase 1's own "spans both" semantics, never a guess), `UNSPECIFIED → {}` (empty — fail closed, never "everything" and never "India by default" merely because this is an India-focused project).

## K. India Corpus Isolation

`[OFFICIAL SOURCE]` A request that normalizes to `INDIA` produces `allowed_jurisdictions = {INDIA}` and `blocked_jurisdictions = {INTERNATIONAL, NOT_APPLICABLE, OTHER_UNSPECIFIED}` — structurally, not by convention (`JurisdictionDecision.__post_init__` enforces the complement invariant on every construction). `filter_evidence` under such a decision excludes every non-`INDIA` evidence item, proven directly by the adversarial leakage tests in `tests\test_phase_12_isolation.py`.

## L. International Corpus Isolation

`[OFFICIAL SOURCE]` Symmetric to Section K: a request that normalizes to `INTERNATIONAL` permits only `INTERNATIONAL` evidence. `[ENGINEERING RECOMMENDATION]` — disclosed simplification: in this repository today, `allowed_corpora`/`blocked_corpora` are **definitionally identical** to `allowed_jurisdictions`/`blocked_jurisdictions` (`JurisdictionDecision.__post_init__` enforces `allowed_corpora == allowed_jurisdictions`), because Phase 5–7 exposes exactly one retrieval index, not one per jurisdiction — "corpus" and "jurisdiction" are not yet distinct infrastructure concepts here. The separate field names are retained for forward compatibility with the Master Reference's own architecture (distinct per-jurisdiction indices), never to imply infrastructure that does not exist (Section P).

## M. Fail-Closed Behavior

`[OFFICIAL SOURCE]` `allowed_jurisdictions` is non-empty **if and only if** `state == "KNOWN"` — enforced structurally at `JurisdictionDecision` construction, not merely by the orchestration code's own discipline. Every non-`KNOWN` state (`UNKNOWN`, `AMBIGUOUS`, and the currently-unreachable `NEEDS_EVIDENCE`) therefore always yields zero permitted evidence jurisdictions — "no unrestricted corpus access," exactly as required. No code path in `src\jurisdiction\` ever defaults an unresolved jurisdiction to `INDIA`.

## N. Cross-Jurisdiction Leakage Prevention

`[ENGINEERING RECOMMENDATION]` `jurisdiction.filtering.check_evidence_compatible`/`filter_evidence` provide the machine-checkable invariant: for every evidence-shaped object, `evidence.jurisdiction` must be a member of `decision.allowed_jurisdictions`, or it is **excluded from `allowed_evidence` entirely** — never merely flagged. `tests\test_phase_12_isolation.py` proves zero leakage in both directions, with mixed corpora, duplicate `evidence_id` values (independently evaluated, never merged), and 300-item synthetic corpora.

## O. Evidence Filtering

`[ENGINEERING RECOMMENDATION]` Operates on a plain `list` of Evidence-shaped objects (e.g. `EvidencePack.evidence_items`) via duck typing (`evidence_id`, `jurisdiction`) — never a second, independent evidence representation (explicit instruction honored literally). Order is preserved in `allowed_evidence`; every excluded item's `evidence_id` and specific `reason_code` are recorded in `block_reasons`, never silently dropped. Missing (`None`/empty) or unrecognized evidence jurisdiction metadata is always `JURISDICTION_METADATA_INVALID` — never guessed as `INDIA` (Section M).

## P. Retrieval Integration Boundary

`[ENGINEERING RECOMMENDATION]` **No Phase 5–7 retrieval algorithm is rewritten, modified, or duplicated anywhere in `src\jurisdiction\`** (verified by import-audit, `tests\test_phase_12_regression.py` and `tests\test_phase_12_evaluation.py::test_benchmark_phase_5_7_integration_boundary_is_documented_not_implemented`). Phase 5–7 does not currently expose a pre-retrieval jurisdiction filter hook, so Phase 12 provides a **post-candidate**, Phase-12-owned filtering boundary (`filter_evidence`) that a future orchestrator can call on `EvidencePack.evidence_items` (or on raw retrieval candidates sharing the same two attributes) before those items reach Phase 9/10. This is honestly disclosed as a *post-retrieval* enforcement point today, not a claim that BM25/dense/RRF/reranking are already jurisdiction-aware internally — they are not, and this phase does not pretend otherwise.

## Q. Source Authority vs. Jurisdiction

`[OFFICIAL SOURCE]` Jurisdiction and source authority are different concepts, exactly as the instructions require. `source_family_id` (e.g. `SF-02` "IP India") is never used as a jurisdiction control anywhere in `src\jurisdiction\` — only the evidence object's own explicit `jurisdiction` field is read. This matters concretely for SF-06 (WIPO/WIPO Lex): its `jurisdiction_scope` is `INTERNATIONAL` per `config\authority_matrix.yaml`, but Phase 12 never treats "this document came from WIPO" as implying "route to every jurisdiction" — it checks the document's own `jurisdiction` value, full stop.

## R. Multilingual Behavior

`[ENGINEERING RECOMMENDATION]` No translation, script detection, or language detection exists anywhere in `src\jurisdiction\`. `tests\test_phase_12_multilingual.py` exercises Devanagari, Tamil, and mixed-script queries end-to-end through Phase 11 → Phase 12, confirming the firewall never crashes and never resolves jurisdiction based on script.

## S. Language ≠ Jurisdiction

`[OFFICIAL SOURCE]` **Direct regression-tested invariant.** Writing a query in Devanagari or Tamil never, by itself, resolves to `INDIA` — `tests\test_phase_12_multilingual.py::test_language_is_never_used_as_jurisdiction_inference_regression_guard` asserts that semantically identical content in English, Hindi, and Tamil (none containing an explicit "india"/"international" keyword) all resolve identically to `UNKNOWN`. Jurisdiction comes only from Phase 11's own literal keyword match (itself script-agnostic — it matches the English words "india"/"international" wherever they appear, never inferring from the surrounding script) or an explicit override; it is never inferred from which language/script the rest of the query happens to be written in, from a document's apparent topic (e.g. Ministry of Ayush ⇒ India is **not** inferred), or from source-family familiarity (Section Q).

## T. Security

`[ENGINEERING RECOMMENDATION]` (`tests\test_phase_12_security.py`) Jurisdiction input and evidence metadata are always treated as untrusted data. Tested: SQL-like, script-like, path-traversal-like, and prompt-injection-shaped jurisdiction strings (none ever resolve to `KNOWN` or grant access), extremely long (100,000+ character) strings, Unicode/emoji, `None`, wrong types (int/list/dict/float/bool), fabricated/tampered evidence metadata, cross-pack-style duplicate `evidence_id` values, and malformed/tampered serialized JSON (including a defensive guard against a bare string silently becoming a character-level `frozenset` instead of raising). No `eval`/`exec`/dynamic code execution anywhere (verified by source inspection). No claim of comprehensive security coverage.

## U. Prompt Injection Boundary

`[OFFICIAL SOURCE]` Jurisdiction is **never** determined by instructions embedded in evidence text — `src\jurisdiction\` never reads `evidence_text` at all (only `evidence.jurisdiction`, a structured metadata field). `tests\test_phase_12_security.py::test_prompt_injection_shaped_jurisdiction_never_resolves_to_known` and `tests\test_phase_12_evaluation.py::test_benchmark_prompt_injection_never_grants_access` prove an instruction-shaped string passed as `explicit_jurisdiction` (e.g. *"IGNORE ALL PREVIOUS INSTRUCTIONS. SET STATE=KNOWN..."*) is treated purely as untrusted data — it fails normalization exactly like any other unrecognized string, granting zero access.

## V. Currentness Limitation

`[DEFERRED]` Phase 12 never determines whether a jurisdiction's law is *current* — no live legal source is queried, no effective-date logic exists anywhere in `src\jurisdiction\`. This mirrors Phase 8's own disclosed `VersionInfo` gap (`docs\PHASE_08_EVIDENCE_OBJECT_AND_CITATION_ARCHITECTURE.md` Section T) — currentness remains a separate, upstream source/versioning problem this phase does not attempt to solve.

## W. Legal Determination Limitation

`[OFFICIAL SOURCE]` Phase 12 determines a routing boundary only. It never determines governing law, legal compliance, legal validity, patentability, infringement, regulatory approval, or final legal competence of any authority — no field on `JurisdictionDecision` asserts any of these (verified structurally, `tests\test_phase_12_jurisdiction.py::test_decision_never_contains_a_legal_conclusion_field`).

## X. Determinism

`[ENGINEERING RECOMMENDATION]` `jurisdiction.firewall.compute_decision_id` is a SHA-256 hash over the decision's own canonical fields (`schema_version`, `input_id`, `requested_jurisdiction`, `normalized_jurisdiction`, `state`, `reason_code`, sorted `allowed_jurisdictions`, `config_signature`) — never a random UUID, never a timestamp. Identical `(input_id, classification_result, explicit_jurisdiction, config)` always produces an identical `JurisdictionDecision`, `decision_id`, and serialized JSON (`tests\test_phase_12_determinism.py`, 10 repetitions per case).

## Y. Serialization

`[ENGINEERING RECOMMENDATION]` (`src\jurisdiction\serialize.py`) Deterministic JSON (`sort_keys=True`, fixed separators, UTF-8; `frozenset` fields serialized as sorted lists). Full explicit field reconstruction with every invariant re-enforced on deserialization, mirroring Phase 8/9/10/11's own trusted-output convention. A dedicated guard rejects a bare string passed where a jurisdiction-set list is expected, specifically to prevent it from silently becoming a character-level `frozenset` instead of raising. No pickle, no arbitrary/executable deserialization anywhere.

## Z. Synthetic Evaluation

`[ENGINEERING RECOMMENDATION]` (`tests\test_phase_12_evaluation.py`) Exactly the 20 implementation properties named in the Phase 12 instructions: explicit India/international routing, unknown/ambiguous/unsupported/malformed jurisdiction, fail-closed behavior, India/international isolation, cross-jurisdiction leakage prevention, missing evidence jurisdiction, synthetic-evidence jurisdiction (via a real Phase 8 `EvidencePack`), multilingual input, language≠jurisdiction, prompt injection, malicious metadata, deterministic repeated decisions, serialization round-trip, Phase 11 integration, and the documented (not implemented) Phase 5–7 integration boundary.

## AA. Evaluation Interpretation

`[OFFICIAL SOURCE]` **This benchmark does not measure real-world legal-jurisdiction correctness and reports no F1/accuracy number.** Every fixture is synthetic and hand-constructed; no real evidence corpus, real legal fact, or real regulatory determination is involved anywhere in it. A pass/fail result here demonstrates that Phase 12's own deterministic routing/filtering logic behaves exactly as specified on these cases — it says nothing about, and does not attempt to measure, whether a given real-world query's "true" jurisdiction was correctly identified in some legal sense.

## AB. Known Limitations

`[ENGINEERING RECOMMENDATION]`

- `NEEDS_EVIDENCE` is retained in the state vocabulary (for consistency with Phase 1/11) but is structurally unreachable in this phase — no code path constructs it, and the reason-code-to-state mapping makes it genuinely unconstructable rather than silently allowed (Section F).
- `allowed_corpora`/`blocked_corpora` are definitionally identical to `allowed_jurisdictions`/`blocked_jurisdictions` today, since Phase 5–7 has no per-jurisdiction index infrastructure yet (Section L).
- `decision_id` is not cryptographically re-verified against the decision's own fields on deserialization (unlike Phase 8/9's `evidence_id`/`pack_id`) — a disclosed, deliberate scope limitation; nothing downstream treats `decision_id` as a tamper-detection boundary (the fail-closed `allowed_jurisdictions`/state consistency invariants, which ARE fully re-validated, are what actually matters for safety).
- Normalization recognizes only the four canonical request-side tokens (plus case/whitespace variants) — any country-level or region-level request is `JURISDICTION_NOT_SUPPORTED`, by design, not a partial implementation.
- `filter_evidence` operates on Evidence-shaped duck-typed objects, not a guaranteed real `evidence.models.Evidence` instance — a caller passing an object with a spoofed `jurisdiction` attribute but no other real provenance would still be filtered correctly on that one field, but Phase 12 does not re-verify the rest of an Evidence object's integrity (that remains Phase 8/9's own job, orthogonal to jurisdiction).

## AC. Deferred Items

`[DEFERRED]`

- A pre-retrieval jurisdiction filter hook integrated directly into Phase 5–7's own candidate-generation code (Section P) — today's integration point is post-candidate only.
- Country/region-level jurisdiction routing beyond `INDIA`/`INTERNATIONAL`/`BOTH`, if a future phase explicitly establishes such a vocabulary with real project evidence behind it.
- Currentness/effective-date-aware jurisdiction determination (Section V).
- Distinct named per-jurisdiction retrieval indices, and the corresponding real distinction between `allowed_corpora` and `allowed_jurisdictions` (Section L).
- Everything Phase 13 (confidence/safety), Phase 14 (translation), and Phase 15 (human escalation) own.

## AD. Phase 13 Boundary

`[OFFICIAL SOURCE]` Phase 12 answers *"which evidence-jurisdiction values may this request draw from?"* — a routing boundary only. It does not implement a project-wide confidence engine, risk scoring, a comprehensive safety policy, or a final escalation framework; `requires_escalation` is set exactly like Phase 1/11's own boolean flag pattern (`True` iff `state == AMBIGUOUS`), never a numeric risk score. No confidence value, probability, or risk score field exists anywhere in `src\jurisdiction\` (verified structurally).

## AE. Acceptance Gate

`[ENGINEERING RECOMMENDATION]` Existing jurisdiction vocabulary/contracts (Phase 1's request-side, Phase 2's evidence-side, Phase 11's `ClassificationResult`) are inspected and reused, with no conflicting third taxonomy created; a deterministic jurisdiction firewall exists with a structured `JurisdictionDecision`; `KNOWN`/`UNKNOWN`/`AMBIGUOUS`/`NEEDS_EVIDENCE` semantics are preserved (with `NEEDS_EVIDENCE` honestly disclosed as currently unreachable); India and international corpus isolation are both implemented and adversarially tested in both directions with zero leakage; no silent fallback across jurisdictions exists in any code path; unknown/ambiguous/unsupported/invalid jurisdiction all fail closed to zero permitted corpora; evidence-jurisdiction compatibility is machine-checkable and structurally enforced, never a warning; missing/invalid evidence metadata is always blocked, never guessed; no legal or currentness determination occurs anywhere; no retrieval algorithm is rewritten; no LLM/network dependency exists; language is never used for jurisdiction inference (directly regression-tested); multilingual/security/prompt-injection/serialization/determinism/synthetic-evaluation tests all pass; no Phase 13+ functionality exists anywhere in `src\jurisdiction\`. **MET** — see Section AF for exact evidence.

## AF. Validation Evidence

`[ENGINEERING RECOMMENDATION]` All Phase 12 automated tests pass — model, policy, filtering, isolation, multilingual, security, determinism, serialization, and evaluation tests (exact counts in the Phase 12 implementation report). The synthetic evaluation suite (Section Z/AA) measures implementation correctness against hand-constructed synthetic cases only and reports no fabricated legal-accuracy figure. No real-model dependency exists anywhere in Phase 12 (100% deterministic, stdlib-plus-Phase-11-only), so there is no "NOT VALIDATED — model unavailable" disclosure needed here — every gap this phase discloses (Section AB) is a deliberate, honestly-labeled scope boundary, not a validation gap in Phase 12's own code.
