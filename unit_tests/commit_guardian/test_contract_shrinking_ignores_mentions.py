"""
MODULE: test_contract_shrinking_ignores_mentions
GOAL: The contract-shrinking guard must fire on a real added skip/xfail
    decorator or call, and must NOT fire on text that merely MENTIONS those
    tokens — a docstring, a string literal, a changelog sentence, or a
    synthetic diff embedded inside a test fixture.
BUSINESS CONTEXT: Every weakening pattern was written as ``^\\+.*<token>``, so
    the token matched ANYWHERE in an added line. The guard therefore flagged
    its own test suite (whose fixtures build sample diffs containing
    ``+    @unittest.skip("flaky")``), any changelog describing it, and any
    merge commit that imported those files. Observed live: a merge of
    origin/main was blocked by twelve violations, every one of which was
    prose or fixture text — while the branch under review deleted no tests
    and added no xfail. A guard that cannot review its own repository trains
    the team to reach for SKIP=check-contract-shrinking, which is exactly how
    a real weakening later slips through unnoticed.
ARCHITECTURE: Loads check_contract_shrinking.py from its canonical template
    path and drives ``_scan_diff()`` directly for per-case precision, mirroring
    test_ge_119_contract_shrinking_rename_aware.py. The must-still-fire case is
    additionally run end-to-end through the real CLI via HOOK_TEST_DIFF so the
    suite cannot pass against a guard that has been neutered into never
    firing — the obvious wrong way to make the false positives go away.
    Do NOT edit check_contract_shrinking.py from this test file.
"""

from __future__ import annotations

import importlib.util as _ilu
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_CANONICAL = (
    Path(__file__).parent.parent.parent
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_contract_shrinking.py"
)


def _load_module():
    """Load the guard from its canonical template path.

    Returns:
        The loaded module, or None when the canonical file is absent.
    """
    if not _CANONICAL.exists():
        return None
    spec = _ilu.spec_from_file_location("check_contract_shrinking_mentions", _CANONICAL)
    mod = _ilu.module_from_spec(spec)
    sys.modules["check_contract_shrinking_mentions"] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


def _run_hook_with_diff(diff_content: str) -> subprocess.CompletedProcess:
    """Run the real hook end-to-end via HOOK_TEST_DIFF (no mocking).

    Args:
        diff_content: Full unified-diff text to feed the hook.

    Returns:
        The completed subprocess result.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False) as handle:
        handle.write(diff_content)
        tmp_path = handle.name
    try:
        env = os.environ.copy()
        env["HOOK_TEST_DIFF"] = tmp_path
        return subprocess.run(
            [sys.executable, str(_CANONICAL)],
            env=env,
            capture_output=True,
            text=True,
        )
    finally:
        os.unlink(tmp_path)


def _weakening_labels(diff: str) -> list[str]:
    """Return only the weakening-pattern violations for *diff*.

    Args:
        diff: Unified-diff text.

    Returns:
        List of violation label strings produced by the guard's scan.
    """
    return [f"{label}: {context}" for label, context in _mod._scan_diff(diff).violations]


@unittest.skipUnless(_mod is not None, f"guard not found at {_CANONICAL}")
class TestMentionsAreNotWeakening(unittest.TestCase):
    """Prose and fixture text that names the tokens must not be flagged."""

    def test_docstring_mentioning_tokens_is_not_a_violation(self) -> None:
        # covers: GE-119
        """A docstring listing the weakening patterns is documentation."""
        diff = textwrap.dedent(
            '''\
            diff --git a/unit_tests/commit_guardian/test_x.py b/unit_tests/commit_guardian/test_x.py
            --- a/unit_tests/commit_guardian/test_x.py
            +++ b/unit_tests/commit_guardian/test_x.py
            @@ -1,0 +1,3 @@
            +        """A diff exercising pytest.skip, pytest.mark.xfail,
            +    @unittest.skip and
            +    @unittest.expectedFailure)."""
            '''
        )
        self.assertEqual(
            _weakening_labels(diff),
            [],
            "A docstring that merely names the weakening tokens must not be "
            "reported as test weakening.",
        )

    def test_string_literal_and_nested_fixture_diff_are_not_violations(self) -> None:
        # covers: GE-119
        """Fixture text — including a diff INSIDE a string — is not weakening.

        The inner lines start with a second ``+`` because the fixture is itself
        a synthetic diff; the guard must not read that as real added code.
        """
        diff = textwrap.dedent(
            '''\
            diff --git a/unit_tests/commit_guardian/test_y.py b/unit_tests/commit_guardian/test_y.py
            --- a/unit_tests/commit_guardian/test_y.py
            +++ b/unit_tests/commit_guardian/test_y.py
            @@ -1,0 +1,5 @@
            +    SAMPLE = [
            +            "pytest.mark.xfail",
            +            +    @unittest.skip("flaky")
            +            +        pytest.skip("nope")
            +    ]
            '''
        )
        self.assertEqual(
            _weakening_labels(diff),
            [],
            "String literals and a synthetic diff embedded in a fixture must "
            "not be reported as test weakening.",
        )

    def test_changelog_prose_is_not_a_violation(self) -> None:
        # covers: GE-119
        """A changelog sentence describing the guard is not weakening."""
        diff = textwrap.dedent(
            """\
            diff --git a/changelogs/2026-08-13-x.md b/changelogs/2026-08-13-x.md
            --- a/changelogs/2026-08-13-x.md
            +++ b/changelogs/2026-08-13-x.md
            @@ -1,0 +1,1 @@
            +description: "check_contract_shrinking.py's _scan_diff() ran its weakening regexes (pytest.mark.xfail, @unittest.expectedFailure) as bare finditer calls."
            """
        )
        self.assertEqual(
            _weakening_labels(diff),
            [],
            "Changelog prose naming the tokens must not be reported as test "
            "weakening.",
        )

    def test_skip_unless_guard_is_not_a_disabled_test(self) -> None:
        # covers: GE-119
        """``@unittest.skipUnless`` is a conditional guard, not a disabled test.

        ``@unittest.skip`` is a literal prefix of ``@unittest.skipUnless``, so a
        substring match wrongly flags every environment-conditional test.
        """
        diff = textwrap.dedent(
            """\
            diff --git a/unit_tests/ac_store/test_z.py b/unit_tests/ac_store/test_z.py
            --- a/unit_tests/ac_store/test_z.py
            +++ b/unit_tests/ac_store/test_z.py
            @@ -1,0 +1,2 @@
            +@unittest.skipUnless(_HAVE_VITEST, _SKIP_REASON)
            +class TestRealRun(unittest.TestCase):
            """
        )
        self.assertEqual(
            _weakening_labels(diff),
            [],
            "@unittest.skipUnless is a conditional guard and must not be "
            "reported as a disabled test.",
        )


@unittest.skipUnless(_mod is not None, f"guard not found at {_CANONICAL}")
class TestRealWeakeningStillFires(unittest.TestCase):
    """The guard must still catch genuine weakening — no neutering."""

    def test_real_decorators_and_skip_call_are_flagged(self) -> None:
        # covers: GE-119
        """Genuine added decorators / skip calls are still violations."""
        diff = textwrap.dedent(
            """\
            diff --git a/unit_tests/ac_store/test_real.py b/unit_tests/ac_store/test_real.py
            --- a/unit_tests/ac_store/test_real.py
            +++ b/unit_tests/ac_store/test_real.py
            @@ -1,0 +1,8 @@
            +    @unittest.skip("flaky")
            +    def test_a(self):
            +        pass
            +    @unittest.expectedFailure
            +    def test_b(self):
            +        pass
            +    @pytest.mark.xfail(reason="broken")
            +    def test_c(self):
            +        pytest.skip("nope")
            """
        )
        labels = " ".join(_weakening_labels(diff))
        self.assertIn("@unittest.skip added", labels)
        self.assertIn("@unittest.expectedFailure added", labels)
        self.assertIn("pytest.mark.xfail added", labels)
        self.assertIn("pytest.skip added", labels)

    def test_real_weakening_fails_the_cli_end_to_end(self) -> None:
        # covers: GE-119
        """The real CLI exits non-zero on genuine weakening.

        Guards the against-dead-code case: a guard neutered into never firing
        would satisfy every negative test above.
        """
        diff = textwrap.dedent(
            """\
            diff --git a/scripts/prod.py b/scripts/prod.py
            --- a/scripts/prod.py
            +++ b/scripts/prod.py
            @@ -1,0 +1,1 @@
            +PRODUCTION_CHANGE = True
            diff --git a/unit_tests/ac_store/test_real.py b/unit_tests/ac_store/test_real.py
            --- a/unit_tests/ac_store/test_real.py
            +++ b/unit_tests/ac_store/test_real.py
            @@ -1,0 +1,2 @@
            +    @unittest.skip("flaky")
            +    def test_a(self):
            """
        )
        result = _run_hook_with_diff(diff)
        self.assertNotEqual(
            result.returncode,
            0,
            "The CLI must fail on a genuinely added @unittest.skip alongside a "
            f"production change. stdout={result.stdout!r}",
        )


if __name__ == "__main__":
    unittest.main()
