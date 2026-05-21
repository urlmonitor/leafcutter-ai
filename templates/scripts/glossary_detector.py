"""
glossary_detector.py — self-contained pattern detector for the GlossaryAutomation system.

Exports:
    detect_candidates(file_path: Path) -> list[Candidate]

CLI:
    python glossary_detector.py <file_or_dir>
    Prints JSON-lines of Candidate objects, one per line.

File-type-aware extraction rules:
    .py  — scan only docstrings (ast.Constant in ast.Expr nodes) and
            # comments (tokenize module). Skip all other nodes.
    .sql — scan only `-- ` line comments, `/* */` block comments, and
            `COMMENT ON ... IS '...'` statements. Ignore SQL identifiers.
    .md  — scan all text content, line by line.

Pattern set is loaded from glossary_patterns.json in the same directory.
If the file is absent, a built-in default set is used.
"""

from __future__ import annotations

import ast
import io
import json
import re
import sys
import tokenize
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

# ---------------------------------------------------------------------------
# Candidate dataclass
# ---------------------------------------------------------------------------


@dataclass
class Candidate:
    term: str
    file_path: str
    line_no: int
    context_window: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Default pattern set (used when glossary_patterns.json is absent)
# ---------------------------------------------------------------------------

_DEFAULT_PATTERNS: list[dict] = [
    {
        "name": "complete_suffix",
        "description": "snake_case identifiers ending with _complete (e.g. backfill_complete)",
        "regex": r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)*_complete)\b",
    },
    {
        "name": "sql_flag_assignment",
        "description": "SQL flag-style assignments: identifier='value'",
        "regex": r"\b([a-z][a-z0-9_]+)\s*=\s*'[^']*'",
    },
    {
        "name": "phase_number",
        "description": "phase followed by a digit, optionally with underscore (e.g. phase1, phase_2)",
        "regex": r"\b(phase_?\d+)\b",
    },
    {
        "name": "snake_case_multi_underscore",
        "description": "snake_case identifiers with 2+ underscores (e.g. candle_context_window)",
        "regex": r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+){2,})\b",
    },
    {
        "name": "all_caps_flag",
        "description": "ALL_CAPS_FLAGS (e.g. ENABLE_BACKFILL, MAX_RETRIES)",
        "regex": r"\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b",
    },
    {
        "name": "camel_case_prose",
        "description": "camelCase identifiers in prose (e.g. candleHorizon)",
        "regex": r"\b([a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)+)\b",
    },
]


def _load_patterns(script_dir: Path) -> list[dict]:
    """Load pattern set from glossary_patterns.json or fall back to defaults."""
    config_path = script_dir / "glossary_patterns.json"
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            patterns = data.get("patterns", data)
            if isinstance(patterns, list) and patterns:
                return patterns
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    return _DEFAULT_PATTERNS


def _compile_patterns(patterns: list[dict]) -> list[re.Pattern]:
    compiled = []
    for p in patterns:
        try:
            compiled.append(re.compile(p["regex"]))
        except re.error:
            pass
    return compiled


# ---------------------------------------------------------------------------
# Context window helper
# ---------------------------------------------------------------------------

_CONTEXT_RADIUS = 2  # lines before and after the match line


def _context_window(lines: list[str], match_line_idx: int) -> list[str]:
    """Return up to 5 lines centred on match_line_idx (0-based)."""
    start = max(0, match_line_idx - _CONTEXT_RADIUS)
    end = min(len(lines), match_line_idx + _CONTEXT_RADIUS + 1)
    return [l.rstrip("\n") for l in lines[start:end]]


# ---------------------------------------------------------------------------
# Extractors (return (text, 1-based line_no) pairs)
# ---------------------------------------------------------------------------

def _extract_py_text_regions(source: str) -> list[tuple[str, int]]:
    """
    Extract (text, line_no) pairs from Python source — docstrings and # comments only.

    Docstrings: walk the AST for ast.Expr(ast.Constant) nodes that are strings.
    Comments: use the tokenize module for COMMENT tokens.
    """
    regions: list[tuple[str, int]] = []

    # --- Docstrings via AST ---
    try:
        tree = ast.parse(source)
    except SyntaxError:
        tree = None

    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str):
                    docstring_text = node.value.value
                    line_no = node.lineno
                    # Add each line of the docstring individually (preserves line numbers)
                    for i, line in enumerate(docstring_text.splitlines()):
                        regions.append((line, line_no + i))

    # --- # comments via tokenize ---
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok_type, tok_string, tok_start, _, _ in tokens:
            if tok_type == tokenize.COMMENT:
                # Strip the leading '#' and any whitespace
                comment_text = tok_string.lstrip("#").strip()
                line_no = tok_start[0]
                regions.append((comment_text, line_no))
    except tokenize.TokenError:
        pass

    return regions


# SQL extraction regexes
_SQL_LINE_COMMENT = re.compile(r"--\s?(.*)")
_SQL_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_SQL_COMMENT_ON = re.compile(r"COMMENT\s+ON\s+\S+\s+\S+\s+IS\s+'([^']*)'", re.IGNORECASE | re.DOTALL)


def _extract_sql_text_regions(source: str) -> list[tuple[str, int]]:
    """Extract text regions from SQL source — comments and COMMENT ON statements only."""
    regions: list[tuple[str, int]] = []
    lines = source.splitlines()

    # -- line comments
    for i, line in enumerate(lines, start=1):
        m = _SQL_LINE_COMMENT.search(line)
        if m:
            regions.append((m.group(1).strip(), i))

    # /* block comments (track start line)
    for m in _SQL_BLOCK_COMMENT.finditer(source):
        text = m.group(0)[2:-2]  # strip /* */
        start_line = source[: m.start()].count("\n") + 1
        for j, line in enumerate(text.splitlines()):
            regions.append((line.strip(), start_line + j))

    # COMMENT ON ... IS '...'
    for m in _SQL_COMMENT_ON.finditer(source):
        text = m.group(1)
        start_line = source[: m.start()].count("\n") + 1
        for j, line in enumerate(text.splitlines()):
            regions.append((line.strip(), start_line + j))

    return regions


def _extract_md_text_regions(source: str) -> list[tuple[str, int]]:
    """Extract all text from a Markdown file (full-text scan, line by line)."""
    return [(line.rstrip("\n"), i + 1) for i, line in enumerate(source.splitlines())]


# ---------------------------------------------------------------------------
# Pattern matching against extracted regions
# ---------------------------------------------------------------------------

def _match_patterns(
    regions: list[tuple[str, int]],
    source_lines: list[str],
    compiled_patterns: list[re.Pattern],
    file_path: Path,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    seen: set[tuple[str, int]] = set()  # (term, line_no) dedup

    for text, line_no in regions:
        for pat in compiled_patterns:
            for match in pat.finditer(text):
                term = match.group(1) if pat.groups >= 1 else match.group(0)
                key = (term, line_no)
                if key in seen:
                    continue
                seen.add(key)
                ctx = _context_window(source_lines, line_no - 1)  # convert to 0-based
                candidates.append(
                    Candidate(
                        term=term,
                        file_path=str(file_path),
                        line_no=line_no,
                        context_window=ctx,
                    )
                )

    return candidates


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PATTERNS_CACHE: list[re.Pattern] | None = None
_SCRIPT_DIR = Path(__file__).parent


def _get_compiled_patterns() -> list[re.Pattern]:
    global _PATTERNS_CACHE
    if _PATTERNS_CACHE is None:
        raw = _load_patterns(_SCRIPT_DIR)
        _PATTERNS_CACHE = _compile_patterns(raw)
    return _PATTERNS_CACHE


def detect_candidates(file_path: Path) -> list[Candidate]:
    """
    Scan *file_path* and return Candidate records for detected jargon terms.

    Supports .py, .sql, .md only.  Returns [] for all other extensions.
    Also returns [] if the file cannot be read.
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix not in (".py", ".sql", ".md"):
        return []

    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    source_lines = source.splitlines()

    compiled = _get_compiled_patterns()

    if suffix == ".py":
        regions = _extract_py_text_regions(source)
    elif suffix == ".sql":
        regions = _extract_sql_text_regions(source)
    else:  # .md
        regions = _extract_md_text_regions(source)

    return _match_patterns(regions, source_lines, compiled, file_path)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _scan_path(target: Path) -> Iterator[Candidate]:
    if target.is_file():
        yield from detect_candidates(target)
    elif target.is_dir():
        for path in sorted(target.rglob("*")):
            if path.is_file() and path.suffix.lower() in (".py", ".sql", ".md"):
                yield from detect_candidates(path)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python glossary_detector.py <file_or_dir>", file=sys.stderr)
        sys.exit(1)

    target = Path(sys.argv[1])
    if not target.exists():
        print(f"Error: path does not exist: {target}", file=sys.stderr)
        sys.exit(1)

    for candidate in _scan_path(target):
        print(json.dumps(candidate.to_dict()))

    sys.exit(0)


if __name__ == "__main__":
    main()
