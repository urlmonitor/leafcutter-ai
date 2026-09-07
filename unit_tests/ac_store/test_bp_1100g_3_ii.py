"""
MODULE: unit_tests/ac_store/test_bp_1100g_3_ii.py
COVERS: BP-1100g-3-ii

GOAL: Prove the taught proof-kind set resolves to the SAME set from every
    layout done_proof.py is imported from, and that an unreadable source is
    reported as unreadable rather than as "nothing is taught".

THE DEFECT THIS PINS DOWN. BP-1100g-3 resolved config/ac_store_schema.json with
    a hand-counted `Path(__file__).resolve().parent.parent.parent`. The distance
    from the module to the repository root is NOT the same in the two layouts it
    runs in:

        <repo>/scripts/ac_store/done_proof.py               root is parents[2]
        <repo>/.leafcutter/scripts/ac_store/done_proof.py   root is parents[3]

    so the deployed copy resolved to `.leafcutter/config/ac_store_schema.json`,
    which does not exist. `_load_permitted_angle_kinds` fail-softs to an empty
    set on a read failure, and an empty permitted set makes EVERY declared kind
    unrecognised — so from the deployed copy, which is what the commit-time and
    merge-time checks actually run, a VALID `criterion` tag was reported as a
    violation. Measured 2026-08-26 against 2f740cc4: source tree returned all
    seven kinds, deployed copy returned none.

WHY BP-1100g-3'S OWN REACHABILITY TEST DID NOT CATCH IT. That test exercised
    `collect_test_tag_records` through the deployed copy and passed. The sibling
    function added in the same commit reads a DIFFERENT file by a DIFFERENT path
    and was never reached from that layout. The angle was right; the coverage was
    partial. One function proven reachable, one assumed.

WHY EACH TEST BELOW EXISTS — the four are not interchangeable:

    deployed      the two resolutions must agree. Compared to EACH OTHER, never
                  to a hand-typed list, because restating the seven kinds here
                  would reintroduce the second vocabulary BP-1100g-1 exists to
                  eliminate.
    real_artifact the observable defect: a real on-disk test file declaring a
                  taught kind, scanned through the deployed copy, must not be
                  reported. This is the one that was red before the fix.
    failure       the negative control that stops the fix being "report
                  nothing". A genuinely untaught kind must STILL be reported by
                  both. Without it, a loader returning every conceivable string
                  would pass the other three.
    boundary      "could not read" must be distinguishable from "read, found
                  none". That boundary is exactly where the defect hid: the
                  failure presented as every test being wrong rather than as one
                  file being unreadable.

FIXTURE AUTHENTICITY: the deployed layouts below are REAL directory trees
    written to disk with the real module copied into them, imported in a FRESH
    subprocess whose sys.path is restricted to that directory. Asserting about
    the path expression instead would pass on a path that does not resolve
    (BO-2900a-2), and importing in-process would let an already-cached
    done_proof shadow the copy under test (KI-TQ-004).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
_SCHEMA_SRC = _REPO_ROOT / "config" / "ac_store_schema.json"
_SUBPROCESS_TIMEOUT = 90

# Modules that must travel together for done_proof to import at all.
_MODULE_FILES = ("done_proof.py", "test_enforcement.py")


def _run_in_subprocess(module_dir: Path, body: str) -> dict:
    """Import done_proof from *module_dir* in a fresh process and return its JSON result.

    A fresh interpreter per call is the point: it guarantees the copy under
    test is the one imported, with no possibility of a previously-imported
    done_proof being served from sys.modules.
    """
    # Assembled line-by-line rather than as an indented triple-quoted block:
    # `body` is multi-line, and substituting it into an indented template before
    # textwrap.dedent runs destroys the common prefix dedent keys on, producing
    # an IndentationError in the child. Joining unindented lines has no such
    # ordering hazard.
    driver = "\n".join(
        [
            "import json, sys",
            f"sys.path.insert(0, {str(module_dir)!r})",
            "import done_proof",
            body,
            'print("___RESULT___" + json.dumps(result, default=str))',
        ]
    )
    proc = subprocess.run(
        [sys.executable, "-c", driver],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    if "___RESULT___" not in proc.stdout:
        raise AssertionError(
            f"driver produced no result.\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}"
        )
    payload = proc.stdout.split("___RESULT___", 1)[1].strip()
    parsed = json.loads(payload)
    parsed["_stderr"] = proc.stderr
    return parsed


def _build_deployed_layout(root: Path, *, layout: str) -> Path:
    """Create a REAL deployed tree of the named shape; return its ac_store dir.

    THE LAYOUT CHOICE IS THE DISCRIMINATING VARIABLE — read before changing it.
    The pre-fix code resolved the schema as ``parents[2]`` of the module, which
    from ``<root>/.leafcutter/scripts/ac_store/`` lands on
    ``<root>/.leafcutter/config/``. So a fixture that puts the schema THERE is
    satisfied by the broken code and proves nothing. An earlier revision of this
    file did exactly that and 3 of these 4 tests passed against the unfixed
    module; only running them against it revealed the fixture was the problem.

    ``worktree``   ``<root>/config/`` holds the schema and ``.leafcutter/config/``
                   does NOT. This is the repository's real shape, and the one
                   that DISCRIMINATES: pre-fix resolves to the absent
                   ``.leafcutter/config/`` and loads nothing; post-fix walks up
                   and finds ``<root>/config/``.

    ``self_hosted`` no ancestor holds ``config/`` at all and the schema is
                   deployed beside the scripts, as ``.leafcutter/`` sits BESIDE
                   the package in the self-hosting workspace. This layout does
                   NOT discriminate — the old parents[2] arithmetic happens to
                   land on the deployed copy — but it is the layout that proves
                   the deploy-manifest half of the fix, without which the
                   upward search has nothing to find here.

    ``unreadable``  no schema anywhere, to separate "could not read" from
                   "read, found none".
    """
    module_dir = root / ".leafcutter" / "scripts" / "ac_store"
    module_dir.mkdir(parents=True)
    for name in _MODULE_FILES:
        shutil.copy2(_AC_STORE_DIR / name, module_dir / name)

    if layout == "worktree":
        cfg = root / "config"
        cfg.mkdir(parents=True)
        shutil.copy2(_SCHEMA_SRC, cfg / "ac_store_schema.json")
    elif layout == "self_hosted":
        cfg = root / ".leafcutter" / "config"
        cfg.mkdir(parents=True)
        shutil.copy2(_SCHEMA_SRC, cfg / "ac_store_schema.json")
    elif layout != "unreadable":
        raise ValueError(f"unknown layout: {layout!r}")
    return module_dir


class TestRecognisedKindSetIsIdenticalFromBothLayouts(unittest.TestCase):
    """test_spec: test_bp_1100g_3_ii_recognised_kind_set_is_identical_from_both_layouts
    (angle: deployed)."""

    def test_bp_1100g_3_ii_recognised_kind_set_is_identical_from_both_layouts(self) -> None:
        # covers: BP-1100g-3-ii
        # angle: deployed
        """The set of taught kinds must be the same from the working copy and
        from the installed copy. Asserted by comparing the two resolutions to
        EACH OTHER — never to a restated list, which would be the second
        vocabulary BP-1100g-1 forbids."""
        read_kinds = "result = {'kinds': sorted(done_proof._load_permitted_angle_kinds())}"
        from_source = _run_in_subprocess(_AC_STORE_DIR, read_kinds)

        self.assertTrue(
            from_source["kinds"],
            "the working copy must resolve a non-empty taught set — if this is "
            "empty every comparison below is vacuously true",
        )

        # BOTH deployed shapes must agree with source. 'worktree' is the one
        # that discriminates against the pre-fix arithmetic; 'self_hosted' is
        # the one that would fail without the deploy-manifest half of the fix.
        for layout in ("worktree", "self_hosted"):
            with self.subTest(layout=layout):
                with tempfile.TemporaryDirectory() as tmp:
                    module_dir = _build_deployed_layout(Path(tmp), layout=layout)
                    from_deployed = _run_in_subprocess(module_dir, read_kinds)
                self.assertEqual(
                    from_deployed["kinds"],
                    from_source["kinds"],
                    f"the installed copy ({layout} layout) must recognise exactly "
                    "the kinds the working copy does; a difference means the two "
                    "disagree about what is taught",
                )


class TestTaughtKindIsNeverReportedFromTheDeployedCopy(unittest.TestCase):
    """test_spec: test_bp_1100g_3_ii_a_taught_kind_is_never_reported_from_the_installed_copy
    (angle: real_artifact)."""

    def test_bp_1100g_3_ii_a_taught_kind_is_never_reported_from_the_installed_copy(self) -> None:
        # covers: BP-1100g-3-ii
        # angle: real_artifact
        """A REAL test file on disk declaring a taught kind, scanned through the
        installed copy, must produce no report. This is the defect as a user
        meets it: before the fix every correctly-tagged test in the repository
        came back reported."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module_dir = _build_deployed_layout(root, layout="worktree")

            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_well_tagged.py").write_text(
                textwrap.dedent(
                    """\
                    def test_properly_tagged():
                        # covers: ZZ-G3II-REAL
                        # angle: criterion
                        assert True
                    """
                ),
                encoding="utf-8",
            )

            outcome = _run_in_subprocess(
                module_dir,
                "from pathlib import Path\n"
                f"records = done_proof.collect_test_tag_records(Path({str(tests_dir)!r}))\n"
                "result = {'records': records, "
                "'reported': done_proof.find_unrecognised_angle_tags(records)}",
            )

        self.assertTrue(
            outcome["records"],
            "fixture sanity: the scanner must have found the test function, "
            "otherwise the assertion below passes on an empty scan",
        )
        self.assertEqual(
            outcome["reported"],
            [],
            "a test declaring a TAUGHT kind must never be reported from the "
            f"installed copy: {outcome['reported']}",
        )


class TestUntaughtKindIsStillReportedFromBothLayouts(unittest.TestCase):
    """test_spec: test_bp_1100g_3_ii_a_genuinely_untaught_kind_is_still_reported_from_both
    (angle: failure)."""

    def test_bp_1100g_3_ii_a_genuinely_untaught_kind_is_still_reported_from_both(self) -> None:
        # covers: BP-1100g-3-ii
        # angle: failure
        """The negative control. Making the check report nothing would satisfy
        the other tests; this one fails on that. A kind genuinely outside the
        taught set must still be reported, naming the test and the value, by
        BOTH resolutions."""
        bad_record = (
            "records = [{'file': 't.py', 'function': 'test_bad', "
            "'covers': ['ZZ-G3II-BAD'], 'angles': ['zzz_definitely_not_taught']}]\n"
            "result = {'reported': done_proof.find_unrecognised_angle_tags(records)}"
        )

        from_source = _run_in_subprocess(_AC_STORE_DIR, bad_record)
        with tempfile.TemporaryDirectory() as tmp:
            module_dir = _build_deployed_layout(Path(tmp), layout="worktree")
            from_deployed = _run_in_subprocess(module_dir, bad_record)

        for label, outcome in (("source", from_source), ("deployed", from_deployed)):
            with self.subTest(layout=label):
                self.assertEqual(
                    len(outcome["reported"]),
                    1,
                    f"an untaught kind must still be reported from the {label} "
                    f"copy: {outcome['reported']}",
                )
                entry = outcome["reported"][0]
                self.assertEqual(entry["function"], "test_bad")
                self.assertEqual(entry["angle"], "zzz_definitely_not_taught")


class TestUnreadableSourceIsNotTreatedAsAnEmptySet(unittest.TestCase):
    """test_spec: test_bp_1100g_3_ii_an_unreadable_source_is_reported_as_unreadable_not_as_empty
    (angle: boundary)."""

    def test_bp_1100g_3_ii_an_unreadable_source_is_reported_as_unreadable_not_as_empty(self) -> None:
        # covers: BP-1100g-3-ii
        # angle: boundary
        """When the taught set cannot be read at all, the outcome must be "could
        not check" — not "nothing is taught, so everything is wrong". The old
        behaviour turned one unreadable file into a report against every tagged
        test in the tree, which is indistinguishable from the check being
        broken, and the reasonable response to that is to switch it off."""
        with tempfile.TemporaryDirectory() as tmp:
            # No schema deployed AND no config/ in any ancestor.
            module_dir = _build_deployed_layout(Path(tmp), layout="unreadable")
            outcome = _run_in_subprocess(
                module_dir,
                "records = [{'file': 't.py', 'function': 'test_x', "
                "'covers': ['ZZ-G3II-UNREADABLE'], 'angles': ['criterion']}]\n"
                "result = {'kinds': sorted(done_proof._load_permitted_angle_kinds()), "
                "'reported': done_proof.find_unrecognised_angle_tags(records)}",
            )

        self.assertEqual(
            outcome["kinds"],
            [],
            "fixture sanity: this layout must genuinely fail to resolve the "
            "schema, otherwise the assertions below prove nothing",
        )
        self.assertEqual(
            outcome["reported"],
            [],
            "an unresolvable taught set must report NOTHING rather than "
            "reporting every declared kind as unrecognised — the false-positive "
            f"flood this AC exists to prevent: {outcome['reported']}",
        )
        self.assertIn(
            "could not check",
            outcome["_stderr"],
            "the unreadable case must say so explicitly, so 'could not check' "
            "is never silently read as 'everything checked out'. stderr was: "
            f"{outcome['_stderr']!r}",
        )


if __name__ == "__main__":
    unittest.main()
