"""
MODULE: unit_tests/ac_store/test_acd_1600c_4_iii.py
AC: ACD-1600c-4-iii — "A declared path outside the repository, or inside a
    copy the build regenerates, is refused"

GOAL: TDD red-baseline for scripts/ac_store/declared_files.py's
    path_form_errors(record_id, declared_files_value, *, build_definition=None)
    and load_build_definition(repo_root) (not yet implemented — see
    unit_tests/ac_store/_declared_files_fixtures.py module docstring for the
    full seam contract). All six of this AC's test_spec entries target
    unit_tests/ac_store/ — there is no commit_guardian-targeted entry for
    this AC.

WHY RED TODAY. scripts/ac_store/declared_files.py does not exist, so every
    call below raises ModuleNotFoundError. Tests 3 and 4 additionally rely
    on load_build_definition() reading the REAL repository's own build
    layout — `.claude/agents/test-writer.md` really is a build output of
    `templates/agents/test-writer.md` in THIS checkout (confirmed via
    `git check-ignore`: `.claude/agents` is a build-output directory listed
    in .gitignore, and the two files differ only in line-wrapping produced
    by the template compiler) — so these are genuine real-artifact checks,
    not synthetic fixtures, per the Real-Artifact Behavioral Test Mandate.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _declared_files_fixtures import REPO_ROOT, import_declared_files_module  # noqa: E402


class TestAbsoluteAndEscapingPathsRefusedAsNotRepoRelative(unittest.TestCase):
    """test_absolute_and_escaping_paths_refused_as_not_repo_relative"""

    def test_absolute_and_escaping_paths_refused_as_not_repo_relative(self) -> None:
        # covers: ACD-1600c-4-iii
        # angle: failure
        """/home/dev/repo/scripts/a.py and ../other-repo/scripts/b.py each
        get one message naming R and the path, stating declared paths are
        repo-root-relative and stay inside it.
        """
        declared = [
            {"path": "/home/dev/repo/scripts/a.py", "state": "existing"},
            {"path": "../other-repo/scripts/b.py", "state": "existing"},
        ]

        dfm = import_declared_files_module()
        errors = dfm.path_form_errors("R", declared)

        self.assertEqual(len(errors), 2, msg=f"expected exactly 2 messages, got: {errors}")
        joined = "\n".join(errors)
        self.assertIn("R", joined)
        self.assertIn("/home/dev/repo/scripts/a.py", joined)
        self.assertIn("../other-repo/scripts/b.py", joined)
        for message in errors:
            self.assertIn("relative to the repository root", message)
            self.assertIn("stay inside it", message)


class TestBackslashPathRefusedWithForwardSlashMessage(unittest.TestCase):
    """test_backslash_path_refused_with_forward_slash_message"""

    def test_backslash_path_refused_with_forward_slash_message(self) -> None:
        # covers: ACD-1600c-4-iii
        # angle: criterion
        """scripts\\ac_store\\c.py gets one message naming R and the path,
        stating declared paths use forward slashes.
        """
        declared = [{"path": "scripts\\ac_store\\c.py", "state": "existing"}]

        dfm = import_declared_files_module()
        errors = dfm.path_form_errors("R", declared)

        self.assertEqual(len(errors), 1, msg=f"expected exactly 1 message, got: {errors}")
        message = errors[0]
        self.assertIn("R", message)
        self.assertIn("scripts\\ac_store\\c.py", message)
        self.assertIn("forward slashes", message)


class TestRegeneratedCopyRefusedNamingTemplateSource(unittest.TestCase):
    """test_regenerated_copy_refused_naming_template_source"""

    def test_regenerated_copy_refused_naming_template_source(self) -> None:
        # covers: ACD-1600c-4-iii
        # angle: criterion
        """.claude/agents/test-writer.md is refused as a regenerated copy,
        and the message names templates/agents/test-writer.md as the file
        to declare instead — using this repo's OWN real build definition.
        """
        declared = [{"path": ".claude/agents/test-writer.md", "state": "existing"}]

        dfm = import_declared_files_module()
        build_definition = dfm.load_build_definition(REPO_ROOT)
        errors = dfm.path_form_errors("R", declared, build_definition=build_definition)

        self.assertEqual(len(errors), 1, msg=f"expected exactly 1 message, got: {errors}")
        message = errors[0]
        self.assertIn("R", message)
        self.assertIn(".claude/agents/test-writer.md", message)
        self.assertIn("templates/agents/test-writer.md", message)


class TestTemplateSourcePathProducesNoMessage(unittest.TestCase):
    """test_template_source_path_produces_no_message"""

    def test_template_source_path_produces_no_message(self) -> None:
        # covers: ACD-1600c-4-iii
        # angle: criterion
        """templates/agents/test-writer.md produces no message; the
        five-entry record from the AC's own criteria yields exactly four
        messages (the first four entries).
        """
        declared = [
            {"path": "/home/dev/repo/scripts/a.py", "state": "existing"},
            {"path": "../other-repo/scripts/b.py", "state": "existing"},
            {"path": "scripts\\ac_store\\c.py", "state": "existing"},
            {"path": ".claude/agents/test-writer.md", "state": "existing"},
            {"path": "templates/agents/test-writer.md", "state": "existing"},
        ]

        dfm = import_declared_files_module()
        build_definition = dfm.load_build_definition(REPO_ROOT)
        errors = dfm.path_form_errors("R", declared, build_definition=build_definition)

        self.assertEqual(len(errors), 4, msg=f"expected exactly 4 messages, got: {errors}")
        # The clean fifth entry (templates/agents/test-writer.md, the real
        # source of the .claude/ copy) must never itself be the flagged path
        # in any of the four messages.
        self.assertFalse(
            any(
                "templates/agents/test-writer.md" in message
                and ".claude/agents/test-writer.md" not in message
                for message in errors
            ),
            msg=f"templates/agents/test-writer.md must never be the offending "
            f"path itself: {errors}",
        )


class TestRegeneratedCopyWithoutKnownSourceRefusedWithoutGuess(unittest.TestCase):
    """test_regenerated_copy_without_known_source_refused_without_guess"""

    def test_regenerated_copy_without_known_source_refused_without_guess(self) -> None:
        # covers: ACD-1600c-4-iii
        # angle: boundary
        """A path under a regenerated root with no mappable source is
        refused, and the message says no source could be determined,
        naming no source.
        """
        declared = [{"path": "build_output/no_source/x.py", "state": "existing"}]
        fixture_build_definition = {"build_output/no_source/": None}

        dfm = import_declared_files_module()
        errors = dfm.path_form_errors("R", declared, build_definition=fixture_build_definition)

        self.assertEqual(len(errors), 1, msg=f"expected exactly 1 message, got: {errors}")
        message = errors[0]
        self.assertIn("R", message)
        self.assertIn("build_output/no_source/x.py", message)
        self.assertIn("no source could be determined", message)


class TestRegeneratedRootsReadFromBuildDefinition(unittest.TestCase):
    """test_regenerated_roots_read_from_build_definition"""

    def test_regenerated_roots_read_from_build_definition(self) -> None:
        # covers: ACD-1600c-4-iii
        # angle: seam
        """A fixture build definition with an extra regenerated root makes a
        path under it refused, with no change to the check — path_form_errors
        is generic over whatever mapping it is given.
        """
        declared = [{"path": "extra_output/thing.py", "state": "existing"}]
        fixture_build_definition = {"extra_output/": "extra_source/"}

        dfm = import_declared_files_module()
        real_default = dfm.load_build_definition(REPO_ROOT)
        self.assertNotIn(
            "extra_output/",
            real_default,
            msg="Sanity check: this root must not already be real, or the test "
            "would not demonstrate fixture-driven behaviour.",
        )

        errors = dfm.path_form_errors("R", declared, build_definition=fixture_build_definition)

        self.assertEqual(len(errors), 1, msg=f"expected exactly 1 message, got: {errors}")
        message = errors[0]
        self.assertIn("R", message)
        self.assertIn("extra_output/thing.py", message)
        self.assertIn("extra_source/thing.py", message)


class TestRegeneratedCopyDetectedForDotSlashPrefixedPath(unittest.TestCase):
    """test_regenerated_copy_detected_for_dot_slash_prefixed_path

    H-1 (review finding, ACD-1600c-4-iii): `_regenerated_copy_error` matches
    a regenerated root with a raw `path.startswith(prefix)` and no
    normalisation, so `./.claude/agents/foo.md` -- a leading-'./' spelling
    of a path the build regenerates -- escapes the refusal entirely today.
    """

    def test_regenerated_copy_detected_for_dot_slash_prefixed_path(self) -> None:
        # covers: ACD-1600c-4-iii
        # angle: discrimination
        """A leading './' on an otherwise-matching regenerated-copy path must
        not defeat the refusal: it must still be refused, still naming
        templates/agents/foo.md, exactly like the un-prefixed spelling does.
        This must go red against TODAY's real (buggy) implementation --
        the named plausible wrong version is the shipped
        `path.startswith(prefix)` with no normalisation.
        """
        declared = [{"path": "./.claude/agents/foo.md", "state": "existing"}]
        fixture_build_definition = {".claude/agents/": "templates/agents/"}

        dfm = import_declared_files_module()
        errors = dfm.path_form_errors("R", declared, build_definition=fixture_build_definition)

        self.assertEqual(
            len(errors), 1,
            msg=(
                "H-1 bypass: './.claude/agents/foo.md' must be refused as a "
                f"regenerated copy just like the unprefixed spelling; got: {errors}"
            ),
        )
        message = errors[0]
        self.assertIn("R", message)
        self.assertIn("./.claude/agents/foo.md", message)
        self.assertIn("templates/agents/foo.md", message)


class TestRegeneratedCopyDetectedForCaseVariedPath(unittest.TestCase):
    """test_regenerated_copy_detected_for_case_varied_path

    H-1 (review finding, ACD-1600c-4-iii): a case-varied spelling of a
    regenerated root (`.Claude/` vs `.claude/`) also escapes today's raw
    `startswith` match, even though Windows/macOS filesystems treat the two
    as the SAME path on disk.
    """

    def test_regenerated_copy_detected_for_case_varied_path(self) -> None:
        # covers: ACD-1600c-4-iii
        # angle: discrimination
        """A case-varied spelling of a regenerated root must still be
        refused, still naming templates/agents/foo.md. Red against today's
        case-sensitive `startswith` comparison -- the named plausible wrong
        version this discriminates against.
        """
        declared = [{"path": ".Claude/agents/foo.md", "state": "existing"}]
        fixture_build_definition = {".claude/agents/": "templates/agents/"}

        dfm = import_declared_files_module()
        errors = dfm.path_form_errors("R", declared, build_definition=fixture_build_definition)

        self.assertEqual(
            len(errors), 1,
            msg=(
                "H-1 bypass: '.Claude/agents/foo.md' (case-varied) must be "
                f"refused as a regenerated copy; got: {errors}"
            ),
        )
        message = errors[0]
        self.assertIn("R", message)
        self.assertIn(".Claude/agents/foo.md", message)
        self.assertIn("templates/agents/foo.md", message)


class TestNonCanonicalDotSlashPrefixRefusedNamingCanonicalForm(unittest.TestCase):
    """test_non_canonical_dot_slash_prefix_refused_naming_canonical_form"""

    def test_non_canonical_dot_slash_prefix_refused_naming_canonical_form(self) -> None:
        # covers: ACD-1600c-4-iii
        # angle: boundary
        """A leading './' on a path that is NOT a regenerated-copy match is
        its own path-form violation -- the store's answer must never carry a
        non-canonical spelling -- refused, naming the canonical spelling on
        its own (quoted separately from the original).
        """
        declared = [{"path": "./scripts/ac_store/c.py", "state": "existing"}]

        dfm = import_declared_files_module()
        errors = dfm.path_form_errors("R", declared, build_definition={})

        self.assertEqual(len(errors), 1, msg=f"expected exactly 1 message, got: {errors}")
        message = errors[0]
        self.assertIn("R", message)
        self.assertIn("./scripts/ac_store/c.py", message)
        self.assertIn("canonical", message.lower())
        self.assertIn(
            "'scripts/ac_store/c.py'", message,
            msg="canonical form must be named on its own, quoted, distinct "
            f"from the quoted original spelling: {message!r}",
        )


class TestNonCanonicalDoubleSlashRefusedNamingCanonicalForm(unittest.TestCase):
    """test_non_canonical_double_slash_refused_naming_canonical_form"""

    def test_non_canonical_double_slash_refused_naming_canonical_form(self) -> None:
        # covers: ACD-1600c-4-iii
        # angle: boundary
        """An internal repeated '//' is the same non-canonical-spelling
        violation, refused, naming the collapsed canonical form.
        """
        declared = [{"path": "scripts//ac_store//c.py", "state": "existing"}]

        dfm = import_declared_files_module()
        errors = dfm.path_form_errors("R", declared, build_definition={})

        self.assertEqual(len(errors), 1, msg=f"expected exactly 1 message, got: {errors}")
        message = errors[0]
        self.assertIn("R", message)
        self.assertIn("scripts//ac_store//c.py", message)
        self.assertIn(
            "'scripts/ac_store/c.py'", message,
            msg=f"canonical (single-slash) form must be named: {message!r}",
        )


class TestNonCanonicalTrailingSlashRefusedNamingCanonicalForm(unittest.TestCase):
    """test_non_canonical_trailing_slash_refused_naming_canonical_form"""

    def test_non_canonical_trailing_slash_refused_naming_canonical_form(self) -> None:
        # covers: ACD-1600c-4-iii
        # angle: boundary
        """A trailing '/' on a declared file entry is the same
        non-canonical-spelling violation, refused, naming the form with the
        trailing slash stripped.
        """
        declared = [{"path": "scripts/ac_store/c.py/", "state": "existing"}]

        dfm = import_declared_files_module()
        errors = dfm.path_form_errors("R", declared, build_definition={})

        self.assertEqual(len(errors), 1, msg=f"expected exactly 1 message, got: {errors}")
        message = errors[0]
        self.assertIn("R", message)
        self.assertIn("scripts/ac_store/c.py/", message)
        self.assertIn(
            "'scripts/ac_store/c.py'", message,
            msg=f"canonical (no trailing slash) form must be named: {message!r}",
        )


if __name__ == "__main__":
    unittest.main()
