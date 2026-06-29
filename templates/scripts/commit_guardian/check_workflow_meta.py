"""
MODULE: check_workflow_meta
GOAL: Pre-commit hook that asserts every `export const meta = {...}` block in
    templates/workflows-js/*.js contains only pure string/array/object literals
    — no binary expressions, identifier references, call expressions, spread
    operators, or template-literal substitutions. Exits non-zero with a per-file
    message naming the offending pattern when any non-literal value is found.
BUSINESS CONTEXT: The `meta` block of a Claude Code Workflow script is parsed
    by the Workflow runtime at invocation time. Any non-literal value (e.g. a
    string concatenation `a + b`, a variable reference, or a template literal
    `${expr}`) causes a `meta must be a pure literal` runtime error that silently
    prevents finalization. This hook gates every commit to the templates/
    workflows-js/ tree so that the defect can never be reintroduced undetected.
ARCHITECTURE: Pure-Python scanner. Extracts the meta block between
    `export const meta = {` and the matching closing `};`, then strips string
    literal content to avoid false-positive matches inside quoted values, and
    finally applies pattern checks against the structural skeleton: template-
    literal substitutions (detected before stripping), string concatenation,
    spread operators, call expressions, and bare identifier references in value
    position. Does not require Node.js or any external dependency. Accepts file
    paths as positional CLI arguments; when none are given it queries git for
    staged templates/workflows-js/*.js files. Exit 0 = pass, exit 1 = violation.

Exit Codes:
    0 - All checked files have a pure-literal meta block (or no files to check)
    1 - One or more files contain a non-literal expression in their meta block

Usage:
    # Standalone scan of all workflow scripts:
    python scripts/commit_guardian/check_workflow_meta.py

    # Check specific files (pre-commit pass_filenames mode):
    python scripts/commit_guardian/check_workflow_meta.py templates/workflows-js/build-epic.js
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Meta-block extraction
# ---------------------------------------------------------------------------

_META_OPEN_RE = re.compile(r"export\s+const\s+meta\s*=\s*\{")


def _extract_meta_block(source: str) -> str | None:
    """Extract the text of the `export const meta = { ... }` block.

    Uses a brace-depth counter to find the matching closing brace. The
    returned text starts at the opening `{` and ends at the matching `}`.

    Args:
        source: Full JS source text.

    Returns:
        str: Raw meta block text (inclusive of braces), or None when not found.
    """
    match = _META_OPEN_RE.search(source)
    if not match:
        return None

    start = match.end() - 1  # position of the opening `{`
    depth = 0
    for i, ch in enumerate(source[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]

    # Unclosed block — return what we found so callers can still scan it.
    return source[start:]


# ---------------------------------------------------------------------------
# String-stripping helpers
# ---------------------------------------------------------------------------

# Matches a complete string literal (single-quoted, double-quoted, or backtick).
# For backtick strings, this matches the ENTIRE literal including any ${...}
# blocks so they are handled separately before stripping.
_SINGLE_QUOTED_RE = re.compile(r"'(?:[^'\\]|\\.)*'", re.DOTALL)
_DOUBLE_QUOTED_RE = re.compile(r'"(?:[^"\\]|\\.)*"', re.DOTALL)
# Backtick strings may span multiple lines.
_BACKTICK_RE = re.compile(r"`(?:[^`\\]|\\.)*`", re.DOTALL)


def _strip_string_content(text: str) -> str:
    """Replace the interior of every string literal with a placeholder.

    Replaces `"..."`, `'...'`, and `` `...` `` literals with `"S"` so that
    subsequent structural checks do not fire on content inside quoted strings.
    The replacement preserves the outer quote characters so the structural
    skeleton (`:`, `,`, `[`, `]`, `{`, `}`) is unchanged.

    Args:
        text: Raw JS text (typically the extracted meta block).

    Returns:
        str: Text with string interiors replaced by `"S"`.
    """
    # Order: backtick first (to avoid partial matches), then double, then single.
    result = _BACKTICK_RE.sub('"S"', text)
    result = _DOUBLE_QUOTED_RE.sub('"S"', result)
    result = _SINGLE_QUOTED_RE.sub('"S"', result)
    return result


# ---------------------------------------------------------------------------
# Non-literal pattern detectors
# ---------------------------------------------------------------------------

# Template literal substitution: `${...}` — must be checked on the RAW block
# (before string stripping) because the stripping will remove the backtick
# string entirely.
_TEMPLATE_SUBST_RE = re.compile(r"`[^`]*\$\{[^`]*`", re.DOTALL)

# String concatenation using + operator after stripping (catches `"S" + varName`
# or `varName + "S"`).
_STRING_CONCAT_RE = re.compile(r'(?:"S"|\w+)\s*\+\s*(?:"S"|\w)')

# Spread operator inside an object or array literal (after stripping).
_SPREAD_RE = re.compile(r"\.\.\.\s*[A-Za-z_$]")

# Call expression: an identifier followed immediately by `(` (after stripping).
# This intentionally matches function calls in value position.
_CALL_EXPR_RE = re.compile(r"\b([A-Za-z_$][A-Za-z0-9_$]*)\s*\(")

# Bare identifier reference in value position: `key: identName` where
# identName is not a JS keyword/literal, followed by `,`, newline, or `}`.
# Checked on the stripped skeleton.
_BARE_IDENT_RE = re.compile(
    r":\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*(?=[,\n\r}])"
)

# JS keywords and literals that are valid bare values (not identifier references).
_ALLOWED_BARE_IDENTS = frozenset(
    {"true", "false", "null", "undefined", "NaN", "Infinity"}
)

# Call expressions that are part of the JS literal syntax (none currently;
# add here if object-literal method shorthand needs to be exempted).
_ALLOWED_CALL_IDENTS: frozenset[str] = frozenset()


# ---------------------------------------------------------------------------
# Violation detection
# ---------------------------------------------------------------------------


def _violations_in_block(raw_block: str) -> list[str]:
    """Return a list of human-readable violation descriptions for *raw_block*.

    Checks the raw block first for template-literal substitutions (which must
    be detected before string stripping removes the backtick content), then
    strips string literals and checks the structural skeleton for concatenation,
    spread, call expressions, and bare identifier references.

    Args:
        raw_block: Raw text of the `export const meta = { ... }` block.

    Returns:
        list[str]: Zero or more short descriptions of non-literal expressions.
    """
    found: list[str] = []

    # -- Check 1: template-literal substitution (on raw text) --
    if _TEMPLATE_SUBST_RE.search(raw_block):
        found.append("template-literal substitution (${...} inside backticks)")
        # No need to check further for this category.

    # Strip string literals to get the structural skeleton.
    skeleton = _strip_string_content(raw_block)

    # -- Check 2: string concatenation --
    if _STRING_CONCAT_RE.search(skeleton):
        found.append("string concatenation (+)")

    # -- Check 3: spread operator --
    if _SPREAD_RE.search(skeleton):
        found.append("spread operator (...identifier)")

    # -- Check 4: call expressions --
    for call_match in _CALL_EXPR_RE.finditer(skeleton):
        ident = call_match.group(1)
        if ident not in _ALLOWED_CALL_IDENTS:
            found.append(f"call expression: {ident}(...)")
            break  # Report the first call; one violation is sufficient.

    # -- Check 5: bare identifier references --
    for ident_match in _BARE_IDENT_RE.finditer(skeleton):
        ident = ident_match.group(1)
        if ident not in _ALLOWED_BARE_IDENTS:
            found.append(f"bare identifier reference: {ident}")
            break  # Report the first bare ident; one violation is sufficient.

    return found


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def _read_file(filepath: str) -> str | None:
    """Read a JS file's text content, returning None on I/O error.

    Args:
        filepath: Path to the JS file.

    Returns:
        str: File content on success, None on failure.
    """
    try:
        return Path(filepath).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"Warning: cannot read {filepath}: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_staged_js_files() -> list[str]:
    """Return staged templates/workflows-js/*.js file paths from git.

    Returns:
        list[str]: Relative paths of staged JS workflow files. Empty on error.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Warning: git diff failed: {exc}", file=sys.stderr)
        return []

    return [
        f
        for f in result.stdout.strip().splitlines()
        if f.startswith("templates/workflows-js/") and f.endswith(".js")
    ]


def _scan_all_workflow_js(repo_root: Path) -> list[str]:
    """Return all *.js files under templates/workflows-js/ relative to *repo_root*.

    Used in standalone mode when no staged files are found.

    Args:
        repo_root: Repository root directory.

    Returns:
        list[str]: Relative paths to all workflow JS files.
    """
    workflow_dir = repo_root / "templates" / "workflows-js"
    if not workflow_dir.is_dir():
        return []
    return [
        str(p.relative_to(repo_root))
        for p in sorted(workflow_dir.glob("*.js"))
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the workflow-meta pure-literal check.

    Returns:
        int: 0 if all files pass, 1 if any violation is found.
    """
    repo_root = Path(__file__).resolve().parents[3]

    if len(sys.argv) > 1:
        candidates = sys.argv[1:]
    else:
        candidates = _get_staged_js_files()
        if not candidates:
            # Standalone mode: scan the full directory.
            candidates = _scan_all_workflow_js(repo_root)

    violations: dict[str, list[str]] = {}

    for filepath in candidates:
        # Accept both relative (from git) and absolute paths (from CLI/tests).
        path = Path(filepath)
        if not path.is_absolute():
            path = repo_root / filepath

        content = _read_file(str(path))
        if content is None:
            continue  # I/O warning already emitted; skip without flagging.

        block = _extract_meta_block(content)
        if block is None:
            # No meta block found — only flag if the file is in workflows-js/.
            if "workflows-js" in str(path):
                violations[filepath] = ["no `export const meta` block found"]
            continue

        issues = _violations_in_block(block)
        if issues:
            violations[filepath] = issues

    for file_path, issues in violations.items():
        for issue in issues:
            print(f"FAIL: {file_path} — {issue}")

    if violations:
        print(
            f"\ncheck_workflow_meta: {len(violations)} file(s) have non-literal "
            "values in their `meta` block.",
            file=sys.stderr,
        )
        print(
            "  FIX: Replace all non-literal expressions with pure string/array/object "
            "literals in the `export const meta = { ... }` block.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-24 [python-coder]: Initial implementation.
  Pure-Python scanner that extracts the `export const meta = {...}` block
  from each templates/workflows-js/*.js file, strips string literal content
  to avoid false positives inside quoted values, then checks the structural
  skeleton for: template-literal substitutions (before stripping), string
  concatenation (+), spread operators (...id), call expressions (id()), and
  bare identifier references (key: identName). String stripping uses three
  regex passes (backtick, double-quote, single-quote) that replace interiors
  with the placeholder "S". Registered in commit_guardian.json as
  check-workflow-meta, scoped to templates/workflows-js/*.js staged files.
  ADR-006 addendum documents the pure-literal meta contract as a package
  invariant.
  (EPIC-FinalizeFeatureHardening/02_workflow_meta_literal_gate.md)
====================================================================
"""
