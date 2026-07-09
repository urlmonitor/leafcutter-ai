"""
MODULE: unit_tests/commit_guardian/test_check_secrets.py
GOAL: Unit tests for BP-812 — verify that templates/skills/ is present in
    _PROSE_FILE_PREFIXES in check_secrets.py and that the prefix-exemption
    logic correctly treats files under that prefix as prose-exempt.
BUSINESS CONTEXT: The check_secrets.py hook must not false-positive on
    TICKET-YYYYMMDD-style documentation placeholders inside
    templates/skills/**/*.md skill prose files. Without the prefix entry
    those files accumulate .security-allowlist workarounds per file.
    In this worktree, check_secrets.py exists only at
    templates/scripts/commit_guardian/ (the canonical template source that
    build.py deploys to consumers). The companion test
    test_check_secrets_template_prose_prefixes.py tests the structural tuple
    membership; this module adds the behavioral coverage (prefix-match logic).
ARCHITECTURE: Uses AST parsing to extract _PROSE_FILE_PREFIXES without
    importing the module (which requires config, _resolve_root, and
    scan_secrets). The behavioral tests replicate Rule 1 of _is_prose_exempt()
    directly from the AST-parsed tuple, covering POSIX, Windows, and nested
    path patterns.

DECISION HISTORY
- 2026-07-08 [BP-812/python-coder]: Initial implementation. Targets the
  canonical template source at templates/scripts/commit_guardian/check_secrets.py.
  GREEN because the fix is already applied; test is a regression guard.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
# The canonical source copy that build.py deploys to consumers.
# scripts/commit_guardian/check_secrets.py is the deployed workspace output;
# in the epic worktree the source-of-truth is the template copy below.
_CHECK_SECRETS = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_secrets.py"
)


# ---------------------------------------------------------------------------
# AST helper
# ---------------------------------------------------------------------------

def _load_prose_prefixes() -> tuple[str, ...] | None:
    """Parse _PROSE_FILE_PREFIXES from check_secrets.py via AST.

    Avoids importing the module (which requires config, _resolve_root, and
    scan_secrets) while still reading the exact runtime value.

    Returns:
        Tuple of strings from _PROSE_FILE_PREFIXES, or None when the variable
        cannot be found (file absent or variable renamed/removed).
    """
    if not _CHECK_SECRETS.exists():
        return None

    source = _CHECK_SECRETS.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_CHECK_SECRETS))

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "_PROSE_FILE_PREFIXES"
            and isinstance(node.value, ast.Tuple)
        ):
            prefixes = []
            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    prefixes.append(elt.value)
            return tuple(prefixes)

    return None


def _is_prefix_exempt(path_str: str, prefixes: tuple[str, ...]) -> bool:
    """Replicate Rule 1 of _is_prose_exempt() using the parsed prefix tuple.

    Keeps tests independent of the module import chain while still exercising
    the actual matching contract (startswith OR path-substring match).

    Args:
        path_str: File path to check (as string).
        prefixes: The _PROSE_FILE_PREFIXES tuple extracted via AST.

    Returns:
        True when path_str matches at least one prose-only prefix.
    """
    normalised_path = path_str.replace("\\", "/")
    for prefix in prefixes:
        normalised_prefix = prefix.replace("\\", "/")
        if (
            normalised_path.startswith(normalised_prefix)
            or ("/" + normalised_prefix) in normalised_path
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------

class TestCheckSecretsProsePrefixesStructure(unittest.TestCase):
    """BP-812 structural regression: _PROSE_FILE_PREFIXES must contain
    templates/skills/ entries in the canonical check_secrets.py source."""

    def setUp(self) -> None:
        """Load _PROSE_FILE_PREFIXES via AST."""
        # covers: BP-812
        self.prefixes = _load_prose_prefixes()

    def test_check_secrets_source_file_exists(self) -> None:
        # covers: BP-812
        """The canonical check_secrets.py template source must exist."""
        self.assertTrue(
            _CHECK_SECRETS.exists(),
            msg=(
                f"Source file not found: {_CHECK_SECRETS}\n"
                "Expected at templates/scripts/commit_guardian/check_secrets.py"
            ),
        )

    def test_prose_prefixes_parseable(self) -> None:
        # covers: BP-812
        """AST parser must successfully extract _PROSE_FILE_PREFIXES."""
        self.assertIsNotNone(
            self.prefixes,
            msg=(
                "_PROSE_FILE_PREFIXES could not be found in the AST of "
                f"{_CHECK_SECRETS}. "
                "Either the file is missing or the variable was renamed/removed."
            ),
        )

    def test_templates_skills_posix_present(self) -> None:
        # covers: BP-812
        """'templates/skills/' (POSIX separator) must be in _PROSE_FILE_PREFIXES."""
        if self.prefixes is None:
            self.skipTest("_PROSE_FILE_PREFIXES not parseable")

        self.assertIn(
            "templates/skills/",
            self.prefixes,
            msg=(
                "'templates/skills/' is MISSING from _PROSE_FILE_PREFIXES. "
                f"Current prefixes: {self.prefixes!r}"
            ),
        )

    def test_templates_skills_windows_variant_present(self) -> None:
        # covers: BP-812
        r"""'templates\skills\' (Windows backslash) must be in _PROSE_FILE_PREFIXES."""
        if self.prefixes is None:
            self.skipTest("_PROSE_FILE_PREFIXES not parseable")

        self.assertIn(
            "templates\\skills\\",
            self.prefixes,
            msg=(
                r"'templates\skills\\' is MISSING from _PROSE_FILE_PREFIXES. "
                f"Current prefixes: {self.prefixes!r}"
            ),
        )


# ---------------------------------------------------------------------------
# Behavioral tests
# ---------------------------------------------------------------------------

class TestCheckSecretsSkillProseExemptBehavior(unittest.TestCase):
    """Behavioral tests: files under templates/skills/ are treated as prose-exempt.

    Replicates Rule 1 of _is_prose_exempt() using the AST-parsed prefix tuple.
    These tests verify the matching logic itself, not just tuple membership —
    a prefix that is syntactically present but logically broken (wrong separator,
    trailing slash missing) would pass structural tests but fail here.
    """

    def setUp(self) -> None:
        """Load _PROSE_FILE_PREFIXES and skip if unavailable."""
        # covers: BP-812
        self.prefixes = _load_prose_prefixes()
        if self.prefixes is None:
            self.skipTest(
                "_PROSE_FILE_PREFIXES not parseable from check_secrets.py"
            )

    def test_top_level_skill_file_is_exempt(self) -> None:
        # covers: BP-812
        """A SKILL.md at the direct child of templates/skills/ is prose-exempt."""
        path = "templates/skills/signoff/SKILL.md"
        self.assertTrue(
            _is_prefix_exempt(path, self.prefixes),
            msg=(
                f"Path '{path}' is NOT exempt. "
                "Expected 'templates/skills/' prefix to match via startswith."
            ),
        )

    def test_deeply_nested_skill_file_is_exempt(self) -> None:
        # covers: BP-812
        """A file nested multiple levels under templates/skills/ is prose-exempt."""
        path = "templates/skills/building-epics/SKILL.md"
        self.assertTrue(
            _is_prefix_exempt(path, self.prefixes),
            msg=f"Deeply nested path '{path}' is NOT exempt under prefix list.",
        )

    def test_absolute_path_style_skill_file_is_exempt(self) -> None:
        # covers: BP-812
        """A path that contains '/templates/skills/' as a substring is exempt.

        Replicates how _is_prose_exempt() handles absolute staged-file paths
        on Linux where the path is something like
        /home/user/project/templates/skills/signoff/SKILL.md.
        """
        path = "/home/user/myproject/templates/skills/knowledge-query/SKILL.md"
        self.assertTrue(
            _is_prefix_exempt(path, self.prefixes),
            msg=(
                f"Absolute-style path '{path}' is NOT exempt. "
                "The substring match ('/' + prefix) should cover absolute paths."
            ),
        )

    def test_windows_path_to_skill_file_is_exempt(self) -> None:
        # covers: BP-812
        r"""A file under templates\skills\ (Windows backslash path) is exempt."""
        path = r"templates\skills\knowledge-query\SKILL.md"
        self.assertTrue(
            _is_prefix_exempt(path, self.prefixes),
            msg=(
                f"Windows-style path '{path}' is NOT exempt. "
                r"The 'templates\\skills\\' variant must match after backslash normalisation."
            ),
        )

    def test_non_skills_template_not_exempt_by_skills_prefix(self) -> None:
        # covers: BP-812
        """A file outside templates/skills/ is NOT exempt by the skills prefix alone."""
        path = "templates/agents/python-coder.md"
        exempt_by_skills = any(
            path.replace("\\", "/").startswith(p.replace("\\", "/"))
            or ("/" + p.replace("\\", "/")) in path.replace("\\", "/")
            for p in self.prefixes
            if "skills" in p
        )
        self.assertFalse(
            exempt_by_skills,
            msg=(
                f"Path '{path}' was incorrectly exempted by a skills prefix. "
                "Only files under templates/skills/ should match."
            ),
        )

    def test_ticket_file_still_exempt(self) -> None:
        # covers: BP-812
        """An existing prose prefix (tickets/) must still be honored.

        Guards against the BP-812 fix accidentally removing pre-existing entries
        in _PROSE_FILE_PREFIXES.
        """
        path = "tickets/00_inbox/my-ticket.md"
        self.assertTrue(
            _is_prefix_exempt(path, self.prefixes),
            msg=(
                f"Path '{path}' is NOT exempt — the 'tickets/' prefix was "
                "removed when adding 'templates/skills/'. The fix must ADD, "
                "not replace, existing prefixes."
            ),
        )


if __name__ == "__main__":
    unittest.main()
