"""
MODULE: commit_guardian._file_size_measure.errors
GOAL: Carry the one distinct failure signal the shared file-size measure
    raises for content that cannot be read as its own language (GE-127d-3-ii).
BUSINESS CONTEXT: A file that cannot be split into the tokens of its language
    has no length. Counting it raw, or as zero, would be a second measurement
    rule with its own comment behaviour; this error lets every caller route
    the situation to INDETERMINATE instead.
ARCHITECTURE: Leaf module of the _file_size_measure sub-package, imported by
    every lexer and re-exported by the package root. It imports nothing from
    the rest of commit_guardian.
"""

from __future__ import annotations


class UnmeasurableContentError(Exception):
    """Content could not be tokenized as the language its extension names.

    Attributes:
        language: The language name (Python, JavaScript, TypeScript, SQL,
            shell) -- or the bare extension when no tokenizer is registered.
        detail: What the tokenizer rejected, without the language prefix.
        reason: The full sentence callers print after their own prefix.
    """

    def __init__(self, language: str, detail: str) -> None:
        self.language = language
        self.detail = detail
        self.reason = f"its content could not be read as {language} ({detail})"
        super().__init__(self.reason)


"""
DECISION HISTORY
========================================================================
- 2026-10-20 15:19 [python-coder]: Initial authoring. One distinct failure type for content a
  tokenizer rejects, so every caller routes it to INDETERMINATE (current content, previous blob,
  added lines) instead of a raw count or zero; its reason names the language so a refusal can say
  what could not be read. (#EPIC-FilesStayWorkable/GE-127d-3)
"""
