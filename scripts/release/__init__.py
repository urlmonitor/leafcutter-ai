"""
MODULE: release
GOAL: Package marker for the leafcutter release scripts module.
BUSINESS CONTEXT: The release package provides compute_next_version.py for
    automated SemVer versioning derived from per-file changelog entries.
ARCHITECTURE: compute_next_version.py is the main entry point; this
    __init__.py is a pure package marker with no public symbols.
"""
