"""
Tests for TQ-600a-13 -- "A test the documentation says the default run skips is a
test the default run skips."

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this).

The owner chose the "exclusion branch": the behaviour changes, not the docs.

1. A pytest marker named exactly ``manual`` is registered in pytest.ini's
   ``markers =`` key (a DIRECT ini key -- never inside addopts).
2. Every collected test whose function name (the node id up to any ``[``)
   ends in ``_MANUAL`` is treated as marked ``manual`` AUTOMATICALLY -- the
   suffix is the rule, no enumeration, no per-test decorator.
3. A plain default collection (``python -m pytest tests/ unit_tests/
   --collect-only -q``, reading the repo's real pytest.ini exactly as CI
   does) DESELECTS every ``manual`` test.
4. The explicit opt-in is ``-m manual``: it collects exactly the ``manual``
   tests and nothing else. ``-m "manual or not manual"`` collects everything
   (this is how these tests derive the unfiltered population).
5. The mechanism lives in the repo's own config (pytest.ini + a plugin
   registered with ``-p scripts....`` in addopts, mirroring the existing
   plugins). Nothing in these tests names the plugin module.

Every assertion is made on node ids a REAL ``pytest --collect-only``
subprocess produced -- never on a grep of pytest.ini or a README. The two
READMEs are read only to learn WHAT they claim.

OUT OF SCOPE (TQ-600a-13-i, deliberately unmet in this PR): the scheduled
cadence that runs the opt-in set. Also not written: the test_spec descriptor
``a_suffixed_test_that_runs_today_is_observed_running``. It is a pre-change
red baseline for the documents branch; under the exclusion branch it asserts
the exact opposite of the required end state, so it can only be wrong after
this change.
======================================================================
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUFFIX = "_MANUAL"
DOCS = (
    REPO_ROOT / "scripts" / "suite_performance" / "README.md",
    REPO_ROOT / "docs" / "testing" / "README.md",
)
_CLAIM_VERB = re.compile(r"exclud|deselect|not collected|omit|skipp", re.IGNORECASE)


def _collect(args, cwd, extra_env=None):
    """Run a real ``pytest --collect-only -q`` subprocess; return (returncode, ids, text)."""
    env = dict(os.environ)
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("PYTEST_ADDOPTS", None)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env.update(extra_env or {})
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    ids = [ln.strip() for ln in proc.stdout.splitlines() if "::" in ln and not ln.startswith(("=", " "))]
    return proc.returncode, ids, proc.stdout + proc.stderr


def _is_manual(node_id):
    return node_id.split("[")[0].endswith(SUFFIX)


def _claim_sentences():
    """(doc_path, sentence) for each sentence that claims _MANUAL tests are excluded."""
    found = []
    for doc in DOCS:
        text = re.sub(r"\s+", " ", doc.read_text(encoding="utf-8"))
        for sentence in re.split(r"(?<=[.;])\s+", text):
            if SUFFIX in sentence and _CLAIM_VERB.search(sentence):
                found.append((doc.relative_to(REPO_ROOT).as_posix(), sentence.strip()))
    return found


def _disagreement(default_ids, claims):
    """Empty string when the claimed exclusion holds for ``default_ids``; else a
    report naming BOTH the specific tests and the specific document sentence(s)."""
    leaked = sorted(i for i in default_ids if _is_manual(i))
    if not leaked or not claims:
        return ""
    sentences = "; ".join(f'{doc}: "{s}"' for doc, s in claims)
    return f"documents claim exclusion [{sentences}] but the default collection contains: {', '.join(leaked)}"


def _write_project(tmp, new_manual_name):
    (tmp / "test_sample.py").write_text(
        f"def test_regular_one():\n    assert True\n\n\ndef {new_manual_name}():\n    assert True\n",
        encoding="utf-8",
    )


class TestTq600a13(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Three real full-suite collections, shared by every test below.
        cls.default_rc, cls.default_ids, cls.default_out = _collect(["tests/", "unit_tests/"], REPO_ROOT)
        cls.optin_rc, cls.optin_ids, cls.optin_out = _collect(["tests/", "unit_tests/", "-m", "manual"], REPO_ROOT)
        cls.all_rc, cls.all_ids, cls.all_out = _collect(
            ["tests/", "unit_tests/", "-m", "manual or not manual"], REPO_ROOT
        )
        cls.all_manual = sorted(i for i in cls.all_ids if _is_manual(i))

    def test_ac13_default_collection_contains_no_manual_tests(self):
        # covers: TQ-600a-13
        # angle: reachability
        """AC-13: a default collection performed the way CI does contains no `_MANUAL` test.

        Must be implemented: a default collection deselects every `_MANUAL` test.
        """
        self.assertTrue(self.default_ids, f"default collection collected nothing:\n{self.default_out[-800:]}")
        leaked = [i for i in self.default_ids if _is_manual(i)]
        self.assertEqual([], leaked[:10], f"{len(leaked)} _MANUAL test(s) in the default collection")

    def test_ac13_optin_and_default_partition_the_unfiltered_suite(self):
        # covers: TQ-600a-13
        # angle: boundary
        """AC-13: the exclusion is a partition, never a deletion.

        Must be implemented: `-m manual` collects exactly the `_MANUAL` tests; default and
        opt-in are disjoint and their union equals the unfiltered collection. The population
        is derived from the unfiltered collection, never hardcoded.
        """
        self.assertTrue(self.all_manual, f"unfiltered collection found no _MANUAL test:\n{self.all_out[-800:]}")
        self.assertEqual(
            self.all_manual, sorted(self.optin_ids), "opt-in `-m manual` must collect exactly every _MANUAL test"
        )
        default, optin = set(self.default_ids), set(self.optin_ids)
        self.assertEqual(set(), default & optin, "default and opt-in collections must be disjoint")
        self.assertEqual(set(self.all_ids), default | optin, "default + opt-in must equal the unfiltered collection")

    def test_ac13_documented_exclusion_agrees_with_the_real_default_collection(self):
        # covers: TQ-600a-13
        # angle: real_artifact
        """AC-13: what the two READMEs claim about `_MANUAL` matches what a collection did."""
        claims = _claim_sentences()
        self.assertTrue(claims, "neither README states a _MANUAL exclusion; the owner chose real deselection")
        self.assertEqual("", _disagreement(self.default_ids, claims))

    def test_ac13_the_comparison_fails_and_names_tests_and_sentence_when_they_disagree(self):
        # covers: TQ-600a-13
        # angle: discrimination
        """AC-13 must_catch: a comparison never seen to fail proves nothing.

        Control: the SAME project collected with NO mechanism DOES contain the `_MANUAL` test,
        and the comparison then fails naming that test id AND a document sentence (not a count).
        Also: an agreeing collection reports no disagreement.
        """
        name = f"test_control_{uuid.uuid4().hex[:8]}{SUFFIX}"
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            _write_project(tmp, name)
            (tmp / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
            _rc, ids, out = _collect([str(tmp), "-c", str(tmp / "pytest.ini")], tmp)
        self.assertTrue(any(i.endswith("::" + name) for i in ids), f"control must collect the test:\n{out[-600:]}")
        claims = _claim_sentences() or [("docs/testing/README.md", f"The pre-commit suite excludes `{SUFFIX}` tests.")]
        report = _disagreement(ids, claims)
        self.assertIn(name, report, "report must name the specific disagreeing test")
        self.assertIn(claims[0][1], report, "report must quote the specific document sentence")
        self.assertIn(claims[0][0], report, "report must name the document")
        self.assertEqual("", _disagreement([i for i in ids if not _is_manual(i)], claims))

    def test_ac13_an_accepted_but_ignored_selection_flag_does_not_fool_the_check(self):
        # covers: TQ-600a-13
        # angle: discrimination
        """AC-13 must_catch: a config that LOOKS like a deselection but has no effect.

        `--deselect=<id that matches nothing>` is accepted and ignored (the same class as
        `--strict-markers` inside addopts on pytest 9.0.3). The config text mentions _MANUAL and
        deselect, yet the `_MANUAL` test is still collected, so the check must still report it.
        """
        name = f"test_inert_{uuid.uuid4().hex[:8]}{SUFFIX}"
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            _write_project(tmp, name)
            ini = tmp / "pytest.ini"
            ini.write_text(f"[pytest]\naddopts = --deselect=nowhere/test_none.py::test_x{SUFFIX}\n", encoding="utf-8")
            _rc, ids, out = _collect([str(tmp), "-c", str(ini)], tmp)
        self.assertTrue(any(i.endswith("::" + name) for i in ids), f"inert flag must not deselect:\n{out[-600:]}")
        claims = [("docs/testing/README.md", f"The pre-commit suite excludes `{SUFFIX}` tests.")]
        self.assertIn(name, _disagreement(ids, claims))

    def test_ac13_a_newly_added_manual_test_is_excluded_by_the_suffix_alone(self):
        # covers: TQ-600a-13
        # angle: criterion
        """AC-13: the suffix is the rule, not an enumeration that rots.

        A brand-new, uniquely named `_MANUAL` test in a throwaway project, collected with the
        repo's REAL pytest.ini, is deselected by default (its sibling regular test is not) and
        is the only thing `-m manual` collects.
        """
        name = f"test_brand_new_{uuid.uuid4().hex[:8]}{SUFFIX}"
        real_ini = ["-c", str(REPO_ROOT / "pytest.ini"), "--rootdir", str(REPO_ROOT)]
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            _write_project(tmp, name)
            _rc, default_ids, out = _collect([str(tmp), *real_ini], REPO_ROOT)
            _rc2, optin_ids, out2 = _collect([str(tmp), *real_ini, "-m", "manual"], REPO_ROOT)
        self.assertTrue(any(i.endswith("::test_regular_one") for i in default_ids), f"regular test lost:\n{out[-600:]}")
        self.assertFalse(any(i.endswith("::" + name) for i in default_ids), "new _MANUAL test was NOT excluded")
        self.assertEqual([name], [i.split("::")[-1] for i in optin_ids], f"opt-in must pick only it:\n{out2[-600:]}")


if __name__ == "__main__":
    unittest.main()
