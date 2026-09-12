# PHASE 14 — MULTILINGUAL DELIVERY

Status: CONTRACT + IMPLEMENTATION DOCUMENT (Phase 14 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_10_GROUNDED_GENERATION.md`, `docs\PHASE_13_CONFIDENCE_SAFETY_ABSTENTION.md`
Machine-readable counterpart: `config\multilingual_delivery_contract.yaml`
Implementation: `src\multilingual\models.py`, `preservation.py`, `providers.py`, `delivery.py`, `serialize.py`

**Translation is a presentation layer, never a decision layer.** By the time Phase 14 runs, Phase 10 has already decided whether an answer is grounded, Phase 13 has already decided whether it is safe to present, and Phase 8/9 have already decided which evidence IDs are real and valid. Phase 14 never re-opens any of those decisions. It only ever does two things: (1) classify the *script* of an incoming query and preserve the original text untouched, and (2) if a supported target language is requested and the upstream answer is both grounded and safe, optionally run it through a translation provider for display — while structurally guaranteeing that provider can never touch anything but the display string.

---

## A. Phase Objective

`[OFFICIAL SOURCE]` `docs\PHASE_TRACKER.md`'s Phase 14 entry: *"Serve evaluated languages while preserving evidence identity... Meaning and evidence references survive translation; only evaluated languages are advertised."* `docs\MASTER_REFERENCE_LOCK.md` Section E lists *"Multilingual: Preserve original query + canonical representation; translate final answers without translating away exact section/article identifiers"* as a locked architectural principle, and names a **Bhashini adapter** as the translation-direction candidate (Section E, "Final Core Stack").

## B. Scope

In scope: `MultilingualInputContext`/`MultilingualConfig`/`TranslationOutput`/`MultilingualDeliveryResult` models; deterministic script detection (`detect_script`); Unicode NFC canonicalization (`canonicalize_query`); a `TranslationProvider` abstraction plus a deterministic, offline `FakeTranslationProvider`; a single output-side orchestration function (`deliver_response`) that ties an already-produced Phase 10 `GroundedResponse` and Phase 13 `SafetyDecision` together with an optional translation attempt; deterministic serialization.

## C. Non-Scope

Out of scope (no code for any of these exists anywhere in `src\multilingual\`): a real Bhashini or any other live translation adapter (credentials, endpoints, network calls); language detection via IP/locale/timezone; jurisdiction inference from language or script; a handcrafted legal-terminology translation dictionary; re-implementing classification (Phase 11), jurisdiction routing (Phase 12), citation validation (Phase 9), generation (Phase 10), or safety policy (Phase 13); human-in-the-loop workflow, reviewer queues, or approval systems (Phase 15's own scope); FastAPI, React, deployment, monitoring, backup, corpus refresh, or CI/CD (Phases 17-22's own scope); semantic entailment; new retrieval, classifier, jurisdiction engine, citation validator, or generation engine of any kind.

## D. Architecture

`[ENGINEERING RECOMMENDATION]` Two independent halves, matching the two ends of the pipeline this phase wraps:

1. **Input-side (`preservation.py`)**: `build_input_context(input_id, original_query, requested_language) -> MultilingualInputContext`. Runs at query time, before classification/retrieval/generation — purely a script-detection + canonicalization step, never a translation.
2. **Output-side (`delivery.py`)**: `deliver_response(input_context, grounded_response, safety_decision, translation_provider, source_language, config) -> MultilingualDeliveryResult`. Runs after Phase 10 and Phase 13 have already produced their real objects — eight ordered, deterministic, first-match-wins gates (`D2`..`D9`), mirroring the exact "ordered rule list" convention Phase 1/9/11/12/13 already established for their own decision flows.

Neither half performs retrieval, classification, jurisdiction routing, citation validation, or generation. `src\multilingual\` imports only `generation.models.GroundedResponse` and `safety.models.SafetyDecision` (both read-only, never recomputed) plus the standard library.

## E. Language Handling

`[OUR ENHANCEMENT]` `SUPPORTED_LANGUAGE_TAGS = {"en", "hi", "ta"}` — a small, explicitly-scoped vocabulary naming exactly the languages this project's own prior-phase test fixtures (Phase 6/7/8/9/10/11/12/13's multilingual test files) have already exercised at the Unicode-plumbing level. This is **not** a list the Master Reference itself specifies (it names no specific language set — only "Bhashini" as the adapter direction and "evaluate only supported languages" as the governing principle); it is this project's own honest, minimal starting point. `UNSPECIFIED` is a distinguished token meaning "no language was requested" — always accepted, never triggering translation, and never confused with `None` at the API boundary (`requested_language=None` and `requested_language="UNSPECIFIED"` are handled identically by gate D5, by design). A language outside this set is reported `UNSUPPORTED_LANGUAGE`, never silently attempted.

## F. Script Handling

`[OFFICIAL SOURCE — Unicode Standard block assignments]` `detect_script(text) -> {"LATIN","DEVANAGARI","TAMIL","MIXED","UNKNOWN"}` is a deterministic count of which of three known Unicode letter ranges (Basic Latin + Latin-1 Supplement, Devanagari U+0900-097F, Tamil U+0B80-0BFF) appear in the text — zero matches is `UNKNOWN` (never guessed as a default script), more than one distinct script present is `MIXED` (never silently collapsed to either), exactly one is that script's tag. This is a **script** classification only — a Unicode codepoint-range fact about the characters used — never a language identification claim, never a jurisdiction signal, and it uses no external library, model, or network call.

## G. Language vs Jurisdiction

`[OFFICIAL SOURCE]` Nothing anywhere in `src\multilingual\` maps a language or script onto a jurisdiction value. Devanagari script does **not** imply the language is Hindi; Tamil script does **not** imply a particular jurisdiction; `requested_language` never feeds Phase 12's `JurisdictionDecision`, which is only ever read/passed through unmodified. This mirrors Phase 12's own already-proven invariant ("language is never used for jurisdiction inference") and is directly regression-tested here (`tests\test_phase_14_language.py`) by asserting `detect_script`'s output type/vocabulary has zero overlap with Phase 1's `REQUEST_JURISDICTION_VALUES` or Phase 2's `EVIDENCE_JURISDICTION_VALUES`.

## H. Input Contract

`[ENGINEERING RECOMMENDATION]` `build_input_context(input_id: str, original_query: str, requested_language: Optional[str] = None) -> MultilingualInputContext`. `requested_language` is deliberately **untrusted, permissive input** at construction (like Phase 9's `CitationReference`) — any string is accepted here; classification as supported/unsupported happens later, only inside `deliver_response`.

## I. Output Contract

`[ENGINEERING RECOMMENDATION]` `MultilingualDeliveryResult`: `schema_version`, `result_id` (deterministic SHA-256, Section Y), `input_id`, `original_query`, `canonical_query`, `requested_language`, `detected_script`, `delivery_status` (`DELIVERED`/`TRANSLATION_FAILED`/`UNSUPPORTED_LANGUAGE`/`UPSTREAM_BLOCKED`), `reason_code` (one of 8, each independently reachable and tested), `explanation`, `answer_text`/`answer_language` (set if and only if `DELIVERED`), `translation_applied`, `provider_name`, `cited_evidence_ids`/`grounding_status`/`safety_status`/`synthetic` (always a direct, unmodified passthrough from the real upstream Phase 9/10/13 objects — never re-derived from `answer_text`), `evidence_preservation_status` (always `"PRESERVED"` — a structural, machine-checkable audit constant, not a genuinely variable state), `delivery_metadata`, `config_signature`. Every invariant (status/reason-code pairing, `answer_text`/`answer_language` presence rule, no-duplicate-citation-ids) is enforced at construction, mirroring Phase 9/11/12/13's own discipline.

## J. Original Input Preservation

`[ENGINEERING RECOMMENDATION]` `original_query` is stored verbatim, byte/character-faithful, on `MultilingualInputContext` and copied through unchanged onto `MultilingualDeliveryResult.original_query` — it is never overwritten by `canonical_query`, never sanitized, never truncated, and remains recoverable from the structured result regardless of delivery outcome (`tests\test_phase_14_preservation.py`, `tests\test_phase_14_security.py::test_mixed_script_prompt_injection_in_original_query_does_not_affect_delivery`).

## K. Canonicalization

`[OFFICIAL SOURCE — Unicode Standard Annex #15]` `canonicalize_query` performs Unicode NFC normalization ONLY (`unicodedata.normalize("NFC", text)`) — a well-established, meaning-preserving standard text-representation transformation that collapses combining-character variants (e.g. `"e" + U+0301` → `"é"`) into one canonical form. It is never a translation, never a rewrite of meaning, and never dependent on detected script or requested language. `canonical_query` is stored as a field distinct from `original_query` — both survive independently.

## L. Translation Abstraction

`[ENGINEERING RECOMMENDATION]` `TranslationProvider` (abstract): `provider_name` (property) and `translate(text, source_language, target_language) -> TranslationOutput`. Provider selection is always explicit — the caller passes a concrete instance to `deliver_response`; nothing in this package chooses, guesses, or silently falls back to a different provider. `TranslationOutput` (`translated_text`, `provider_name`, `source_language`, `target_language`, `success`, `failure_reason`, `metadata`) is treated as **untrusted output** everywhere downstream: `deliver_response` consults it only for `translated_text`, never for anything security-relevant, and its `metadata` dict is structurally forbidden from carrying credential-shaped keys (reusing Phase 10's own `GenerationOutput` guard verbatim).

## M. FakeTranslationProvider

`[ENGINEERING RECOMMENDATION]` Deterministic, offline, no-network test double mirroring Phase 10's `FakeGenerationProvider` exactly. Three mutually-exclusive construction modes: `response_text="..."` (always that exact text), `respond_fn=callable` (full input-dependent control — used deliberately in `tests\test_phase_14_security.py` to construct adversarial payloads), `fail_with="..."` (always reports failure with that reason). Never touches the network or filesystem (verified by source inspection, `tests\test_phase_14_translation.py::test_fake_provider_never_touches_network_or_filesystem`) and is not itself a claim of real translation quality.

## N. Bhashini Status

`[OFFICIAL SOURCE]` The Master Reference names Bhashini as the multilingual adapter direction (`config\authority_matrix.yaml` SF-08; `docs\MASTER_REFERENCE_LOCK.md` Section E). **LIVE TRANSLATION — DEFERRED.** `[DEFERRED]` No live Bhashini (or any other) adapter is implemented anywhere in this repository — no credentials, no network access, no specific endpoint, no specific language pair, and no latency/availability guarantee is assumed to exist in this development environment. A future adapter would subclass `TranslationProvider` exactly like `FakeTranslationProvider` does, with no other change required anywhere in this package. `config\multilingual_delivery_contract.yaml`'s `bhashini_adapter_status` field records this explicitly: `"DEFERRED_NO_CREDENTIAL_OR_ENDPOINT_OR_LANGUAGE_PAIR_ASSUMED"`.

**LIVE TRANSLATION QUALITY — NOT VALIDATED.** No BLEU/COMET/human-evaluation number, no accuracy claim, and no latency measurement exists anywhere for any language, including `en`/`hi`/`ta` — nothing beyond Unicode-plumbing-level testing against the deterministic `FakeTranslationProvider` has been performed.

## O. Translation Failure

`[ENGINEERING RECOMMENDATION]` Three independently-reachable failure/non-translation paths, all fail-explicit rather than fail-silent: `MISSING_TRANSLATION_PROVIDER` (translation to a supported language was required but no provider was supplied — `deliver_response` never silently delivers an untranslated or fabricated answer instead); `TRANSLATION_PROVIDER_FAILED` (the provider raised an exception, returned a value that is not a `TranslationOutput`, or itself reported `success=False` — all three are treated identically: `delivery_status="TRANSLATION_FAILED"`, `answer_text=None`); a provider is never retried, never silently substituted, and never allowed to crash the orchestrator (`tests\test_phase_14_delivery.py`, gates D7/D8).

## P. Unsupported Language

`[ENGINEERING RECOMMENDATION]` A `requested_language` outside `{"en","hi","ta","UNSPECIFIED",None}` is reported `delivery_status="UNSUPPORTED_LANGUAGE"`, `reason_code="UNSUPPORTED_LANGUAGE_REQUESTED"`, `answer_text=None` — never attempted, never silently downgraded to English, never guessed. This check (`D4`) runs **before** any translation-provider interaction. No claim is made that `en`/`hi`/`ta` themselves have validated translation quality (Section N) — being in the supported set means only "this project's own plumbing has been exercised for this tag," never "translation quality for this language has been measured."

## Q. Evidence Preservation

`[OFFICIAL SOURCE]` `MultilingualDeliveryResult.cited_evidence_ids` is always `list(grounded_response.cited_evidence_ids)` — a direct copy from the real, already-validated Phase 9/10 object, with **zero** code path anywhere in `delivery.py` that derives it from `answer_text`, `TranslationOutput`, or any provider call. `evidence_preservation_status` is a structural audit constant (`"PRESERVED"`, the only value in its vocabulary) recorded on every result, `DELIVERED` or not. `tests\test_phase_14_security.py` proves this adversarially: even when the translation provider's output contains fabricated evidence-ID-shaped text (`"evidence_id=FAKE-EVIDENCE-999"`), `result.cited_evidence_ids` remains exactly the original, real list.

## R. Citation Preservation

`[OFFICIAL SOURCE]` Phase 14 never parses `answer_text`/`TranslationOutput.translated_text` for `[[CITE:...]]` markers or any other structured citation syntax — that parsing belongs exclusively to Phase 10 (`generation.grounding`), already completed before `deliver_response` ever runs. A malicious translation containing citation-marker-shaped text (e.g. `"[[CITE:FAKE-EVIDENCE-999]]"`) is delivered verbatim as **display text only** and never re-interpreted as a real citation (`tests\test_phase_14_security.py::test_malicious_translation_cannot_alter_cited_evidence_ids`).

## S. Grounding Preservation

`[OFFICIAL SOURCE]` `grounding_status` on the result is always `grounded_response.grounding_status` (or `None` if no response was supplied) — Phase 10's own status is read once, at gate D3, and then copied unchanged into the final result; no translation outcome, successful or failed, can change it. A `GENERATION_FAILED`/`ABSTAINED` response is blocked at D3 **before** any translation attempt — translation can never "rescue" an ungrounded answer into a delivered one (`tests\test_phase_14_delivery.py`, gate D3; `tests\test_phase_14_security.py::test_translation_provider_cannot_rescue_an_abstained_upstream_result`).

## T. Regulatory Terminology Limitations

`[ASSUMPTION]`/`[DEFERRED]` No handcrafted legal/regulatory terminology dictionary or glossary exists anywhere in this phase. A generic translation provider (real or fake) has no special handling for regulatory terms of art (e.g. exact section/article numbers, statute names) — the Master Reference's own principle ("translate final answers without translating away exact section/article identifiers," `docs\MASTER_REFERENCE_LOCK.md` Section E) is honored **structurally** by never letting translation touch `cited_evidence_ids` or any identifier field, but the `answer_text` string itself, once handed to a real translation provider, is not guarded against a provider mistranslating an inline section number that appears only as prose text. This residual risk is disclosed, not hidden — it becomes directly testable only once a real (non-fake) provider exists, which this phase deliberately does not implement (Section N).

## U. Identifier Preservation

`[OFFICIAL SOURCE]` Evidence IDs, document IDs, content hashes, source-family IDs, and jurisdiction values are never read from, written to, or derived from anything in `src\multilingual\` — they live exclusively inside Phase 8's `Evidence`/`EvidencePack` objects, which this phase never imports or touches. `tests\test_phase_14_security.py::test_malicious_translation_leaves_underlying_evidence_pack_identity_intact` proves this by re-running Phase 8's own `verify_pack_identity`/`verify_evidence_identity` cryptographic checks against the original pack both before and after a malicious `deliver_response` call, with identical results.

## V. Mixed-Language Handling

`[ENGINEERING RECOMMENDATION]` A query containing more than one script (e.g. `"Ayurveda आयुर्वेद மருந்து"`) is honestly classified `MIXED` by `detect_script` — never forced into a single script bucket, never silently collapsed, and never treated as an error. `MIXED` carries no information about jurisdiction or which language(s) are "primary" — it is purely descriptive of the characters observed. `requested_language` and `detected_script` remain independent fields throughout: a user may write a `LATIN`-script query while requesting `hi` output, and delivery proceeds by that `requested_language` value regardless of the input script.

## W. Security

`[ENGINEERING RECOMMENDATION]` The full adversarial-translation invariant is structural (enforced by control flow, not merely by convention): `_build_result` in `delivery.py` reads `cited_evidence_ids`/`grounding_status`/`synthetic` from `grounded_response` and `safety_status` from `safety_decision` — never from `output` (the `TranslationOutput`). `output.translated_text` is assigned to exactly one field, `answer_text`, and nowhere else. `TranslationOutput.metadata` is checked for credential-shaped keys at construction (`api_key`, `credential`, `secret`, `password`, `access_token`, `auth_token`, `bearer` substrings, case-insensitive) — mirroring Phase 10's own `GenerationOutput` guard. A translation provider can raise, return the wrong type, or report failure without ever crashing `deliver_response` or corrupting a result (Section O). Prompt-injection-shaped text in `original_query`, `requested_language`, or provider output is preserved as inert display data everywhere it appears, never executed, evaluated, or treated as a structured instruction.

## X. Adversarial Translation

`[OFFICIAL SOURCE]` This is the phase's single most important test requirement, verified directly by `tests\test_phase_14_security.py` (27 tests): a malicious `TranslationProvider` (via `respond_fn`, deliberately crafted to emit fake evidence IDs, fake `[[CITE:...]]` markers, fake `jurisdiction=`/`safety_status=`/`grounding_status=` override strings, HTML/script-injection payloads, and classic "ignore previous instructions" prompt-injection phrasing) is proven, for every payload in the catalogue, unable to alter `cited_evidence_ids`, `grounding_status`, `safety_status`, `synthetic`, or the underlying `Evidence`/`EvidencePack` identity. The only field ever affected is `answer_text`, exactly as designed.

## Y. Determinism

`[ENGINEERING RECOMMENDATION]` `result_id` is a deterministic SHA-256 hash (`compute_result_id`) over exactly `schema_version`, `input_id`, `original_query`, `requested_language`, `delivery_status`, `reason_code`, `answer_text`, and `config_signature` — never a random UUID, never derived from a timestamp or call order. Repeated calls with identical inputs produce byte-identical `MultilingualDeliveryResult` objects and byte-identical serialized JSON (`tests\test_phase_14_determinism.py`); different `input_id`, different translated text, or a different delivery outcome each produce a different `result_id`.

## Z. Serialization

`[ENGINEERING RECOMMENDATION]` `serialize.py` mirrors `src\safety\serialize.py`'s convention exactly: full explicit field reconstruction on deserialization, with every dataclass invariant (closed vocabularies, status/reason-code pairing, presence rules, no-duplicate-citation-ids) re-enforced by `MultilingualDeliveryResult.__post_init__`/`MultilingualInputContext.__post_init__` — never bypassed. Malformed input (non-dict, missing field, wrong type, forged `delivery_status`, inconsistent `reason_code`, duplicate `cited_evidence_ids`) raises `MultilingualSchemaError`, never silently repaired or coerced (`tests\test_phase_14_serialization.py`, 19 tests). JSON output uses `ensure_ascii=False` — Devanagari/Tamil/emoji text round-trips without `\uXXXX` escaping.

## AA. Testing

`[ENGINEERING RECOMMENDATION]` Eight test files, 108 tests: `test_phase_14_language.py` (14 — script detection, canonicalization, language-vs-script/jurisdiction distinction), `test_phase_14_preservation.py` (10 — original/canonical query preservation, input-context invariants), `test_phase_14_translation.py` (11 — provider abstraction, `FakeTranslationProvider`, credential-key guard), `test_phase_14_delivery.py` (18 — all eight gates individually, plus type discipline), `test_phase_14_security.py` (27 — the critical adversarial-translation requirement, prompt injection, emoji/mixed-script safety), `test_phase_14_serialization.py` (19 — round-trip + malformed-input rejection), `test_phase_14_determinism.py` (9 — repeated-call/result-id/JSON determinism), `test_phase_14_regression.py` (Phase 0-13 regression, phase-boundary audit, doc completeness).

## AB. Known Limitations

`[ENGINEERING RECOMMENDATION]`, disclosed, not hidden:
1. `SUPPORTED_LANGUAGE_TAGS = {"en","hi","ta"}` is this project's own minimal, honestly-scoped starting set — not a claim the Master Reference makes and not a translation-quality claim for any of the three (Section E, N).
2. No live translation provider exists — every test uses `FakeTranslationProvider` (Section N).
3. No regulatory-terminology-preserving translation guard exists inside `answer_text` itself — only structural identifier isolation is guaranteed (Section T).
4. `answer_language` for the `LANGUAGE_UNSPECIFIED_NO_TRANSLATION_NEEDED` path is the literal token `"UNSPECIFIED"`, not a detected/inferred language of the underlying `answer_text` — Phase 10 does not tell Phase 14 what language a generated answer is actually written in, and Phase 14 does not guess it.
5. `result_id` is not cryptographically re-verified on deserialization (consistent with Phase 10/12/13's own disclosed, deliberate scope limitation on `response_id`/`decision_id`).

## AC. Deferred Items

`[DEFERRED]`: a real Bhashini (or any other live) translation adapter; any translation-quality benchmark (BLEU/COMET/human evaluation); a handcrafted regulatory-terminology glossary; language inference from anything other than an explicit `requested_language` parameter; human-in-the-loop review of translated output (Phase 15's own scope); expanded language coverage beyond `{en, hi, ta}` (would require new, real test evidence, not just a vocabulary edit).

## AD. Phase 15 Boundary

`[ENGINEERING RECOMMENDATION]` Phase 14 emits no reviewer queue, no case assignment, no notification, no escalation UI, and reuses `SafetyDecision.escalation_required` only as an upstream fact that (via `safety_status != "SAFE_TO_PRESENT"`) blocks delivery at gate D2 — it never itself decides to escalate. The actual human-in-the-loop workflow remains entirely Phase 15's own, separately not-started, scope.

## AE. Acceptance Gate

`[OFFICIAL SOURCE, as restated for this implementation]` CAP-14's text — *"Meaning and evidence references survive translation; only evaluated languages are advertised"* — is met as follows: `original_query` and `cited_evidence_ids`/`grounding_status`/`safety_status`/`synthetic` all survive translation unchanged and adversarially-proven-unmodifiable (Sections Q-X); only `{en, hi, ta}` are ever advertised as targets, each explicitly and honestly qualified as Unicode-plumbing-tested only, never translation-quality-validated (Section N); an unsupported language is rejected before any translation attempt (Section P); an unsafe/ungrounded upstream result can never be rescued by translation (Sections S, X). **MET** for this restated, honestly-scoped acceptance criterion.

## AF. Validation Evidence

`pytest tests/ -v` run twice — see the Phase 14 implementation report for the exact pass counts of both runs. Zero skips, zero xfail, zero weakened assertions anywhere in `tests\test_phase_14_*.py`. Phase 0-13 regression, Master Reference hash integrity, source-discipline audit, and phase-boundary audit (no FastAPI/React/reviewer-queue/deployment/monitoring/backup/corpus-refresh/CI-CD/semantic-entailment/new-retrieval/new-classifier/new-jurisdiction-engine/new-citation-validator/new-safety-engine/new-generation-engine code, fields, or imports anywhere in `src\multilingual\`) all pass — see `tests\test_phase_14_regression.py`.
