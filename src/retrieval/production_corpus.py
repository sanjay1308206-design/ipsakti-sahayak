"""
LD-2 (Production Corpus & Retrieval): loads, integrity-verifies, and
exposes the one real, admitted SF-05 corpus document - "Food Safety and
Standards (Ayurveda Aahara) Regulations, 2022" - for retrieval.

SCOPE: originally (LD-2) this module was deliberately NOT wired into
`application.service.ApplicationService`/`api/dependencies.py`, proving
production retrieval independently before touching the query path (LD-2
master prompt, Step I). `sf05_evidence_pack_builder` below is shaped
exactly like `ApplicationService.evidence_pack_builder` (`Callable[[str],
EvidencePack]`) for exactly that reason. LD-3 (Production RAG Query Path)
has since connected it: `api/dependencies.py::get_evidence_pack_builder`
now returns `sf05_evidence_pack_builder` directly, unconditionally, and
`get_application_service` passes it into every real `ApplicationService`
it constructs - no change was needed in this file to do so, exactly as
designed. Nothing in this file changed for that wiring.

STRATEGY - "no second loader", extended from test code into production
code: the durable source of truth is exactly two files -

    data/manifest/SF-05/<document_id>.json   (tracked; provenance/hash)
    data/raw/SF-05/<document_id>.pdf         (tracked - see this LD-2's
                                               own narrow .gitignore
                                               exception)

Everything else - the normalized document, the 83 real chunks, and the
BM25 index - is deterministically REBUILT in-process, on every cold
start, through the exact same real, unmodified pipeline already used
elsewhere in this repository (ingestion.pipeline.ingest_bytes ->
chunking.chunker.chunk_document -> retrieval.index.build_index). The
convention that the gitignored data/normalized/, data/chunks/,
data/indexes/ JSON snapshots on disk are NEVER read back as a second,
potentially-stale loading path was already established by
tests/test_phase_23_3_sf05_chunking_and_bm25.py's own module docstring
("Phase 3/4 offer only a one-way serializer, never a dict-to-dataclass
loader") - this module keeps that convention, in production code, rather
than inventing a competing BM25-index-JSON loader.

WHY A TRACKED ARTIFACT, NOT SOMETHING ELSE (LD-2 Step B - verified
against current official Render documentation, not assumed):
  - https://render.com/docs/disks: persistent disks require a PAID plan;
    without one a web service's filesystem is fully ephemeral - "any
    changes you make to a service's local files are lost every time the
    service redeploys or restarts." This project's render.yaml is
    `plan: free` throughout (an explicit, documented COST LOCK) - a
    persistent disk is not an option.
  - https://render.com/docs/deploys: Render deploys "the most recent
    commit on your service's linked branch" (or an explicit commit) -
    i.e. ONLY git-committed content ever reaches the deployed
    filesystem. A file that is merely present on a developer's machine,
    gitignored or unstaged, never arrives.
  - Downloading the PDF at container startup was rejected: it would (a)
    contradict this project's own consistent "never downloads anything"
    principle (every ingestion-phase docstring in this repository says
    this), (b) need to re-run on every restart against an ephemeral
    filesystem with no caching benefit, and (c) introduce a new runtime
    network dependency and failure mode for zero benefit over simply
    committing 2.3 MB of already-integrity-verified PDF bytes.
  The only reproducible, Free-plan-compatible, zero-new-infrastructure
  strategy is therefore committing the raw PDF to git, exactly like
  `data/manifest/` already is by this repository's own pre-existing
  policy (see .gitignore's own note on Phase 2 Authority Matrix & Corpus
  Lock).

INTEGRITY (LD-2 Steps C/D) - `load_validated_sf05_index()` fails closed
(raises `ProductionCorpusIntegrityError`) rather than silently
substituting, skipping, or degrading, at every one of these layers:
  1. the manifest and raw PDF files must exist on disk;
  2. the manifest's own declared provenance must equal this module's
     pinned SF-05 identity below (document_id/source_family_id/
     jurisdiction/synthetic/content_hash) - proving this is literally
     the one, previously-admitted document, not merely A validly-shaped
     one (a manifest could be replaced with a different, still
     internally-consistent document otherwise);
  3. `ingestion.pipeline.ingest_bytes`'s own byte-for-byte SHA-256 check
     (never reimplemented here - reused verbatim) must pass, and
     admission against `config/authority_matrix.yaml` must pass;
  4. extraction must succeed and yield exactly the expected page count;
  5. chunking must yield exactly the expected chunk count, and every
     chunk's own provenance fields must match the pinned identity;
  6. the freshly-built BM25 index's own signature
     (`retrieval.identity.compute_index_signature`, a hash over its
     config + the exact ordered chunk_ids + the exact content_hashes)
     must equal the pinned, previously-verified signature - this one
     check transitively re-proves chunk identity/order/content are
     unchanged, without a separate per-chunk text comparison.
Every one of these was independently verified against the real,
admitted asset before being pinned here (see this phase's own LD-2
implementation report for the exact reconstruction run).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from chunking.chunker import chunk_document
from evidence.builder import build_evidence_pack
from evidence.models import EvidencePack
from ingestion.admission import load_authority_matrix
from ingestion.pipeline import ingest_bytes

from .index import build_index, query
from .models import Bm25Index, RetrievalResponse

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# --- SF-05 Corpus Lock (LD-2) ---------------------------------------------
# Pinned identity of the one document this module will ever serve. Any
# legitimate future re-admission (a new version, a superseding
# regulation) requires a deliberate, reviewed update to these constants -
# never an automatic/implicit acceptance of whatever happens to be on
# disk.
DOCUMENT_ID = "SF05-FSSAI-AYURVEDA-AAHARA-REGULATIONS-2022"
SOURCE_FAMILY_ID = "SF-05"
EXPECTED_JURISDICTION = "INDIA"
EXPECTED_SYNTHETIC = False
EXPECTED_CONTENT_HASH = "1ae8cfc632fad0a775316a84999a48adb6cf4b47d05bd4faa75f5190c511f699"
EXPECTED_PAGE_COUNT = 27
EXPECTED_CHUNK_COUNT = 83
# Read directly from the actual persisted data/indexes/SF-05/*.bm25.json
# artifact's own "signature" field (never assumed from a truncated
# value) - see this phase's implementation report for the exact
# inspection command used.
EXPECTED_BM25_SIGNATURE = "c75035ff9dde1e3f8afef907d5c15c2ae4b726c31dbaea423245440fbe716e6a"

MANIFEST_PATH = REPO_ROOT / "data" / "manifest" / SOURCE_FAMILY_ID / f"{DOCUMENT_ID}.json"
RAW_PDF_PATH = REPO_ROOT / "data" / "raw" / SOURCE_FAMILY_ID / f"{DOCUMENT_ID}.pdf"

DEFAULT_TOP_K = 5


class ProductionCorpusIntegrityError(RuntimeError):
    """
    Raised whenever the real SF-05 corpus/index cannot be located,
    reconstructed, or verified against its pinned identity above - the
    ONLY outcome for any such failure. Never a silent fallback to an
    empty/synthetic/partial corpus presented as ready.
    """


def _load_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        raise ProductionCorpusIntegrityError(f"SF-05 manifest not found: {MANIFEST_PATH}")
    try:
        provenance = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProductionCorpusIntegrityError(f"SF-05 manifest is corrupted (invalid JSON): {MANIFEST_PATH}") from exc
    if not isinstance(provenance, dict):
        raise ProductionCorpusIntegrityError(f"SF-05 manifest must contain a JSON object: {MANIFEST_PATH}")

    expected_fields = {
        "document_id": DOCUMENT_ID,
        "source_family_id": SOURCE_FAMILY_ID,
        "jurisdiction": EXPECTED_JURISDICTION,
        "synthetic": EXPECTED_SYNTHETIC,
        "content_hash": EXPECTED_CONTENT_HASH,
    }
    for field, expected in expected_fields.items():
        if provenance.get(field) != expected:
            raise ProductionCorpusIntegrityError(
                f"SF-05 manifest field {field!r} is {provenance.get(field)!r}, expected {expected!r} - this is "
                f"not the pinned, previously-admitted SF-05 document; refusing to load it"
            )
    return provenance


def _load_raw_bytes() -> bytes:
    if not RAW_PDF_PATH.is_file():
        raise ProductionCorpusIntegrityError(f"SF-05 raw source PDF not found: {RAW_PDF_PATH}")
    return RAW_PDF_PATH.read_bytes()


def _build_and_verify_index() -> Bm25Index:
    provenance = _load_manifest()
    data = _load_raw_bytes()
    authority_matrix = load_authority_matrix()

    result = ingest_bytes(data, provenance, ".pdf", authority_matrix)
    if result.pipeline_state != "EXTRACTION_SUCCESS":
        raise ProductionCorpusIntegrityError(
            f"SF-05 ingestion did not succeed: pipeline_state={result.pipeline_state!r}, "
            f"reason_codes={result.reason_codes!r} - refusing to serve a corpus that failed integrity/admission checks"
        )

    document = result.document
    if len(document.pages) != EXPECTED_PAGE_COUNT:
        raise ProductionCorpusIntegrityError(
            f"SF-05 extraction produced {len(document.pages)} pages, expected {EXPECTED_PAGE_COUNT}"
        )

    chunks = chunk_document(document).chunks
    if len(chunks) != EXPECTED_CHUNK_COUNT:
        raise ProductionCorpusIntegrityError(
            f"SF-05 chunking produced {len(chunks)} chunks, expected exactly {EXPECTED_CHUNK_COUNT}"
        )
    for chunk in chunks:
        actual = (chunk.document_id, chunk.source_family_id, chunk.jurisdiction, chunk.synthetic, chunk.content_hash)
        expected = (DOCUMENT_ID, SOURCE_FAMILY_ID, EXPECTED_JURISDICTION, EXPECTED_SYNTHETIC, EXPECTED_CONTENT_HASH)
        if actual != expected:
            raise ProductionCorpusIntegrityError(
                f"SF-05 chunk {chunk.chunk_id!r} carries unexpected provenance {actual!r}, expected {expected!r}"
            )

    index = build_index(chunks)
    if index.chunk_count != EXPECTED_CHUNK_COUNT:
        raise ProductionCorpusIntegrityError(
            f"SF-05 BM25 index chunk_count {index.chunk_count} does not match expected {EXPECTED_CHUNK_COUNT}"
        )
    if index.signature != EXPECTED_BM25_SIGNATURE:
        raise ProductionCorpusIntegrityError(
            f"SF-05 BM25 index signature {index.signature!r} does not match the pinned, previously-verified "
            f"signature {EXPECTED_BM25_SIGNATURE!r} - the corpus, chunking, or indexing logic has drifted; "
            f"refusing to serve an unverified index rather than presenting it as trustworthy"
        )

    return index


@lru_cache(maxsize=1)
def load_validated_sf05_index() -> Bm25Index:
    """
    The one production entry point for obtaining the real, verified SF-05
    BM25 index. Cached for the life of the process (mirrors
    `api/dependencies.py`'s own `get_backend_config`/
    `get_generation_provider` lazy-singleton convention) - the
    reconstruct-and-verify work in `_build_and_verify_index` runs at most
    once. A failed attempt is NOT cached (`lru_cache` never caches a
    raised exception), so every subsequent call re-attempts and
    re-reports the same failure honestly rather than freezing in a
    broken state.
    """
    return _build_and_verify_index()


def sf05_corpus_status() -> str:
    """
    Non-raising status probe: "VALIDATED" if the real corpus is loaded
    and verified, "UNAVAILABLE" otherwise. Never returns "VALIDATED"
    without every check in `_build_and_verify_index` having actually
    passed - there is no separate, weaker notion of "ready" here.
    """
    try:
        load_validated_sf05_index()
        return "VALIDATED"
    except ProductionCorpusIntegrityError:
        return "UNAVAILABLE"


def query_sf05(query_text: str, top_k: int = DEFAULT_TOP_K) -> RetrievalResponse:
    """Real BM25 retrieval (`retrieval.index.query`, unmodified) over the validated SF-05 index. Raises `ProductionCorpusIntegrityError` if the corpus itself is unavailable/invalid - never returns a response over an unverified index."""
    index = load_validated_sf05_index()
    return query(index, query_text, top_k=top_k)


def sf05_evidence_pack_builder(query_text: str) -> EvidencePack:
    """
    `Callable[[str], EvidencePack]` - exactly the shape
    `ApplicationService.evidence_pack_builder` already expects (see
    `application.service.default_evidence_pack_builder`), so a future,
    separately-authorized phase can wire this in as a drop-in
    replacement with no change to this function. NOT wired in by LD-2
    itself (see module docstring "SCOPE").

    Real BM25 results feed directly into the existing, unmodified
    `evidence.builder.build_evidence_pack` - no new EvidencePack
    construction path, no bypass of Phase 8/9.
    """
    response = query_sf05(query_text)
    return build_evidence_pack(response.results, query_text)
