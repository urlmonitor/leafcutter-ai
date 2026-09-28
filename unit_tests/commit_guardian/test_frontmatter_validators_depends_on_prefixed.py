"""
MODULE: test_frontmatter_validators_depends_on_prefixed
GOAL: Regression tests for validate_depends_on() (frontmatter_validators.py) —
      the third consumer of the ``depends_on`` field to need dual-spelling
      support, mirroring the already-committed fix in
      ticket_frontmatter_guard._depends_candidates() (f9ee688c0).
BUSINESS CONTEXT: A depends_on entry is read by three places: build-feature.js's
      toWorktreePath (needs the repo-relative prefixed form, resolved against the
      worktree root), ticket_frontmatter_guard.py's _depends_candidates() (already
      fixed to accept both spellings), and validate_depends_on() here — invoked by
      the check-doc-frontmatter pre-commit hook. This validator was still
      bare-only: given a prefixed entry it concatenated a doubled, non-existent
      path and reported a real dependency as missing, blocking commits.
ARCHITECTURE: Loads frontmatter_validators.py from the canonical
      templates/scripts/commit_guardian/ source tree via importlib, with that
      directory temporarily added to sys.path so its sibling-module imports
      (config, diagram_type_validators, doc_type_validators) resolve. Exercises
      validate_depends_on() directly against real on-disk tempdir ticket trees
      (no mocks) so path resolution is genuinely tested, not assumed.

====================================================================
DECISION HISTORY
====================================================================
- 2026-09-08 [python-coder/EPIC-StartingNewWorkTheProperWayAlways]: Initial
  tests for the validate_depends_on() dual-spelling fix. Of the four scenarios
  below, only test_prefixed_same_epic_form_now_resolves is genuinely RED
  against the unmodified validator (a prefixed entry concatenates into a
  doubled path and is reported missing). The other three assert properties
  the old bare-only code already satisfied by omission: the bare form was
  never broken, a bare dangling reference was always reported, and a
  cross-epic prefixed path was always rejected (it just never had a chance to
  wrongly resolve, since the old code never looked at prefixed paths at all).
  Reported accurately rather than inflating the red count, matching how the
  sibling fix (_depends_candidates(), f9ee688c0) reported its own red/green
  split.
====================================================================
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_COMMIT_GUARDIAN = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"


def _import_module_from_dir(module_name: str, directory: Path):
    """Import a module by name from a specific directory.

    Temporarily inserts *directory* at the front of sys.path so that its
    sibling-module imports (config, diagram_type_validators, doc_type_validators)
    resolve, then removes it after import.

    Args:
        module_name: Bare module name (no extension).
        directory: Directory to add to sys.path before importing.

    Returns:
        The imported module object.
    """
    dir_str = str(directory)
    inserted = False
    try:
        if dir_str not in sys.path:
            sys.path.insert(0, dir_str)
            inserted = True
        sys.modules.pop(module_name, None)
        spec = importlib.util.spec_from_file_location(
            module_name, directory / f"{module_name}.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load spec for {module_name} from {directory}")  # noqa: TRY003
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    finally:
        if inserted and dir_str in sys.path:
            sys.path.remove(dir_str)


try:
    _fmv = _import_module_from_dir("frontmatter_validators", _SCRIPTS_COMMIT_GUARDIAN)
    _MODULE_OK = True
    _MODULE_ERR = ""
except (ImportError, OSError) as _exc:
    _MODULE_OK = False
    _MODULE_ERR = str(_exc)


@unittest.skipUnless(_MODULE_OK, f"frontmatter_validators module load failed: {_MODULE_ERR}")
class TestValidateDependsOnAcceptsBareAndPrefixedForms(unittest.TestCase):
    """validate_depends_on() dual-spelling support for depends_on entries.

    Mirrors TestDependsOnAcceptsBareAndPrefixedForms in
    unit_tests/test_ticket_frontmatter_guard.py (the already-fixed sibling
    validator), applied to frontmatter_validators.validate_depends_on()
    instead of ticket_frontmatter_guard._depends_candidates().
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        root = Path(self._tmpdir.name)
        self.epic_dir = root / "tickets" / "00_inbox" / "epics" / "EPIC-Foo"
        self.epic_dir.mkdir(parents=True)
        self.other_epic_dir = root / "tickets" / "00_inbox" / "epics" / "EPIC-Other"
        self.other_epic_dir.mkdir(parents=True)
        self.ticket_path = self.epic_dir / "07_TICKET-consumer.md"
        self.ticket_path.write_text("---\n---\n", encoding="utf-8")

    def test_bare_sibling_filename_still_valid(self) -> None:
        # covers: python-coder-depends-on-prefixed
        """Existing bare-filename spelling must keep resolving unchanged."""
        dep = self.epic_dir / "06_TICKET-dep.md"
        dep.write_text("---\n---\n", encoding="utf-8")
        errors = _fmv.validate_depends_on(
            {"depends_on": ["06_TICKET-dep.md"]}, self.ticket_path
        )
        self.assertEqual(
            errors, [], msg=f"bare sibling filename must be valid; errors={errors}"
        )

    def test_prefixed_same_epic_form_now_resolves(self) -> None:
        # covers: python-coder-depends-on-prefixed
        """New repo-relative prefixed spelling must resolve to the same-epic sibling.

        RED against the unmodified validator: the old candidate list
        concatenates parent / entry, producing a doubled, non-existent path
        such as ".../EPIC-Foo/tickets/00_inbox/epics/EPIC-Foo/06_TICKET-dep.md",
        so the dependency is reported missing even though it exists.
        """
        dep = self.epic_dir / "06_TICKET-dep.md"
        dep.write_text("---\n---\n", encoding="utf-8")
        entry = "tickets/00_inbox/epics/EPIC-Foo/06_TICKET-dep.md"
        errors = _fmv.validate_depends_on({"depends_on": [entry]}, self.ticket_path)
        self.assertEqual(
            errors,
            [],
            msg=(
                "prefixed same-epic path must resolve; a real dependency must not "
                f"be reported missing. errors={errors}"
            ),
        )

    def test_missing_under_both_forms_stays_invalid(self) -> None:
        # covers: python-coder-depends-on-prefixed
        """A dangling reference must be reported missing under EITHER spelling
        (no fail-open) — bare form.
        """
        errors_bare = _fmv.validate_depends_on(
            {"depends_on": ["99_TICKET-missing.md"]}, self.ticket_path
        )
        self.assertEqual(len(errors_bare), 1, msg=f"errors={errors_bare}")

        entry = "tickets/00_inbox/epics/EPIC-Foo/99_TICKET-missing.md"
        errors_prefixed = _fmv.validate_depends_on(
            {"depends_on": [entry]}, self.ticket_path
        )
        self.assertEqual(len(errors_prefixed), 1, msg=f"errors={errors_prefixed}")

    def test_cross_epic_prefixed_path_stays_invalid(self) -> None:
        # covers: python-coder-depends-on-prefixed
        """A prefixed path naming a DIFFERENT epic must not validate merely
        because a same-named file sits in this ticket's own epic folder — a
        naive basename-only resolution would accept this; the directory-name
        check must reject it.
        """
        samename = self.epic_dir / "99_TICKET-foo.md"
        samename.write_text("---\n---\n", encoding="utf-8")
        entry = "tickets/00_inbox/epics/EPIC-Other/99_TICKET-foo.md"
        errors = _fmv.validate_depends_on({"depends_on": [entry]}, self.ticket_path)
        self.assertEqual(
            len(errors),
            1,
            msg=(
                "cross-epic prefixed path incorrectly validated via a "
                f"same-named sibling in the ticket's own epic folder; errors={errors}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
