"""
MODULE: check_agent_verification_consistency
GOAL: Pre-commit hook that blocks commits staging an agent template whose
    frontmatter declares requires_verification: true but lists no edit-capable
    tool (Edit or Write).
BUSINESS CONTEXT: An agent that declares requires_verification: true commits
    to verifying the changes it makes. An agent whose tool list contains only
    read-and-inspect tools (e.g. Read, Bash) cannot perform that verification —
    it has no ability to create or modify files. Committing such an incoherent
    template leads to runtime failures that are difficult to diagnose.  This hook
    catches the contradiction at commit time and names both fixes so the author
    can resolve it before the offending template reaches the main branch.
ARCHITECTURE: Standalone script (no leafcutter-internal imports). Scans STAGED
    templates/agents/*.md files by file identity only (git diff --cached
    --name-only). For each staged agent template, reads its content via
    _read_staged_file() (patchable for unit tests) and parses YAML frontmatter.
    If requires_verification is true AND tools contains neither Edit nor Write,
    the template is flagged as an offender. On any offender, exits non-zero
    fail-closed with a block message naming every offending path and stating both
    fixes. Parse errors are treated fail-open (exit 0 + WARNING) per GE-116a-1-iii.
    Trigger pattern: ^templates/agents/.*\\.md$ — file identity only, no content
    grep of unrelated files. Designed to complete well under 1s for a typical
    staged set.
"""

from __future__ import annotations

import subprocess
import sys

import yaml

_AGENT_TEMPLATE_PREFIX = "templates/agents/"
_EDIT_CAPABLE_TOOLS: frozenset[str] = frozenset({"Edit", "Write"})
_HOOK_TAG = "[check-agent-verification-consistency]"


def _get_staged_files() -> list[str]:
    """Return the list of staged file paths from git.

    Returns:
        List of staged file path strings relative to the repo root.
        Returns an empty list when git diff fails.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACRM"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        # OSError covers a missing/unexecutable git binary (FileNotFoundError,
        # PermissionError). Fail open: an unreadable index must never hard-block.
        print(f"{_HOOK_TAG} WARNING: git diff failed: {exc}", file=sys.stderr)
        return []
    return result.stdout.strip().splitlines()


def _read_staged_file(path: str) -> str:
    """Read the staged content of a file from the git index.

    Reads via ``git show :0:<path>`` (the staged blob) so that partial-staging
    scenarios (``git add -p``) inspect the staged version, never the working-tree
    version — this is what makes the staged-only guarantee (GE-116c-3) hold.
    Deliberately does NOT fall back to a working-tree disk read: doing so would
    let a contradiction that was fixed only in the working tree (not re-staged)
    slip the committed blob past the guard. On any failure the file is treated as
    uninspectable and skipped fail-open (empty string), never hard-blocked.

    Args:
        path: Repo-root-relative path to the staged file.

    Returns:
        The staged blob content as a UTF-8 string, or an empty string on error
        (caller skips empty content as fail-open).
    """
    try:
        result = subprocess.run(
            ["git", "show", f":0:{path}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        # OSError covers a missing/unexecutable git binary. Fail open.
        print(
            f"{_HOOK_TAG} WARNING: git show :0:{path} failed: {exc}; "
            "skipping (fail-open).",
            file=sys.stderr,
        )
        return ""

    if result.returncode != 0:
        print(
            f"{_HOOK_TAG} WARNING: {path} not readable from the index "
            f"(git show exit {result.returncode}); skipping (fail-open).",
            file=sys.stderr,
        )
        return ""
    return result.stdout


def _parse_frontmatter(content: str) -> dict | None:
    """Parse YAML frontmatter from a markdown file.

    Extracts the YAML block between the first two ``---`` delimiters and
    returns the parsed mapping.  Returns ``None`` on any parse error so the
    caller can apply the fail-open policy (GE-116a-1-iii).

    Args:
        content: Full text content of the markdown file.

    Returns:
        Parsed frontmatter as a ``dict``, or ``None`` when the content has no
        recognisable YAML frontmatter block or the YAML is malformed.
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    end_idx: int | None = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None

    fm_text = "\n".join(lines[1:end_idx])
    try:
        parsed = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None
    return parsed


def _is_verification_required(value: object) -> bool:
    """Interpret a frontmatter ``requires_verification`` value as a boolean.

    Handles bare YAML booleans (``true``/``false`` parse to ``bool``), quoted
    scalars that parse to strings (``"false"`` must be falsy, not truthy by
    non-emptiness), numeric values, and absent/``None`` values (not-required).

    Args:
        value: The raw ``requires_verification`` value from parsed frontmatter.

    Returns:
        ``True`` when the value denotes verification-required; ``False`` otherwise.
    """
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "on"}
    return bool(value)


def _is_offender(frontmatter: dict) -> bool:
    """Return True when the agent template violates the verification-consistency rule.

    An agent template is an offender when:
    - ``requires_verification`` is truthy, AND
    - the ``tools`` value contains neither ``Edit`` nor ``Write``.

    Agent templates may represent tools as a YAML list (e.g. ``- Read``) or as a
    scalar comma-separated string (e.g. ``tools: Read, Write, Bash``). Both formats
    are handled.  An absent ``tools`` field is treated as an empty tool set (offender
    when requires_verification is true), consistent with GE-116a-1-i.
    A missing or falsy ``requires_verification`` field is treated as not-required
    (allowed). A quoted YAML scalar (e.g. ``requires_verification: "false"``)
    parses to a string; such strings are interpreted case-insensitively so that
    ``"false"``/``"no"``/``"0"``/``"off"``/``""`` are correctly falsy rather than
    truthy-by-non-emptiness.

    Args:
        frontmatter: Parsed YAML frontmatter dict from the agent template.

    Returns:
        ``True`` when the template violates the rule; ``False`` when consistent
        or requires_verification is not declared.
    """
    if not _is_verification_required(frontmatter.get("requires_verification", False)):
        return False
    tools = frontmatter.get("tools")
    if tools is None:
        # tools field absent — treated as no edit capability (offender).
        return True
    if isinstance(tools, list):
        return not any(tool in _EDIT_CAPABLE_TOOLS for tool in tools)
    if isinstance(tools, str):
        # Scalar string format: "Read, Write, Edit, Bash" or "Read Bash Edit"
        # Split on commas (common format) and whitespace, then check membership.
        tool_names = {t.strip() for t in tools.replace(",", " ").split() if t.strip()}
        return not any(tool in _EDIT_CAPABLE_TOOLS for tool in tool_names)
    # Unknown format (e.g. tools: 42) — treated as no edit capability.
    return True


def main() -> int:
    """Run the agent verification consistency pre-commit hook.

    Scans STAGED ``templates/agents/*.md`` files by file identity only.
    For each staged agent template, parses YAML frontmatter and checks
    the requires_verification / tools coherence rule.  Exits 1 (fail-closed)
    when any offender is found, naming every offending path and stating both
    fixes.  Exits 0 when no agent templates are staged, or all staged
    templates are consistent, or a parse error occurs (fail-open per
    GE-116a-1-iii).

    Returns:
        0 if no offenders found or no relevant files staged.
        1 if one or more offending agent templates are staged.
    """
    staged = _get_staged_files()

    agent_templates = [
        f for f in staged
        if f.startswith(_AGENT_TEMPLATE_PREFIX) and f.endswith(".md")
    ]

    if not agent_templates:
        return 0

    offenders: list[str] = []

    for path in agent_templates:
        content = _read_staged_file(path)
        if not content:
            # Empty or uninspectable staged blob — cannot evaluate the rule.
            # Fail open with a warning per GE-116a-1-iii (never hard-block).
            # (A git-read failure already warned inside _read_staged_file.)
            print(
                f"{_HOOK_TAG} WARNING: {path} is empty or uninspectable; "
                "skipping (fail-open per GE-116a-1-iii).",
                file=sys.stderr,
            )
            continue

        frontmatter = _parse_frontmatter(content)
        if frontmatter is None:
            print(
                f"{_HOOK_TAG} WARNING: Could not parse frontmatter in {path}; "
                "skipping (fail-open per GE-116a-1-iii).",
                file=sys.stderr,
            )
            continue

        if _is_offender(frontmatter):
            offenders.append(path)

    if not offenders:
        return 0

    print(
        f"\n{_HOOK_TAG} FAIL: The following staged agent template(s) declare "
        "requires_verification: true but list no edit-capable tool (Edit or Write).\n"
        "An agent without Edit or Write cannot verify file changes.\n",
        file=sys.stderr,
    )
    for path in offenders:
        print(f"  Offender: {path}", file=sys.stderr)
        print(
            f"    Fix 1: Add 'Edit' or 'Write' to the tools list in {path}.",
            file=sys.stderr,
        )
        print(
            f"    Fix 2: Set requires_verification: false in {path} "
            "if this agent does not need to verify its changes.",
            file=sys.stderr,
        )
    print("", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(
            f"{_HOOK_TAG} unexpected error, skipping: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-07-20 [python-coder/GE-116a-1]: Initial implementation.
#   AC GE-116a-1: blocks commits staging a templates/agents/*.md whose
#   frontmatter has requires_verification: true AND tools contains neither
#   Edit nor Write. Fail-closed exit 1 on detection; fail-open exit 0 on
#   parse errors (GE-116a-1-iii). Scoped to staged templates/agents/*.md
#   by file identity only (git diff --cached); non-agent files with
#   triggering keywords are never inspected (GE-116c-2). Pre-existing
#   unstaged contradictions are ignored (GE-116c-3). Block message names
#   every offending path and states both fixes: add Edit/Write to tools,
#   or set requires_verification: false (GE-116b-1/GE-116b-1-i). Registered
#   in templates/scripts/commit_guardian/commit_guardian.json with files
#   pattern ^templates/agents/.*[.]md$ and pass_filenames: false.
#   (#GE-116a-1)
# - 2026-07-20 [BrainCandy/GE-116a-1]: Post-review remediation (code-review +
#   adversarial logic-check). (1) requires_verification truthiness now routed
#   through _is_verification_required so a quoted "false" is falsy instead of
#   truthy-by-non-emptiness (was false-blocking a valid read-only agent).
#   (2) _read_staged_file no longer falls back to a working-tree disk read on
#   git-show failure — that fallback could commit a staged contradiction fixed
#   only in the working tree, violating the staged-only contract (GE-116c-3);
#   it now fails open (empty string). (3) git helpers catch OSError as well as
#   SubprocessError so a missing git binary fails open inside main(), not only
#   at the __main__ wrapper. (4) empty/uninspectable staged blob now emits the
#   GE-116a-1-iii warning instead of skipping silently.
#   (#GE-116a-1)
# ====================================================================
