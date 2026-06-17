"""
MODULE: unit_tests/commit_guardian/test_check_secrets_template_prose_prefixes.py
GOAL: Regression test for BP-812 — templates/skills/ prose-prefix missing from
    the deployed check_secrets.py template copy.
BUSINESS CONTEXT: The deployed hook (built from templates/scripts/commit_guardian/)
    false-positives on TICKET-YYYYMMDD- style documentation placeholders inside
    templates/skills/**/*.md prose files because templates/skills/ is absent from
    _PROSE_FILE_PREFIXES in that copy. This forced a .security-allowlist workaround
    (commit c355f80). This test pins the template copy — NOT the dev-runtime copy
    at scripts/commit_guardian/check_secrets.py — because that copy already has
    the fix. The template copy is what build.py actually deploys to consumers.
ARCHITECTURE: Uses importlib.util.spec_from_file_location to load the exact
    template file without ambiguity, since three check_secrets.py copies exist
    in the repo. No sys.path manipulation of the commit_guardian directory is
    needed for the tuple-membership assertion; the _is_prose_exempt function
    cannot be exercised without the full module import chain (config, _resolve_root),
    so we restrict to tuple-level assertions which are robust and sufficient.

DECISION HISTORY
- 2026-06-17 [BP-812]: Initial TDD stub. Tests must be RED against the current
  templates/scripts/commit_guardian/check_secrets.py which lacks templates/skills/
  in _PROSE_FILE_PREFIXES. GREEN after python-coder forward-ports the two entries.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path to the TEMPLATE copy — this is what build.py deploys to consumers.
# Do NOT change this to scripts/commit_guardian/check_secrets.py (that copy
# already has the fix and a test against it would be trivially green).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATE_CHECK_SECRETS = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_secrets.py"
)


def _load_prose_prefixes_via_ast() -> tuple[str, ...] | None:
    """Parse the template file with the AST and extract _PROSE_FILE_PREFIXES.

    This approach avoids importing the module (which requires the sibling
    modules config and _resolve_root) while still reading the actual runtime
    value that would be used by the deployed hook.

    Returns:
        Tuple of strings from the _PROSE_FILE_PREFIXES assignment, or None if
        the variable cannot be found in the AST (indicating the template is
        missing or malformed).
    """
    if not _TEMPLATE_CHECK_SECRETS.exists():
        return None

    source = _TEMPLATE_CHECK_SECRETS.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_TEMPLATE_CHECK_SECRETS))

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "_PROSE_FILE_PREFIXES"
        ):
            # The value must be a Tuple of string constants
            if isinstance(node.value, ast.Tuple):
                elts = node.value.elts
                prefixes = []
                for elt in elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        prefixes.append(elt.value)
                return tuple(prefixes)

    return None


class TestCheckSecretsTemplateProsePrefixes(unittest.TestCase):
    """BP-812 regression: templates/scripts/commit_guardian/check_secrets.py
    must declare templates/skills/ in _PROSE_FILE_PREFIXES."""

    def setUp(self) -> None:
        """Load _PROSE_FILE_PREFIXES from the template file via AST."""
        # covers: BP-812
        self.assertIsFile = self.assertTrue  # alias for clarity below
        self.prefixes = _load_prose_prefixes_via_ast()

    def test_template_check_secrets_file_exists(self) -> None:
        # covers: BP-812
        """The template copy of check_secrets.py must exist for this test to be meaningful."""
        self.assertTrue(
            _TEMPLATE_CHECK_SECRETS.exists(),
            msg=(
                f"Template file not found: {_TEMPLATE_CHECK_SECRETS}\n"
                "The file must exist for BP-812 to be fixed."
            ),
        )

    def test_prose_prefixes_parseable(self) -> None:
        # covers: BP-812
        """The AST parser must be able to extract _PROSE_FILE_PREFIXES from the template.

        If this test fails, the variable was renamed or removed — a structural change
        that also breaks the hook's prose-exemption logic.
        """
        self.assertIsNotNone(
            self.prefixes,
            msg=(
                "_PROSE_FILE_PREFIXES could not be found in the AST of "
                f"{_TEMPLATE_CHECK_SECRETS}. "
                "Either the file is missing or the variable was renamed/removed."
            ),
        )

    def test_templates_skills_posix_in_prose_prefixes(self) -> None:
        # covers: BP-812
        """'templates/skills/' (POSIX) must be in _PROSE_FILE_PREFIXES of the TEMPLATE copy.

        This is the primary regression guard for BP-812. The deployed hook
        (built from this template) false-positives on documentation placeholders
        in templates/skills/**/*.md because this prefix is absent.

        Must be RED before python-coder adds the entry; GREEN after.
        """
        if self.prefixes is None:
            self.skipTest("_PROSE_FILE_PREFIXES not parseable — see test_prose_prefixes_parseable")

        self.assertIn(
            "templates/skills/",
            self.prefixes,
            msg=(
                "'templates/skills/' is MISSING from _PROSE_FILE_PREFIXES in the template copy:\n"
                f"  {_TEMPLATE_CHECK_SECRETS}\n\n"
                f"Current prefixes: {self.prefixes!r}\n\n"
                "Fix: add 'templates/skills/' to _PROSE_FILE_PREFIXES in that file. "
                "This is the forward-port required by BP-812."
            ),
        )

    def test_templates_skills_windows_variant_in_prose_prefixes(self) -> None:
        # covers: BP-812
        """'templates\\skills\\' (Windows backslash) must also be in _PROSE_FILE_PREFIXES.

        Consumers running on Windows compare file paths using backslash separators.
        Without this variant, the prose exemption silently fails on Windows even
        when the POSIX variant is present. Both must be added together.

        Must be RED before python-coder adds the entry; GREEN after.
        """
        if self.prefixes is None:
            self.skipTest("_PROSE_FILE_PREFIXES not parseable — see test_prose_prefixes_parseable")

        self.assertIn(
            "templates\\skills\\",
            self.prefixes,
            msg=(
                r"'templates\skills\\' is MISSING from _PROSE_FILE_PREFIXES in the template copy:"
                f"\n  {_TEMPLATE_CHECK_SECRETS}\n\n"
                f"Current prefixes: {self.prefixes!r}\n\n"
                r"Fix: add 'templates\\skills\\' alongside 'templates/skills/' for "
                "Windows path compatibility. Required by BP-812."
            ),
        )

    def test_existing_prose_prefixes_still_present(self) -> None:
        # covers: BP-812
        """The six existing prose prefixes must not be removed by the BP-812 fix.

        Guards against an accidental overwrite that clears existing entries while
        adding the new templates/skills/ ones.
        """
        if self.prefixes is None:
            self.skipTest("_PROSE_FILE_PREFIXES not parseable — see test_prose_prefixes_parseable")

        existing_required = (
            "tickets/",
            "tickets\\",
            "docs/retrospectives/",
            "docs\\retrospectives\\",
            "docs/acceptance-criteria/",
            "docs\\acceptance-criteria\\",
        )
        for prefix in existing_required:
            self.assertIn(
                prefix,
                self.prefixes,
                msg=(
                    f"Existing prefix {prefix!r} was unexpectedly removed from "
                    f"_PROSE_FILE_PREFIXES in {_TEMPLATE_CHECK_SECRETS}. "
                    "The BP-812 fix must ADD entries, not replace them."
                ),
            )


if __name__ == "__main__":
    unittest.main()
