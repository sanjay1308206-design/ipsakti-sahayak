"""
Pytest configuration: make src/ importable as a top-level package root so
Phase 3+ tests can `import ingestion...` without path hacks in every file.
"""

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
