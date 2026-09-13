#!/usr/bin/env python3
"""
Phase 22 Step 22.7 — rollback target resolution and validation
(docs/PHASE_22_CICD_PRODUCTION_RELEASE.md "Rollback System").

`[ENGINEERING RECOMMENDATION]` Standalone, Python-standard-library-only,
mirroring `scripts/build_release_manifest.py`'s own precedent exactly
(no `requests`/`httpx`, no import from `src/` - importing anything from
`retrieval` cascades into `numpy`/`faiss`/`PyYAML`,
`requirements-render.txt`'s own header). This module does NOT duplicate
release-identity computation - it imports `REPO_ROOT` directly from
`build_release_manifest` rather than redefining it, and the actual
release-manifest generation/validation at a rollback target commit is
performed by invoking `build_release_manifest.py` itself (unchanged,
never a second manifest format) from `.github/workflows/rollback.yml`,
never reimplemented here. This module's own job is narrower and
DISTINCT from release-identity computation: given an ARBITRARY,
UNTRUSTED candidate SHA (an operator-typed `workflow_dispatch` input, or
the recorded `RENDER_LAST_KNOWN_GOOD_SHA` variable), decide whether it is
safe to check out and roll back to at all.

TWO RESPONSIBILITIES, DELIBERATELY KEPT SEPARATE:
1. `resolve_target_sha` - decides WHICH sha to use (explicit input wins,
   falling back to the recorded known-good SHA) - never a network call,
   never a git call, pure string logic.
2. `validate_target_sha` - decides whether that sha is SAFE to act on:
   exactly 40 lowercase hex characters, a real commit object in this
   repository, and reachable from the reference branch's history (never
   an arbitrary foreign/unmerged/hand-typed string that merely happens
   to look like a SHA). Every check runs in order and raises
   `RollbackTargetError` on the FIRST failure - never a partial "mostly
   valid" result.

FAIL-CLOSED (matches `build_release_manifest.py`'s own
`ReleaseManifestError` convention exactly): every failure here is a
raised exception, never a silently-returned `None`/`False` a caller could
forget to check.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from build_release_manifest import REPO_ROOT  # noqa: E402 - reused, never redefined

_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class RollbackTargetError(Exception):
    """Raised for any rollback-target resolution/validation failure - never swallowed, mirrors `ReleaseManifestError`."""


def resolve_target_sha(input_sha: Optional[str], known_good_sha: Optional[str]) -> str:
    """
    An explicitly-supplied `input_sha` always wins (an operator
    deliberately targeting a specific commit, e.g. rolling back further
    than one step). Only when it is empty/absent does this fall back to
    the recorded `RENDER_LAST_KNOWN_GOOD_SHA`. Raises if BOTH are empty -
    there is nothing to roll back to, and this must never silently invent
    a default (e.g. "HEAD", or the currently-deployed commit).
    """
    input_sha = (input_sha or "").strip()
    if input_sha:
        return input_sha

    known_good_sha = (known_good_sha or "").strip()
    if known_good_sha:
        return known_good_sha

    raise RollbackTargetError(
        "no target_sha was supplied and RENDER_LAST_KNOWN_GOOD_SHA is not set - "
        "there is nothing recorded to roll back to yet"
    )


def _run_git(args: list, repo_root: Path) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, check=True)
    except OSError as exc:
        raise RollbackTargetError(f"git command failed: git {' '.join(args)}: {exc}") from exc


def validate_sha_format(sha: str) -> None:
    if not isinstance(sha, str) or not _SHA_PATTERN.fullmatch(sha):
        raise RollbackTargetError(f"target_sha must be exactly 40 lowercase hexadecimal characters, got {sha!r}")


def validate_commit_exists(sha: str, repo_root: Path = REPO_ROOT) -> None:
    """Confirms `sha` is a real commit object in THIS repository's object database - never trusts the string merely because it is shaped like a SHA."""
    try:
        _run_git(["cat-file", "-e", f"{sha}^{{commit}}"], repo_root)
    except subprocess.CalledProcessError as exc:
        raise RollbackTargetError(f"target_sha {sha!r} is not a valid git commit in this repository") from exc


def validate_commit_reachable(sha: str, ref: str = "HEAD", repo_root: Path = REPO_ROOT) -> None:
    """
    Confirms `sha` is an ANCESTOR of `ref` (the branch that triggered this
    workflow, normally `main`'s tip) - rejects a commit that technically
    still exists in the object database (e.g. from an unmerged branch, or
    one left over from a rebase during git's reflog grace period) but was
    never part of this project's actual, released history.
    """
    try:
        _run_git(["merge-base", "--is-ancestor", sha, ref], repo_root)
    except subprocess.CalledProcessError as exc:
        raise RollbackTargetError(
            f"target_sha {sha!r} is not reachable from {ref!r} - refusing to roll back to an unrelated or unmerged commit"
        ) from exc


def validate_target_sha(sha: str, ref: str = "HEAD", repo_root: Path = REPO_ROOT) -> None:
    """Runs every validation check in order, raising on the first failure (docs "Never accept arbitrary unvalidated input")."""
    validate_sha_format(sha)
    validate_commit_exists(sha, repo_root=repo_root)
    validate_commit_reachable(sha, ref=ref, repo_root=repo_root)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 22 Step 22.7 rollback target resolution and validation.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve_parser = subparsers.add_parser("resolve", help="Resolve which SHA to roll back to (explicit input, or the recorded known-good SHA).")
    resolve_parser.add_argument("--input-sha", default="", help="An operator-supplied workflow_dispatch input (may be empty).")
    resolve_parser.add_argument("--known-good-sha", default="", help="The recorded RENDER_LAST_KNOWN_GOOD_SHA repository variable (may be empty).")

    validate_parser = subparsers.add_parser("validate", help="Validate a resolved target SHA before checking it out.")
    validate_parser.add_argument("--sha", required=True)
    validate_parser.add_argument("--ref", default="HEAD", help="Reference branch tip the target must be reachable from (default: HEAD).")

    args = parser.parse_args(argv)

    try:
        if args.command == "resolve":
            target_sha = resolve_target_sha(args.input_sha, args.known_good_sha)
            print(f"target_sha={target_sha}")
        else:
            validate_target_sha(args.sha, ref=args.ref)
            print(f"target_sha {args.sha} is VALID: correctly formatted, exists, and reachable from {args.ref}")
    except RollbackTargetError as exc:
        print(f"rollback target FAILED: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
