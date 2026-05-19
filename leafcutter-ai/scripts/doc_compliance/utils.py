"""
MODULE: utils
GOAL: Provide shared output utilities (safe_print) for the doc_compliance package.
BUSINESS CONTEXT: Windows terminals may not support Unicode; a safe fallback prevents crashes on all platforms.
ARCHITECTURE: Not needed.
"""
import sys

def safe_print(msg: str) -> None:
    """Print with fallback for terminals that cannot encode Unicode (e.g. Windows cp1252).

    Args:
        msg: The string to print.
    """
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-04 19:00 [Antigravity]: Initial creation as part of the doc_compliance_scanner (#EPIC-LeafcutterMVP/01)
  modularization. Extracted safe_print helper to prevent Windows cp1252 UnicodeEncodeError.
====================================================================
"""
