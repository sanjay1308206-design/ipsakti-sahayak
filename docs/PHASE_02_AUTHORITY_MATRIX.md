# PHASE 2 — AUTHORITY MATRIX

Status: CONTRACT DOCUMENT (Phase 2 deliverable)
Authoritative source: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`
Governed by: `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`
Machine-readable counterpart: `config\authority_matrix.yaml`

**Scope note `[ENGINEERING RECOMMENDATION]`:** This document locks the corpus *policy* — which source families may ever contribute evidence, what they may be trusted for, and how they relate to jurisdiction. It does not ingest, download, scrape, parse, or otherwise acquire a single document. No document exists in this repository as a result of this phase.

---

## 0. Source Families — Exactly As Named by the Master Reference

`[OFFICIAL SOURCE]` The Master Reference's Authoritative Source Strategy table names exactly eight source families. This matrix defines no more and no fewer. No source family is added because it "might be useful" — per the Final Decision Lock, *"New technologies must earn their place through measurable evidence; they should not be added simply because they sound advanced,"* which this phase treats as applying equally to new source families.

| Source Family ID | Name | Role (verbatim/paraphrased from Master Reference) |
|---|---|---|
| SF-01 | India Code | Acts, sections, rules, regulations, notifications and other Indian legal material. |
| SF-02 | IP India | Patents, trademarks, designs, GI and related public search/e-services. |
| SF-03 | Ministry of Ayush | Ayush policy, programmes and official Ayurveda-related material. |
| SF-04 | CDSCO / Drugs & Cosmetics | Regulatory material relevant to traditional drugs and Drugs & Cosmetics Rules. |
| SF-05 | FSSAI | Ayurveda Aahara regulations and related food-law material. |
| SF-06 | WIPO / WIPO Lex | International IP treaties, traditional knowledge and genetic-resources material. |
| SF-07 | TKDL | Use only authorized/publicly accessible material; do not assume protected full-database access. |
| SF-08 | Bhashini | Multilingual translation/language infrastructure through an adapter; evaluate only supported languages. |

`[OFFICIAL SOURCE]` Reminder from the Authoritative Source Strategy table's own callout: *"current official sources show that Ayurveda Aahara has its own FSSAI regulatory framework, while CDSCO separately publishes traditional-drug rules/material. The classifier must therefore distinguish food/Ayurveda-Aahara from Ayurvedic drugs instead of treating every Ayurvedic ingestible as one category."* This is why SF-04 (CDSCO) and SF-05 (FSSAI) are kept as two distinct source families rather than merged, matching `RT-04 AYURVEDA_AAHARA_FOOD` being distinct from the drug-track categories in `docs\PHASE_01_DOMAIN_TAXONOMY.md`.

## 1. Category Groupings (as requested: India / International / Knowledge / Language / Contextual)

`[ENGINEERING RECOMMENDATION]` These five groupings are an engineering governance grouping for readability; they introduce no new authority beyond Section 0.

1. **India regulatory sources:** SF-01, SF-02, SF-03, SF-04, SF-05
2. **International/IP sources:** SF-06
3. **Knowledge/traditional-knowledge sources:** SF-07
4. **Language-service sources:** SF-08 (**not** an evidence source — see Section 5)
5. **Non-authoritative contextual sources:** *(deliberately empty — see Section 6)*

## 2. Authority Matrix Table

`[OFFICIAL SOURCE]` where noted; `[ENGINEERING RECOMMENDATION]` for the classification vocabulary (tier/role enums) applied to that sourced information; `[ASSUMPTION]` flagged per-cell where the Master Reference does not state the value directly.

| ID | Authority Tier | Authority Role | Jurisdiction | Question Type Supported (Phase 1 RQ) | URL (only if in Master Reference) | Source Label |
|---|---|---|---|---|---|---|
| SF-01 | PRIMARY_OFFICIAL | PRIMARY_LEGISLATIVE_SOURCE | INDIA | RQ-01 `INDIA_LEGISLATIVE` | `https://www.indiacode.nic.in/` | `[OFFICIAL SOURCE]` |
| SF-02 | PRIMARY_OFFICIAL | IP_REGISTRY_AND_SEARCH_SERVICE | INDIA | RQ-02 `IP_REGISTRATION_AND_SEARCH` | `https://ipindia.gov.in/` | `[OFFICIAL SOURCE]` |
| SF-03 | PRIMARY_OFFICIAL | POLICY_AND_PROGRAMME_SOURCE | INDIA | RQ-03 `AYUSH_POLICY` | `https://ayush.gov.in/` | `[OFFICIAL SOURCE]` |
| SF-04 | PRIMARY_OFFICIAL | DRUG_REGULATORY_AUTHORITY | INDIA | RQ-04 `TRADITIONAL_DRUG_REGULATION` | `https://www.cdsco.gov.in/opencms/opencms/en/Traditional_Drugs/` and `https://www.cdsco.gov.in/opencms/opencms/en/Acts-and-rules/Drugs-Rules/` | `[OFFICIAL SOURCE]` |
| SF-05 | PRIMARY_OFFICIAL | FOOD_REGULATORY_AUTHORITY | INDIA | RQ-05 `AYURVEDA_AAHARA_FOOD_LAW` | `https://fssai.gov.in/upload/notifications/2022/05/62789a20b54bdGazette_Notification_Ayurveda_Aahara_09_05_2022.pdf` and `https://www.fssai.gov.in/food-law/advisories` | `[OFFICIAL SOURCE]` |
| SF-06 | PRIMARY_OFFICIAL | INTERNATIONAL_TREATY_SOURCE | INTERNATIONAL | RQ-06 `INTERNATIONAL_IP_TREATY` | `https://www.wipo.int/en/web/traditional-knowledge/wipo-treaty-on-ip-gr-and-associated-tk` and `https://www.wipo.int/wipolex/en/treaties/textdetails/19849` | `[OFFICIAL SOURCE]` |
| SF-07 | PRIMARY_OFFICIAL_RESTRICTED | TRADITIONAL_KNOWLEDGE_REGISTRY | INDIA *(`[ASSUMPTION]` — see note below)* | RQ-07 `TRADITIONAL_KNOWLEDGE_DATABASE` | **not specified** — `[ASSUMPTION]`/`[DEFERRED]`, see below | `[OFFICIAL SOURCE]` (existence/role/restriction) |
| SF-08 | SERVICE_ADAPTER | LANGUAGE_SERVICE_PROVIDER | NOT_APPLICABLE | *(none — excluded, see Section 5)* | `https://app.bhashini.ai/translate` | `[OFFICIAL SOURCE]` |

**SF-07 (TKDL) note `[ASSUMPTION]`:** the Master Reference names TKDL as a source family and states the access restriction ("authorized/publicly accessible material... do not assume protected full-database access") but does **not** state its jurisdiction classification in the India/international retrieval-firewall sense, and its access URL does **not** appear anywhere in the Master Reference's "Research Sources & Provenance" list (unlike all seven other source families, which do have URLs listed there). Both the `INDIA` jurisdiction assignment and the absence of a URL are therefore explicitly flagged, not filled in with an invented value. Locating and verifying an authorized TKDL access URL is `[DEFERRED]` to whichever future phase actually attempts TKDL corpus acquisition (not before Phase 2's own review has re-confirmed it).

**Authority tier vs. inter-family hierarchy `[ENGINEERING RECOMMENDATION]`:** `authority_tier` classifies how authoritative a source is *in absolute terms* (is this a first-party official source at all?), not a ranking used to pick a winner when two authoritative sources conflict. The Master Reference establishes no such inter-family ranking (e.g., it never states "India Code outranks CDSCO"). See `docs\PHASE_02_SOURCE_CONFLICT_POLICY.md` — no legal hierarchy is invented here.

## 3. Regulatory Domain / Question-Type Mapping

`[OFFICIAL SOURCE]` Each authoritative source family maps to exactly one Phase 1 regulatory-question category (`docs\PHASE_01_DOMAIN_TAXONOMY.md` Section D), by construction — Phase 1's `regulatory_question_categories` were themselves derived 1:1 from this same Authoritative Source Strategy table. See Section 2's "Question Type Supported" column. SF-08 (Bhashini) intentionally supports none — it is a translation adapter, not an answer source.

## 4. Provenance & Version Requirements

`[OFFICIAL SOURCE]` Directly from the Master Reference's Phase 2 Build scope: *"Source registry with authority tier, jurisdiction, document type, URL, version, effective date, retrieval date, checksum and refresh status."* Every authoritative source family (SF-01..SF-07) therefore requires, for any document it ever contributes:

- `document_type` (e.g., Act, Rule, Notification, Regulation, Gazette Notification, Advisory, Treaty Text — only types actually observed in the Master Reference's own document references are used; no document type is invented)
- `url` (the specific document's URL, not merely the family portal URL)
- `version`
- `effective_date`
- `retrieval_date`
- `checksum` (content hash)
- `refresh_status`

The full per-document shape is defined machine-readably in `config\corpus_provenance_schema.yaml`.

`[ENGINEERING RECOMMENDATION]` **Validation requirement** (not itself named by the Master Reference, but necessary to operationalize "authoritative"): before any document is eligible for `ADMIT`, its recorded metadata must be independently confirmed to match the live/official source at review time — self-declared metadata is never sufficient on its own. See `docs\PHASE_02_CORPUS_ADMISSION_POLICY.md`.

## 5. Language-Service Sources (SF-08 Bhashini) — Not an Evidence Source

`[OFFICIAL SOURCE]` Bhashini's row in the Authoritative Source Strategy table describes it as *"Multilingual translation/language infrastructure through an adapter; evaluate only supported languages."* It is a **service**, not a document source. It:

- contributes **no** regulatory question type (Section 3),
- has **no** corpus admission status because it is never a candidate for corpus admission (`corpus_role: SERVICE_ADAPTER` in `config\authority_matrix.yaml`),
- is excluded from `permitted_source_families` in `config\corpus_lock.yaml` (which lists only families that may contribute evidence documents).

`[OFFICIAL SOURCE]` Per the Master Reference's Research Sources & Provenance entry for Bhashini: *"verify exact service terms and supported languages before production use."* This obligation is preserved verbatim as a limitation, not dropped.

## 6. Authoritative vs. Contextual vs. Prohibited Sources

`[ENGINEERING RECOMMENDATION]`, extending the Master Reference's explicit instruction to *"Use a curated authoritative corpus and avoid mass scraping"* into an enforceable three-way boundary:

### 6.1 AUTHORITATIVE
Exactly SF-01 through SF-07. Only documents traceable to one of these seven families, with complete provenance (Section 4) and a `VALIDATED` review, may ever back a citation.

### 6.2 CONTEXTUAL / NON-AUTHORITATIVE
`[ENGINEERING RECOMMENDATION]` **Deliberately empty at Phase 2.** The Master Reference does not name any source as merely "contextual," and this project does not invent a contextual tier as a backdoor into the evidence corpus. If a future phase identifies a genuine need for non-authoritative background material, that requires an explicit corpus-lock version bump and review (Section 8) — it does not exist today, and no code or document in this repository may treat any source as "contextual evidence."

### 6.3 PROHIBITED / UNTRUSTED
`[ENGINEERING RECOMMENDATION]` The following source classes are explicitly barred from ever entering the authoritative corpus, regardless of how they are hosted:

- Search engines (as a primary source, rather than a discovery tool pointing back to an SF-01..SF-07 source)
- Blogs and commercial legal-advice websites
- Wikipedia and other general encyclopedias
- Social media
- Any arbitrary/unvetted webpage
- Any source family not explicitly registered in `config\authority_matrix.yaml` (including government-hosted sites not already named in Section 0 — government hosting alone does not confer authority under this policy)

This directly operationalizes the Master Reference's corpus-curation principle and this phase's explicit instruction not to treat search engines, blogs, commercial legal sites, Wikipedia, social media, or arbitrary webpages as authoritative unless the Master Reference explicitly permits them (it does not, for any of these).

## 7. Jurisdiction Separation Policy

`[OFFICIAL SOURCE]` Directly required by the Jurisdiction Firewall lock (`MASTER_REFERENCE_LOCK.md` Section E): *"India and international corpora should be separated at retrieval time, not merely mentioned in the prompt."* Phase 2 defines the corpus-side half of this contract (Phase 12 will implement retrieval-time enforcement):

**Jurisdiction values:** `INDIA`, `INTERNATIONAL`, `OTHER_UNSPECIFIED` (`[ENGINEERING RECOMMENDATION]` — defined for completeness/future source families; no current source family resolves to this value).

**Admission rules:** A document's jurisdiction is inherited from its source family (Section 2) and is never independently reassigned per document. A document whose jurisdiction cannot be determined is `OTHER_UNSPECIFIED` and cannot reach `ADMIT` (see `docs\PHASE_02_CORPUS_ADMISSION_POLICY.md`, rule A2/A3).

**Metadata rules:** Every provenance record carries an explicit `jurisdiction` field (`config\corpus_provenance_schema.yaml`); it is never left implicit or inferred from document content at admission time.

**Separation rules:** India-jurisdiction source families (SF-01–SF-05) and the international-jurisdiction source family (SF-06) are never merged into one collection or index. This repository currently has no indices at all (Phase 5+), so today "separation" means: the corpus-lock and provenance schema make jurisdiction a mandatory, explicit, per-document field so that no future phase can build a merged index without actively discarding this metadata.

**Conflict behavior:** A document whose declared jurisdiction does not match its source family's fixed jurisdiction (e.g., a WIPO document tagged `INDIA`) is rejected outright by the admission policy (`docs\PHASE_02_CORPUS_ADMISSION_POLICY.md` rule A3) — it is a data-integrity error, not a legal question, and is never silently corrected or guessed.

**Retrieval-time boundary expectation:** `[DEFERRED]` Actual retrieval-time index separation and leakage testing is Phase 12's responsibility (`docs\MASTER_REFERENCE_LOCK.md` Section G, CAP-12 in `config\acceptance_contract.yaml`). Phase 2 only guarantees the metadata exists for Phase 12 to enforce against.

## 8. Corpus Expansion Policy

`[OFFICIAL SOURCE]` per the Final Decision Lock's general principle (*"New technologies must earn their place through measurable evidence"*), applied here to source families specifically: no source family may be added to `config\authority_matrix.yaml` / `config\corpus_lock.yaml` without an explicit, reviewed update bumping `authority_matrix_version` / `lock_version`. No ingestion code, script, or future phase may silently register a new source family. Full policy text lives in `config\corpus_lock.yaml`'s `expansion_policy` field.

## 9. Limitations

`[OFFICIAL SOURCE]` / `[ASSUMPTION]`, consolidated per family:

- **SF-04/SF-05:** Must remain logically distinguished (Ayurveda Aahara food law vs. traditional drug regulation) per the Master Reference's explicit callout — never merged into one "Ayurvedic ingestible" bucket.
- **SF-07 (TKDL):** Authorized/public access only; full-database access is never assumed; jurisdiction assignment is `[ASSUMPTION]`; access URL is unknown and not invented (`[DEFERRED]`).
- **SF-08 (Bhashini):** Service terms and exact supported-language set must be verified before production use (Master Reference's own instruction); never treated as an evidence source.
- **All families:** Government/regulatory source URLs listed in Section 2 must be re-verified for currency before legal/production release (`MASTER_REFERENCE_LOCK.md` Section L) — Phase 2 records them as given in the Master Reference, it does not re-verify their live status (no network access performed in this phase).

## 10. Source/Evidence Audit (self-check for this document)

`[ENGINEERING RECOMMENDATION]`

- Every one of the 8 source families traces to the Master Reference's Authoritative Source Strategy table; none are invented.
- Every URL in Section 2 is copied verbatim from the Master Reference's "Research Sources & Provenance" section; none are invented; TKDL's absence from that list is preserved as an absence, not filled in.
- No inter-family legal hierarchy is asserted (Section 2's authority-tier note).
- No document, version, or publication date is claimed for any specific document — none exist yet.
- The contextual-source tier is explicitly empty, not populated with guessed entries.
