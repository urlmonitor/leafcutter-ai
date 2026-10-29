"""
MODULE: scripts/evals/designer_eval/__init__.py
GOAL: The assertion kinds and the dispatch input of the test-designer eval set (TQ-200d-3).
BUSINESS CONTEXT: scripts/evals/ is at its folder file limit, so what only this agent's set uses
    lives in this sub-package instead of in sibling modules. The designer writes no test file: its
    output is the requirement record it edits, so its kinds read that record.
ARCHITECTURE: ``kinds`` holds the four record-reading assertion kinds (``KINDS``, spread into
    produced_tests_scoring.KINDS); ``dispatch`` builds the live input of a row from the real
    design_prepass.py report. ``produced_tests_mode`` reaches ``build_dispatch_input`` through the
    agent's ``input_builder`` config key.
"""

from __future__ import annotations

from designer_eval.dispatch import build_dispatch_input
from designer_eval.kinds import KINDS

__all__ = ["KINDS", "build_dispatch_input"]
