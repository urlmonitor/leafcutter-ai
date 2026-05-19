"""
MODULE: changelog
GOAL: Package marker for the leafcutter changelog scripts module.
BUSINESS CONTEXT: The changelog package provides the emit_entry helper for
    writing per-file changelog entries with YAML frontmatter. Used by both the
    changelog-agent (Call site 1) and epic-supervisor post-completion chain
    (Call site 2).
ARCHITECTURE: emit_entry.py is the single write-path entry point; this
    __init__.py is a pure package marker with no public symbols.
"""
