"""
MODULE: scripts.run_kernel
GOAL: Path-independent launcher: `<python> <repo>/scripts/run_kernel.py ...` is `python -m kernel ...`.
BUSINESS CONTEXT: The commands the kernel prints must run verbatim from any shell and directory;
    plain `python -m kernel` needs the kernel on the import path, which an unrelated shell lacks.
ARCHITECTURE: Puts the repository root (this script's parent directory's parent) first on
    sys.path so the `kernel` package imports with no PYTHONPATH; delegates to
    `kernel.adapters.cli.main`.

DECISION HISTORY:
    2026-10-02 Lives in scripts/, not the repo root: the check-root-files hook rejects new root
        files (owner decision). The root is therefore added to sys.path explicitly, because Python
        only puts this script's own directory (scripts/) there.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kernel.adapters.cli import main  # noqa: E402  (import needs the root on sys.path first)

if __name__ == "__main__":
    sys.exit(main())
