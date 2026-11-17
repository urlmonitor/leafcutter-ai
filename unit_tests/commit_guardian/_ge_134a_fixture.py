"""
MODULE: unit_tests/commit_guardian/_ge_134a_fixture.py
COVERS: GE-134a-1, GE-134a-1-i, GE-134a-2, GE-134a-3 (shared fixture module --
    carries no tests of its own)

GOAL: Shared builders and helpers for the GE-134a suite: a file's
    line-comment DECISION HISTORY block is left out of its measured length.
    Reuses _ge_127d_2_fixture.build_fixture_tree (a copy of the production
    modules in a temporary git repository -- no build.py, no POSIX flock) for
    every subprocess test, and adds:

    - a loader for the REAL production _file_size_ratchet.py;
    - the GE-134a-1 worked examples (80-line Python + 25-line ruled block,
      120-line JavaScript + 15-line unruled header block);
    - INDEPENDENT counters implementing the 2026-10-21 rule (GE-127d-3
      supersedes GE-134a: no comment, standalone string or blank line counts),
      never importing production.

DECISION HISTORY
- 2026-10-21 [test-writer/GE-134a-1..3]: Initial authoring.
- 2026-10-23 [test-writer/GE-127d-3]: Rewritten for GE-127d-3 superseding GE-134a; the
  history-block stripper, prefix-constant loader and category helpers were removed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_2_fixture as d2  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
RATCHET_SRC = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "_file_size_ratchet.py"
SHIPPED_CONFIG = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json"

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

_RULE = "=" * 68


# ---------------------------------------------------------------------------
# Production module loaders
# ---------------------------------------------------------------------------


def _load_from(path: Path, module_name: str) -> ModuleType:
    """Import the module file at *path* under *module_name*, fresh."""
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        message = f"cannot build an import spec for {path}"
        raise ImportError(message)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_ratchet() -> ModuleType:
    """Load the REAL production templates/.../_file_size_ratchet.py.

    The module imports its sibling ``_file_size_measure`` package (GE-127d-3), so the
    template directory must be importable the way a deployed layout makes it.
    """
    guardian_dir = str(RATCHET_SRC.parent)
    if guardian_dir not in sys.path:
        sys.path.insert(0, guardian_dir)
    return _load_from(RATCHET_SRC, "ge_134a_file_size_ratchet")


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


def independent_count(content: str) -> int:
    """The 2026-10-21 rule (GE-127d-3 supersedes GE-134a), coded independently of production.

    No comment of any style, no standalone string and no blank line counts; a line counts
    only if it holds a code token. Python goes through the stdlib tokenizer
    (``_ge_127d_2_fixture.independent_python_measure``); the other languages' content built
    here uses whole-line ``//`` / ``--`` / ``#`` comments only, so a non-blank line that does
    not start with a comment prefix is a code line.
    """
    return d2.independent_python_measure(content)


def line_rule_count(content: str) -> int:
    """Non-Python content built from whole-line comments, blanks and code lines only."""
    return sum(
        1 for ln in content.splitlines() if ln.strip() and not ln.strip().startswith(EXPECTED_PREFIXES)
    )


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
