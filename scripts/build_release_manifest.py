#!/usr/bin/env python3
"""
Phase 22 Step 22.4 — deterministic release-identity and release-artifact
manifest builder (docs/PHASE_22_CICD_PRODUCTION_RELEASE.md).

`[ENGINEERING RECOMMENDATION]` This is a standalone, Python-standard-library-only
BUILD-TIME TOOL, deliberately kept OUTSIDE `src/` and importing nothing from
it - `src/`'s own package `__init__.py` chain has already, twice, pulled in
unexpected heavyweight imports at Phase 20 time (see
`requirements-render.txt`'s own header: importing anything from `retrieval`
cascades into `numpy`/`faiss`/`PyYAML`). Keeping this script import-isolated
from `src/` means it can NEVER become part of, or be affected by, the
deployed application's own import graph, and needs no dependency beyond the
Python interpreter itself.

RELEASE IDENTITY (`[ENGINEERING RECOMMENDATION]`, docs Section "RELEASE ID
REQUIREMENTS"): the git commit SHA of `HEAD` - not invented here, but
REUSED from a mechanism that already exists and already IS a deterministic,
content-addressed, immutable identity for "this exact source revision"
(git's own object model). This is deliberately distinct from
`application.config.API_VERSION` ("v1", an HTTP API CONTRACT version,
Phase 17) - the two concepts are recorded separately in the manifest below
and the release identity is never derived from, or confused with, the API
version.

RELEASE ARTIFACT (`[ENGINEERING RECOMMENDATION]`, docs Section "RELEASE
ARTIFACT"): Render's own deployment model (docs/PHASE_20_DEPLOYMENT_ENGINEERING.md)
clones this repository itself at a target commit and runs its OWN build
commands (`pip install -r requirements-render.txt`, `npm ci && npm run
build`) - it never consumes a pre-built bundle or container image (Docker
is explicitly excluded, docs/PHASE_22_CICD_PRODUCTION_RELEASE.md Step
22.1). Given that reality, bundling a full copy of the source tree here
would be dead weight nothing downstream consumes. The release artifact
for THIS project is therefore a deterministic MANIFEST - never a
container image, never a re-bundled source tarball - naming the release
identity plus content-hashed integrity metadata for exactly the files
that determine what gets deployed: Phase 20's own deployment
configuration (`render.yaml`, `requirements-render.txt`, the version pin
files, the frontend's package manifest/lockfile) and the actual
application source trees (`src/`, `frontend/src`). This mirrors
`observability.backup`'s own `SnapshotManifest` convention directly
(a `content` block + one deterministic `manifest_hash`, wall-clock
`created_at` kept in a separate, non-hashed `manifest_metadata` block) -
never a second, incompatible hashing/manifest scheme.

REPRODUCIBILITY DISCLOSURE (`[ASSUMPTION]`, docs Section "REPRODUCIBILITY"):
every hash here depends only on file BYTES and relative paths - never
wall-clock time, absolute paths, random values, or filesystem enumeration
order (all file lists are sorted before hashing). This does NOT
guarantee byte-identical hashes across two machines whose `git` line-ending
configuration (`core.autocrlf`) differs, since that changes the actual
bytes git checks out to disk - an external constraint of git's own
checkout behavior, not something this script can or should silently
"fix" by re-normalizing line endings. Given identical bytes on disk
(the normal case: one CI runner, one checkout), generation is fully
deterministic and idempotent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

MANIFEST_SCHEMA_VERSION = "1.0.0"
ARTIFACT_SCHEMA = "ipsakti-release-manifest-v1"

# The exact set of Phase 20 deployment-configuration files that determine
# what actually gets deployed (docs/PHASE_20_DEPLOYMENT_ENGINEERING.md) -
# never a heuristic "everything at repo root" scan.
DEPLOYMENT_CONFIG_FILES = (
    "render.yaml",
    "requirements-render.txt",
    ".python-version",
    "frontend/.node-version",
    "frontend/package.json",
    "frontend/package-lock.json",
)

# Application source trees actually consumed at deploy time (backend
# `src/`, frontend `frontend/src`) - never `tests/`, `.venv/`,
# `node_modules/`, or any build/cache output.
APP_SOURCE_DIRECTORIES = ("src", "frontend/src")

# Defensive, belt-and-suspenders exclusion for stray local artifacts that
# must never influence a reproducible hash even if present on disk
# (mirrors this project's own .gitignore Python/cache sections).
_EXCLUDED_NAMES = {"__pycache__", ".DS_Store", "Thumbs.db"}
_EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


class ReleaseManifestError(Exception):
    """Raised for a genuine build-time failure (e.g. git unavailable) - never swallowed."""


def _run_git(args: list) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReleaseManifestError(f"git command failed: git {' '.join(args)}: {exc}") from exc
    return result.stdout.strip()


def compute_release_identity() -> dict:
    """
    Returns `{"release_id": <full 40-char git commit SHA of HEAD>,
    "source_tree_clean": bool}`. `source_tree_clean` is False whenever
    `git status --porcelain` reports ANY uncommitted change (staged,
    unstaged, or untracked) - never used to derive `release_id` itself
    (a dirty tree does not change the identity of the last real commit),
    only recorded so nobody mistakes an artifact built from a dirty tree
    for one that exactly, immutably matches its named commit.
    """
    commit_sha = _run_git(["rev-parse", "HEAD"])
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ReleaseManifestError(f"unexpected git rev-parse HEAD output: {commit_sha!r}")
    dirty_output = _run_git(["status", "--porcelain"])
    return {"release_id": commit_sha, "source_tree_clean": dirty_output == ""}


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _iter_source_files(directory: Path):
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix in _EXCLUDED_SUFFIXES:
            continue
        if _EXCLUDED_NAMES & set(path.parts):
            continue
        yield path


def hash_deployment_config_files() -> list:
    """
    Per-file integrity record for every Phase 20 deployment-configuration
    file - raises `ReleaseManifestError` if one is missing, rather than
    silently omitting it (a release manifest that pretends a missing
    deployment file doesn't matter would be dishonest, not deterministic).
    """
    records = []
    for relative_path in DEPLOYMENT_CONFIG_FILES:
        full_path = REPO_ROOT / relative_path
        if not full_path.is_file():
            raise ReleaseManifestError(f"required deployment configuration file is missing: {relative_path}")
        records.append(
            {
                "relative_path": relative_path,
                "content_hash": hash_file(full_path),
                "size_bytes": full_path.stat().st_size,
            }
        )
    return records


def collect_app_content_hash(directory: Path) -> dict:
    """
    Deterministic aggregate integrity hash over every file in `directory`
    - sorted relative POSIX paths, content-only (never mtime/order),
    mirroring `observability.backup`'s own "sha256 over sorted canonical
    fields" convention. Returns `{"content_hash": ..., "file_count": ...}`;
    `content_hash` is `None` (never a fabricated placeholder) if the
    directory does not exist or contains zero files.
    """
    if not directory.is_dir():
        return {"content_hash": None, "file_count": 0}

    entries = []
    for file_path in _iter_source_files(directory):
        relative = file_path.relative_to(directory).as_posix()
        entries.append(f"{relative}:{hash_file(file_path)}")

    if not entries:
        return {"content_hash": None, "file_count": 0}

    canonical = "|".join(["app-content-v1", *entries])
    return {"content_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(), "file_count": len(entries)}


def _extract_api_contract_version() -> Optional[str]:
    """
    Reads `application.config.API_VERSION`'s literal string value by
    TEXT INSPECTION only - never `import`s `src/application/config`,
    since importing anything from `src/` risks pulling in its package
    `__init__.py` chain (the exact hazard `requirements-render.txt`'s
    own header documents). Recorded purely as informational/traceability
    metadata - never used to compute `release_id`.
    """
    config_path = REPO_ROOT / "src" / "application" / "config.py"
    if not config_path.is_file():
        return None
    match = re.search(r'^API_VERSION\s*=\s*"([^"]+)"', config_path.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def build_manifest_content(*, release_id: Optional[str] = None, source_tree_clean: Optional[bool] = None) -> dict:
    """
    Builds the deterministic `content` block (never includes wall-clock
    time). `release_id`/`source_tree_clean` may be injected directly -
    the only mechanism this module offers for deterministic testing of
    otherwise git-state-dependent fields; real callers (main()) always
    derive them from `compute_release_identity()`.
    """
    if release_id is None or source_tree_clean is None:
        identity = compute_release_identity()
        release_id = identity["release_id"] if release_id is None else release_id
        source_tree_clean = identity["source_tree_clean"] if source_tree_clean is None else source_tree_clean

    backend = collect_app_content_hash(REPO_ROOT / "src")
    frontend = collect_app_content_hash(REPO_ROOT / "frontend" / "src")

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "artifact_schema": ARTIFACT_SCHEMA,
        "release_id": release_id,
        "source_tree_clean": source_tree_clean,
        "api_contract_version_reference": _extract_api_contract_version(),
        "deployment_config_files": sorted(hash_deployment_config_files(), key=lambda r: r["relative_path"]),
        "backend_app_content_hash": backend["content_hash"],
        "backend_app_file_count": backend["file_count"],
        "frontend_app_content_hash": frontend["content_hash"],
        "frontend_app_file_count": frontend["file_count"],
    }


def compute_manifest_hash(content: dict) -> str:
    canonical_json = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def build_release_manifest(*, created_at: Optional[str] = None, release_id: Optional[str] = None, source_tree_clean: Optional[bool] = None) -> dict:
    """
    The single top-level entry point. Returns the full manifest payload
    (`{"content": {...}, "manifest_hash": ..., "manifest_metadata": {...}}`,
    the exact `observability.backup` snapshot-manifest shape) - never
    writes to disk itself (see `write_manifest`/`main`).
    """
    content = build_manifest_content(release_id=release_id, source_tree_clean=source_tree_clean)
    manifest_hash = compute_manifest_hash(content)
    payload = {"content": content, "manifest_hash": manifest_hash}
    if created_at is not None:
        payload["manifest_metadata"] = {"created_at": created_at}
    return payload


def write_manifest(manifest: dict, output_path: Path) -> None:
    output_path.write_text(
        json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Phase 22 deterministic release manifest.")
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "release_manifest.json"),
        help="Path to write the manifest JSON to (default: release_manifest.json at the repository root).",
    )
    parser.add_argument(
        "--created-at",
        default=None,
        help="ISO-8601 timestamp to record as build metadata (default: current UTC time). Never part of manifest_hash.",
    )
    args = parser.parse_args(argv)

    created_at = args.created_at
    if created_at is None:
        from datetime import datetime, timezone

        created_at = datetime.now(timezone.utc).isoformat()

    try:
        manifest = build_release_manifest(created_at=created_at)
    except ReleaseManifestError as exc:
        print(f"release manifest generation FAILED: {exc}", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    write_manifest(manifest, output_path)

    print(f"release_id={manifest['content']['release_id']}")
    print(f"source_tree_clean={manifest['content']['source_tree_clean']}")
    print(f"manifest_hash={manifest['manifest_hash']}")
    print(f"written to: {output_path}")
    if not manifest["content"]["source_tree_clean"]:
        print(
            "WARNING: source tree has uncommitted changes - this manifest's release_id "
            "names the last real commit, NOT the exact (uncommitted) state that was hashed.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
