"""
MODULE: unit_tests/commit_guardian/_ge_134a_fixture.py
COVERS: GE-134a-1, GE-134a-1-i, GE-134a-2, GE-134a-3 (shared fixture module --
    carries no tests of its own)

GOAL: Shared builders and helpers for the GE-134a suite: a file's
    line-comment DECISION HISTORY block is left out of its measured length.
    Reuses _ge_127d_2_fixture.build_fixture_tree (a copy of the production
    modules in a temporary git repository -- no build.py, no POSIX flock) for
    every subprocess test, and adds:

    - loaders for the REAL production _file_size_ratchet.py (and for a
      disposable copy whose prefix constant has been rewritten);
    - the GE-134a-1 worked examples (80-line Python + 25-line ruled block,
      120-line JavaScript + 15-line unruled header block);
    - an INDEPENDENT counter implementing the rule as the GE-134a-3 statement
      publishes it, never importing production, so agreement with the
      quoted length is a genuine reproducibility proof (the same discipline
      _ge_127d_2_fixture.independent_count_content_lines follows).

TEST-WRITER DESIGN DECISIONS (python-coder must honour these names):

    1. PREFIX_CONSTANT_NAME = "DECISION_HISTORY_COMMENT_PREFIXES": the ONE
       module-level constant in _file_size_ratchet.py holding the
       line-comment prefixes, exactly ("#", "//", "--"). GE-134a-1's IT PO
       note requires one such constant but names none; this pins the name.
       It must be a plain module-level assignment (``NAME = (...)`` or
       ``NAME: tuple[str, ...] = (...)``) that the measurement AND the
       published rule both read at call time, so rewriting it in a copy of
       the module changes both.
    2. The published rule (describe_measurement_rule) states the history
       exclusion in a clause matched by ``HISTORY_EXCLUSION_RE``: the words
       "decision history" / "decision-history" in the same clause as
       "not counted" / "discard" / "left out".
    3. The GE-127d-2 category vocabulary gains the key "decision_history"
       (``parse_discard_categories_with_history``), extending
       _ge_127d_2_fixture.parse_discard_categories without editing the
       GE-127d-2 suite's own fixture.

DECISION HISTORY
- 2026-10-21 [test-writer/GE-134a-1..3]: Initial authoring.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_2_fixture as d2  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
RATCHET_SRC = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "_file_size_ratchet.py"
SHIPPED_CONFIG = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json"

PREFIX_CONSTANT_NAME = "DECISION_HISTORY_COMMENT_PREFIXES"
EXPECTED_PREFIXES: tuple[str, ...] = ("#", "//", "--")

# The line-comment prefix each shipped checked extension uses (GE-134a-1
# test_spec): '#' for .py and .sh, '//' for .js/.mjs/.ts/.tsx, '--' for .sql.
PREFIX_BY_EXTENSION: dict[str, str] = {
    ".py": "#",
    ".sh": "#",
    ".js": "//",
    ".mjs": "//",
    ".ts": "//",
    ".tsx": "//",
    ".sql": "--",
}

HISTORY_EXCLUSION_RE = re.compile(
    r"(?:not\s+count\w*|discard\w*|left\s+out)[^;]*decision[- ]history"
    r"|decision[- ]history[^;]*(?:not\s+count\w*|discard\w*|left\s+out)",
    re.IGNORECASE,
)

_RULE = "=" * 68


# ---------------------------------------------------------------------------
# Production module loaders
# ---------------------------------------------------------------------------


def _load_from(path: Path, module_name: str) -> ModuleType:
    """Import the module file at *path* under *module_name*, fresh."""
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build an import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_ratchet() -> ModuleType:
    """Load the REAL production templates/.../_file_size_ratchet.py."""
    return _load_from(RATCHET_SRC, "ge_134a_file_size_ratchet")


def prefix_constant(module: ModuleType) -> tuple[str, ...] | None:
    """Return the pinned prefix constant's value, or None when absent."""
    value = getattr(module, PREFIX_CONSTANT_NAME, None)
    return tuple(value) if value is not None else None


def load_ratchet_with_prefixes(tmp_dir: Path, prefixes: tuple[str, ...], tag: str) -> ModuleType | None:
    """Load a disposable copy of the ratchet whose prefix constant is *prefixes*.

    The constant's module-level assignment is located with ``ast`` and its
    whole line span replaced, so the copy reads *prefixes* wherever the real
    module reads the constant. Returns None when the constant does not exist
    (the caller turns that into an assertion failure, never an import error).
    """
    source = RATCHET_SRC.read_text(encoding="utf-8")
    span = None
    for node in ast.parse(source).body:
        targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
        if any(isinstance(t, ast.Name) and t.id == PREFIX_CONSTANT_NAME for t in targets):
            span = (node.lineno, node.end_lineno)
            break
    if span is None:
        return None
    lines = source.splitlines(keepends=True)
    replacement = f"{PREFIX_CONSTANT_NAME} = {prefixes!r}\n"
    rewritten = "".join(lines[: span[0] - 1]) + replacement + "".join(lines[span[1] :])
    dest = tmp_dir / f"_file_size_ratchet_{tag}.py"
    dest.write_text(rewritten, encoding="utf-8")
    return _load_from(dest, f"ge_134a_ratchet_copy_{tag}")


def measure_text(module: ModuleType, tmp_dir: Path, name: str, content: str) -> int:
    """Write *content* to ``tmp_dir/name`` and measure it with *module*."""
    path = tmp_dir / name
    path.write_text(content, encoding="utf-8", newline="\n")
    return module.measure_current_length(str(path))


# ---------------------------------------------------------------------------
# Content builders
# ---------------------------------------------------------------------------


def body_lines(count: int, prefix: str, code: str = "value_{i} = {i}") -> list[str]:
    """*count* measured lines: code, ordinary *prefix* comments and blanks.

    Every 10th line (index % 10 == 9) is blank and every index % 10 == 4 is
    an ordinary comment, so the last line of a multiple-of-ten body is blank.
    """
    lines = []
    for i in range(count):
        if i % 10 == 9:
            lines.append("")
        elif i % 10 == 4:
            lines.append(f"{prefix} ordinary comment {i}")
        else:
            lines.append(code.format(i=i))
    return lines


def history_entries(prefix: str, count: int, start: int = 0) -> list[str]:
    """*count* decision-history entry lines, alternating '- ' and '  ' forms."""
    entries = []
    for k in range(start, start + count):
        if k % 2 == 0:
            entries.append(f"{prefix} - 2026-10-{(k % 28) + 1:02d} [python-coder/GE-134a-1]: entry {k}")
        else:
            entries.append(f"{prefix}   continuation of entry {k - 1}")
    return entries


def ruled_python_block(entry_count: int = 22) -> list[str]:
    """A '#' block: rule line, heading, rule line, *entry_count* entries."""
    return [f"# {_RULE}", "# DECISION HISTORY", f"# {_RULE}", *history_entries("#", entry_count)]


def python_example(extra_code_lines: int = 0) -> str:
    """GE-134a-1's Python file: 80 measured lines + the 25-line ruled block.

    *extra_code_lines* code lines are added before the block, outside it.
    """
    extra = [f"extra_value_{i} = {i}" for i in range(extra_code_lines)]
    lines = [*extra, *body_lines(80, "#"), *ruled_python_block(22)]
    return "\n".join(lines) + "\n"


def javascript_example() -> str:
    """GE-134a-1's JavaScript file: a 15-line '//' header block (no rule
    lines: the heading plus 14 entries), then 120 measured lines."""
    block = ["// DECISION HISTORY", *history_entries("//", 14)]
    lines = [*block, *body_lines(120, "//", "const value_{i} = {i};")]
    return "\n".join(lines) + "\n"


def h_1_i_example(trailing: list[str] | None = None) -> str:
    """GE-134a-1-i's fixture: mention comment, LABEL line, 6-line block
    (heading, rule line, 4 entries), then x = 1 (plus *trailing* lines)."""
    lines = [
        "# see DECISION HISTORY below for why",
        'LABEL = "DECISION HISTORY"',
        "# DECISION HISTORY",
        f"# {_RULE}",
        *history_entries("#", 4),
        "x = 1",
        *(trailing or []),
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# The pre-change rule and the independent, published-rule counter
# ---------------------------------------------------------------------------


def _strip_regions(content: str) -> str:
    """Strip triple-quoted and block-comment regions (GE-127d-2's rule)."""
    text = d2._INDEPENDENT_TRIPLE_DOUBLE_RE.sub("", content)
    text = d2._INDEPENDENT_TRIPLE_SINGLE_RE.sub("", text)
    return d2._INDEPENDENT_BLOCK_COMMENT_RE.sub("", text)


def pre_change_count(content: str) -> int:
    """The measurement rule in force BEFORE GE-134a-1, re-coded here."""
    return len(_strip_regions(content).splitlines())


def _comment_text(line: str, prefix: str) -> str | None:
    """The text after *prefix* when *line* is a *prefix* comment, else None."""
    stripped = line.strip()
    return stripped[len(prefix) :].strip() if stripped.startswith(prefix) else None


def _heading_prefix(line: str) -> str | None:
    """The prefix of *line* when it is a whole-text DECISION HISTORY heading."""
    for prefix in EXPECTED_PREFIXES:
        if _comment_text(line, prefix) == "DECISION HISTORY":
            return prefix
    return None


def _is_rule_line(line: str, prefix: str) -> bool:
    text = _comment_text(line, prefix)
    return text is not None and bool(text) and set(text) == {"="}


def strip_history_blocks(lines: list[str]) -> list[str]:
    """Drop every line-comment DECISION HISTORY block, as the rule states it:
    a heading whose whole comment text is DECISION HISTORY, a '=' rule line
    directly above it, through the last consecutive same-prefix comment line.
    """
    kept: list[str] = []
    index = 0
    while index < len(lines):
        prefix = _heading_prefix(lines[index])
        if prefix is None:
            kept.append(lines[index])
            index += 1
            continue
        if kept and _is_rule_line(kept[-1], prefix):
            kept.pop()
        index += 1
        while index < len(lines) and _comment_text(lines[index], prefix) is not None:
            index += 1
    return kept


def independent_count(content: str) -> int:
    """The published post-change rule, coded independently of production."""
    return len(strip_history_blocks(_strip_regions(content).splitlines()))


def parse_discard_categories_with_history(measures_text: str | None) -> set[str]:
    """_ge_127d_2_fixture.parse_discard_categories plus "decision_history"."""
    categories = d2.parse_discard_categories(measures_text)
    if measures_text and HISTORY_EXCLUSION_RE.search(measures_text):
        categories.add("decision_history")
    return categories


def count_by_categories(content: str, categories: set[str]) -> int:
    """Re-derive a length from *content* driven only by parsed *categories*."""
    text = content
    if "triple_quoted" in categories:
        text = d2._INDEPENDENT_TRIPLE_DOUBLE_RE.sub("", text)
        text = d2._INDEPENDENT_TRIPLE_SINGLE_RE.sub("", text)
    if "block_comment" in categories:
        text = d2._INDEPENDENT_BLOCK_COMMENT_RE.sub("", text)
    lines = text.splitlines()
    if "decision_history" in categories:
        lines = strip_history_blocks(lines)
    return len(lines)


# ---------------------------------------------------------------------------
# Fixture-repository helpers (build_fixture_tree lives in _ge_127d_2_fixture)
# ---------------------------------------------------------------------------


def stage_and_check(root: Path, relative_path: str, content: str):
    """Write+stage *content* and run the fixture copy of check_file_size.py."""
    d2.write_and_stage(root, relative_path, content)
    return d2.run_check_file_size(root)


def commit_setup(root: Path, relative_path: str, content: str) -> None:
    """Land *content* at HEAD before any hook is installed (setup only)."""
    d2.write_and_stage(root, relative_path, content)
    result = d2.commit_bypassing_hook(root, f"setup {relative_path}")
    assert result.returncode == 0, f"setup commit failed: {result.stdout!r}{result.stderr!r}"
