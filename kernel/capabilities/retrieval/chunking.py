"""
MODULE: kernel.capabilities.retrieval.chunking
GOAL: Split a text file into sections (Markdown headings, YAML or JSON top-level keys, Python
    top-level classes and functions) and cut a bounded excerpt from one section.
BUSINESS CONTEXT: One densest window per file hid the parts of long documents that carry the
    answer (an ADR's Alternatives section, a design part's decisions list) and started excerpts
    mid-table. A section is the unit a reader would cite, so its heading path becomes part of the
    locator (Rev 3 section 10.3: every result carries its location and truncation).
ARCHITECTURE: Pure functions over text and lines; no IO. `split_sections` returns None for formats
    without structure so the caller falls back to the old line window. Section ends are exclusive
    0-based line indexes. `cut_at_boundary` lives here so every excerpt (section, window,
    explicit locator, request budget) is cut the same way.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass

from kernel.config import RetrievalConfig

_SENTENCE_END = re.compile(r"[.!?](?=\s)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_YAML_KEY = re.compile(r"""^(?![-#\s])(?:"([^"]+)"|'([^']+)'|([^\s:#][^:#]*?))\s*:(?:\s|$)""")
_JSON_KEY = re.compile(r'^(\s+)"((?:[^"\\]|\\.)*)"\s*:')
MARKDOWN_SUFFIXES = (".md", ".markdown")
YAML_SUFFIXES = (".yaml", ".yml")
MAX_TITLE_CHARS = 60


@dataclass(frozen=True)
class Section:
    """A line range of one file with the label naming it (None for an unlabelled preamble)."""

    start: int
    end: int
    label: str | None = None
    level: int = 0


def cut_at_boundary(text: str, cap: int) -> str:
    """Return text cut to at most `cap` chars, at a line end, else a sentence end, else a word.

    The cut never goes below half the cap (a tiny excerpt would say nothing); the caller still
    marks the result as truncated.
    """
    if len(text) <= cap:
        return text
    window, floor = text[:cap], cap // 2
    line = window.rfind("\n")
    if line >= floor:
        return window[:line]
    sentence = max((m.end() for m in _SENTENCE_END.finditer(window)), default=0)
    if sentence >= floor:
        return window[:sentence]
    word = window.rfind(" ")
    return window[:word] if word >= floor else window


def best_window(lines: list[str], terms: list[str], context: int) -> tuple[int, int, int]:
    """Return (start, end, hits): the line window with the most hits (end exclusive)."""
    lowered = [line.lower() for line in lines]
    hit_lines = [i for i, line in enumerate(lowered) if any(t in line for t in terms)]
    if not hit_lines:
        return 0, 0, 0
    best = max(hit_lines, key=lambda i: sum(
        lowered[j].count(t) for j in range(max(0, i - context), min(len(lines), i + context + 1))
        for t in terms))
    start, end = max(0, best - context), min(len(lines), best + context + 1)
    hits = sum(lowered[j].count(t) for j in range(len(lines)) for t in terms)
    return start, end, hits


def markdown_headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """Return (line index, level, title) for every heading outside fenced code blocks."""
    found: list[tuple[int, int, str]] = []
    fenced = False
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and (match := _HEADING.match(line)):
            title = match.group(2).rstrip("#").strip()
            if title:
                found.append((index, len(match.group(1)), title))
    return found


def _merge_tiny(sections: list[Section], lines: list[str]) -> list[Section]:
    """Fold a heading with no body of its own into the next section (it only names a child)."""
    merged: list[Section] = []
    carry: int | None = None
    for position, sec in enumerate(sections):
        start = sec.start if carry is None else carry
        body = [x for x in lines[sec.start + (1 if sec.label else 0):sec.end] if x.strip()]
        if sec.label and not body and position < len(sections) - 1:
            carry = start
            continue
        merged.append(Section(start, sec.end, sec.label, sec.level))
        carry = None
    return merged


def _heading_path(stack: list[tuple[int, str]]) -> str:
    """Return `§Parent > Child`; the document's own title is dropped and long titles shortened."""
    shown = stack[1:] if len(stack) > 1 and stack[0][0] == 1 else stack
    return "§" + " > ".join(t if len(t) <= MAX_TITLE_CHARS else t[:MAX_TITLE_CHARS - 1] + "…"
                            for _, t in shown)


def _markdown_sections(lines: list[str]) -> list[Section] | None:
    """Split on headings; the label is the heading path (`§Parent > Child`)."""
    heads = markdown_headings(lines)
    if not heads:
        return None
    sections: list[Section] = []
    if heads[0][0] > 0 and any(x.strip() for x in lines[:heads[0][0]]):
        sections.append(Section(0, heads[0][0]))
    stack: list[tuple[int, str]] = []
    for position, (index, level, title) in enumerate(heads):
        end = heads[position + 1][0] if position + 1 < len(heads) else len(lines)
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        sections.append(Section(index, end, _heading_path(stack), level))
    return _merge_tiny(sections, lines)


def _keyed(starts: list[tuple[int, str]], total: int) -> list[Section] | None:
    """Sections from (line, key) starts; the first one also owns any preamble lines."""
    if len(starts) < 2:
        return None
    return [Section(0 if n == 0 else line, starts[n + 1][0] if n + 1 < len(starts) else total,
                    key) for n, (line, key) in enumerate(starts)]


def _yaml_sections(lines: list[str]) -> list[Section] | None:
    """Split a YAML document on its top-level keys."""
    starts = []
    for index, line in enumerate(lines):
        match = _YAML_KEY.match(line)
        if match:
            starts.append((index, match.group(1) or match.group(2) or match.group(3).strip()))
    return _keyed(starts, len(lines))


def _json_sections(text: str, lines: list[str]) -> list[Section] | None:
    """Split a pretty-printed JSON object on its top-level keys (else None)."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    indent: int | None = None
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = _JSON_KEY.match(line)
        if match is None:
            continue
        indent = len(match.group(1)) if indent is None else indent
        if len(match.group(1)) == indent:
            starts.append((index, match.group(2)))
    return _keyed(starts, len(lines)) if len(starts) == len(data) else None


def _def_span(node: ast.stmt) -> tuple[int, int, str] | None:
    """Return (start, end, label) of a top-level class or function node, else None."""
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return None
    start = min([node.lineno, *(d.lineno for d in node.decorator_list)]) - 1
    kind = "class" if isinstance(node, ast.ClassDef) else "def"
    return start, node.end_lineno or node.lineno, f"{kind} {node.name}"


def _python_sections(text: str, lines: list[str]) -> list[Section] | None:
    """Split on top-level classes and functions; code between them is `module level`."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    spans = [s for s in (_def_span(n) for n in tree.body) if s is not None]
    if not spans:
        return None
    sections: list[Section] = []
    cursor = 0
    for start, end, label in [*spans, (len(lines), len(lines), "")]:
        if start > cursor and any(x.strip() for x in lines[cursor:start]):
            sections.append(Section(cursor, start, "module level"))
        if label:
            sections.append(Section(start, end, label))
        cursor = max(cursor, end)
    return sections


def split_sections(rel: str, text: str, lines: list[str]) -> list[Section] | None:
    """Return the file's sections, or None when its format has no structure to split on."""
    suffix = rel.lower().rsplit(".", 1)[-1] if "." in rel else ""
    dotted = f".{suffix}"
    if dotted in MARKDOWN_SUFFIXES:
        return _markdown_sections(lines)
    if dotted in YAML_SUFFIXES:
        return _yaml_sections(lines)
    if dotted == ".json":
        return _json_sections(text, lines)
    if dotted == ".py":
        return _python_sections(text, lines)
    return None


def find_heading(lines: list[str], fragment: str) -> Section | None:
    """Return the Markdown section whose heading matches `fragment` (with its sub-sections).

    An exact (case-insensitive, `§` and `#` ignored) title match beats a prefix match, which
    beats a substring match; the first heading wins within a tier.
    """
    wanted = fragment.lstrip("§# ").strip().lower()
    heads = markdown_headings(lines)
    if not wanted:
        return None
    for tier in (lambda t: t == wanted, lambda t: t.startswith(wanted), lambda t: wanted in t):
        for position, (index, level, title) in enumerate(heads):
            if tier(title.lower()):
                end = next((i for i, lvl, _ in heads[position + 1:] if lvl <= level), len(lines))
                return Section(index, end, f"§{title}", level)
    return None


def find_symbol(text: str, name: str) -> Section | None:
    """Return the span of a Python class or function (`Name` or `Class.method`), else None."""
    try:
        body: list[ast.stmt] = ast.parse(text).body
    except (SyntaxError, ValueError):
        return None
    found: Section | None = None
    for part in name.split("."):
        match = next((n for n in body if _def_span(n) and getattr(n, "name", None) == part), None)
        span = _def_span(match) if match is not None else None
        if match is None or span is None:
            return None
        found = Section(span[0], span[1], span[2].split(" ")[0] + f" {name}")
        body = list(getattr(match, "body", []))
    return found


def section_excerpt(lines: list[str], sec: Section, terms: list[str], cfg: RetrievalConfig
                    ) -> tuple[int, int, str, bool]:
    """Return (start, end, text, truncated) for one section within `max_excerpt_chars`.

    A section that fits is returned whole (so it starts at its heading). A longer one starts at
    its beginning unless the densest term window lies beyond what fits, then at that window.
    """
    cap, block = cfg.max_excerpt_chars, lines[sec.start:sec.end]
    if len("\n".join(block)) <= cap:
        return sec.start, sec.end, "\n".join(block), False
    fit, used = 0, 0
    for line in block:
        if used + len(line) + 1 > cap and fit:
            break
        used, fit = used + len(line) + 1, fit + 1
    start, end = 0, fit
    window_start, window_end, hits = best_window(block, terms, cfg.excerpt_context_lines)
    if hits and window_start >= fit:
        start, end = window_start, window_end
    body = cut_at_boundary("\n".join(block[start:end]), cap)
    return sec.start + start, sec.start + end, body, True


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Sections replace the one-window-per-file read: Markdown by heading
#   path, YAML/JSON by top-level key, Python by top-level def or class; other formats keep the
#   old window. A heading with no body of its own is folded into the next section so a parent
#   such as "Alternatives" is read together with its first child. (#KernelV01/B)
# ====================================================================
