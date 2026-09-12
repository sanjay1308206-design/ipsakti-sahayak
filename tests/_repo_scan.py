"""
Shared repository-scan boundary for regression tests that walk the whole
repository tree (REPO_ROOT.rglob(...)) looking for stray/forbidden project
files (future-phase module names, leaked corpus documents, etc.).

Development-environment and build-metadata directories (the local
virtualenv, VCS metadata, dependency caches) are never part of the project
itself and must be excluded from every such scan - installed third-party
packages (e.g. transformers' bundled OCR model modules, torch's own
example HTML file) are not project files and must never trip a
future-phase-module or corpus-document-leakage guard. This was previously
duplicated ad hoc (only ".git" was excluded) in every regression file;
centralized here rather than repeating the same exclusion logic in each one.
"""

from __future__ import annotations

from pathlib import Path

# Intentionally narrow: only directories that hold installed packages, VCS
# metadata, or dependency/build caches - never an actual project directory.
# `src/`, `tests/`, `docs/`, `config/`, `frontend/` (its own source, as
# opposed to its `node_modules`/`dist`) all stay fully scanned.
EXCLUDED_ENV_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
    }
)


def is_repo_scan_excluded(path: Path) -> bool:
    """True if any component of `path` names a dev-environment/build-metadata directory."""
    return not EXCLUDED_ENV_DIR_NAMES.isdisjoint(path.parts)
