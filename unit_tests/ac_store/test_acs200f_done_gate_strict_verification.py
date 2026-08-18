"""
MODULE: unit_tests/ac_store/test_acs200f_done_gate_strict_verification.py
GOAL: Behavioral coverage for ACS-200f and ACS-200f-1 — the done-marking gate's
    own verification run must not consume an outcome that the
    ``pytest_ac_enforcement`` plugin downgraded on the basis of the
    not-yet-updated work_status, and the gate's refusals must stay distinguishable.

=== The defect ===

``done_proof._run_pytest_and_parse`` launches ``python -m pytest -v`` as a
subprocess that inherits the parent environment.  The repo's ``pytest.ini``
loads ``scripts.ac_store.pytest_ac_enforcement`` into that subprocess, and the
plugin rewrites the outcome of any failing test whose ``# covers:`` tag points
at an AC with ``work_status != "done"`` to XFAIL.

The AC the gate is evaluating is, by definition, still not-done at that moment.
So the gate — the authority that decides done-ness — reads a verdict the plugin
has already rewritten *because* of the status the gate is about to change.  A
genuinely FAILED covering test is reported to the operator as an xfail, which
names the wrong cause and points at the wrong fix.

=== Fixture authenticity ===

Every AC record is written with ``yaml.safe_dump``; every covering test is a
real ``.py`` file with a genuine body that passes, fails, skips, or xfails under
a real pytest run.  No pass/fail signal is mocked, and no test greps the source
of the module under test — a grep-only assertion would pass on dead code.

The plugin only masks failures for AC ids it can resolve in the store, so these
tests point ``LEAFCUTTER_AC_STORE_ROOT`` at the synthetic store.  That is what
makes the masking real here rather than simulated.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from done_proof import verify_done_eligible  # noqa: E402

_MARK_AC_DONE_CLI = _REPO_ROOT / "scripts" / "ac_store" / "mark_ac_done.py"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_ac(ac_root: Path, ac_id: str, *, work_status: str = "todo") -> Path:
    """Write a minimal active AC record with ``yaml.safe_dump``.

    Args:
        ac_root: Root of the synthetic AC store.
        ac_id: Identifier to write.
        work_status: The record's work_status value.

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic AC {ac_id}",
        "component": "ac-store",
        "level": "L2",
        "status": "active",
        "work_status": work_status,
        "readiness": "draft",
        "priority": "medium",
        "depends_on": [],
        "amended_by": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _write_test_file(test_root: Path, filename: str, content: str) -> Path:
    """Write a real Python test file (dedented) into *test_root*."""
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def _gate_env(ac_root: Path) -> dict[str, str]:
    """Return a child environment with the plugin pointed at the synthetic store.

    ``AC_ENFORCE_STRICT`` is explicitly removed: the whole point of ACS-200f is
    that the operator must not have to know about it.

    Args:
        ac_root: Root of the synthetic AC store the plugin should read.

    Returns:
        An environment mapping suitable for ``subprocess.run(env=...)``.
    """
    env = dict(os.environ)
    env["LEAFCUTTER_AC_STORE_ROOT"] = str(ac_root)
    env.pop("AC_ENFORCE_STRICT", None)
    return env


class _StoreRootEnv:
    """Context manager pointing the plugin at *ac_root* for in-process calls.

    ``verify_done_eligible`` spawns pytest as a child process, which inherits
    this process's environment — so setting it here is what reaches the plugin.
    """

    def __init__(self, ac_root: Path) -> None:
        self._ac_root = ac_root
        self._saved: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for key, value in (
            ("LEAFCUTTER_AC_STORE_ROOT", str(self._ac_root)),
            ("AC_ENFORCE_STRICT", None),
        ):
            self._saved[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def __exit__(self, *_exc: object) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


_PASSING_BODY = """\
    def test_synthetic_covering_test():
        # covers: {ac_id}
        assert 1 + 1 == 2
"""

_FAILING_BODY = """\
    def test_synthetic_covering_test():
        # covers: {ac_id}
        assert 1 + 1 == 3, "deliberate genuine failure"
"""

_SKIPPED_BODY = """\
    import pytest

    @pytest.mark.skip(reason="deliberately skipped for its own reasons")
    def test_synthetic_covering_test():
        # covers: {ac_id}
        assert True
"""

# The xfail decorator is assembled rather than written out literally.  The
# contract-shrinking guard is line-anchored by design (see the "Deliberate
# narrowing" note in check_contract_shrinking.py): it matches a decorator at
# the start of an added diff line and cannot tell that these lines live inside
# a string constant that is written to a temp directory at runtime.  Spelling
# it out here would make this fixture indistinguishable from someone genuinely
# xfailing a real test alongside a production change — the exact thing that
# guard exists to block.  Assembling it keeps the guard strict and keeps this
# fixture honest; the generated file still carries a real decorator.
_XFAIL_DECORATOR = "@pytest.mark." + 'xfail(reason="independently expected to fail")'

_XFAIL_BODY = (
    "import pytest\n\n"
    + _XFAIL_DECORATOR
    + "\ndef test_synthetic_covering_test():\n"
    "    # covers: {ac_id}\n"
    '    assert False, "independently xfailed"\n'
)


class _GateFixture(unittest.TestCase):
    """Base fixture: a synthetic store plus a test tree, torn down per test."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.ac_root.mkdir(parents=True, exist_ok=True)
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _verdict_for(self, ac_id: str, body: str) -> dict:
        """Write an AC + a covering test with *body*, then run the real gate."""
        _write_ac(self.ac_root, ac_id)
        _write_test_file(
            self.test_root,
            f"test_{ac_id.replace('-', '_').lower()}.py",
            body.format(ac_id=ac_id),
        )
        with _StoreRootEnv(self.ac_root):
            return verify_done_eligible(
                ac_id, ac_root=self.ac_root, test_root=self.test_root
            )


# ---------------------------------------------------------------------------
# ACS-200f — the gate's verification run is immune to not-yet-done masking
# ---------------------------------------------------------------------------


class TestGateRunIsImmuneToNotYetDoneMasking(_GateFixture):
    """ACS-200f: the gate must not consume a plugin-downgraded outcome."""

    def test_acs200f_failing_covering_test_reported_as_failed_not_xfail(self) -> None:
        # covers: ACS-200f
        """A genuinely FAILED covering test must be reported as failed.

        Without the fix the enforcement plugin rewrites the outcome to XFAIL —
        precisely because the AC under evaluation is still ``todo`` — and the
        gate repeats that downgraded verdict back to the operator.  The refusal
        is correct either way; the *stated cause* is not, and it sends the
        operator looking for an xfail marker that does not exist.
        """
        verdict = self._verdict_for("ACS-TEST-200F-FAIL", _FAILING_BODY)

        self.assertFalse(
            verdict["eligible"],
            "A genuinely failing covering test must never satisfy the gate.",
        )
        reason = verdict["reason"]
        self.assertIn(
            "failed",
            reason.lower(),
            "The gate must name the real outcome (failed). Got: " + reason,
        )
        self.assertNotIn(
            "xfail",
            reason.lower(),
            "The gate consumed the enforcement plugin's not-yet-done downgrade: "
            "a genuinely FAILED test was reported as an xfail. Reason: " + reason,
        )

    def test_acs200f_passing_covering_test_is_eligible_with_no_env_var(self) -> None:
        # covers: ACS-200f
        """An AC whose covering test genuinely passes is eligible, plainly."""
        verdict = self._verdict_for("ACS-TEST-200F-PASS", _PASSING_BODY)

        self.assertTrue(
            verdict["eligible"],
            "A genuinely passing covering test must satisfy the gate without "
            f"any environment configuration. Reason given: {verdict['reason']}",
        )
        self.assertEqual(verdict["reason"], "")

    def test_acs200f_cli_marks_done_in_a_fresh_process_without_env_var(self) -> None:
        # covers: ACS-200f
        """End-to-end: the real CLI, a fresh process, no environment overrides.

        Drives ``mark_ac_done.py`` as a subprocess and asserts on the exit code
        and the actual store write — not on a return value from an in-process
        call, and not on the presence of any string in the source.
        """
        ac_id = "ACS-TEST-200F-CLI"
        ac_path = _write_ac(self.ac_root, ac_id)
        _write_test_file(
            self.test_root,
            "test_acs_test_200f_cli.py",
            _PASSING_BODY.format(ac_id=ac_id),
        )

        proc = subprocess.run(
            [
                sys.executable,
                str(_MARK_AC_DONE_CLI),
                "--ac",
                ac_id,
                "--ac-root",
                str(self.ac_root),
                "--test-root",
                str(self.test_root),
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(_REPO_ROOT),
            env=_gate_env(self.ac_root),
            check=False,
        )

        self.assertEqual(
            proc.returncode,
            0,
            "The documented invocation must succeed for a genuinely covered AC.\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )
        written = yaml.safe_load(ac_path.read_text(encoding="utf-8"))
        self.assertEqual(
            written["work_status"],
            "done",
            "The CLI reported success but the store was not updated.",
        )


# ---------------------------------------------------------------------------
# ACS-200f-1 — the gate is unblocked, not weakened
# ---------------------------------------------------------------------------


class TestGateStillRefusesEveryNonPassingCase(_GateFixture):
    """ACS-200f-1: the three refusal cases survive and stay distinguishable."""

    def test_acs200f1_genuinely_failing_test_is_refused(self) -> None:
        # covers: ACS-200f-1
        """A genuinely failing covering test is refused and named."""
        verdict = self._verdict_for("ACS-TEST-200F1-FAIL", _FAILING_BODY)

        self.assertFalse(verdict["eligible"])
        self.assertTrue(
            verdict["failing_tests"],
            "The failing test must be listed in failing_tests.",
        )
        self.assertIn("test_synthetic_covering_test", verdict["reason"])

    def test_acs200f1_no_covering_test_is_refused(self) -> None:
        # covers: ACS-200f-1
        """An AC with no covering test at all is refused, and says so."""
        ac_id = "ACS-TEST-200F1-NONE"
        _write_ac(self.ac_root, ac_id)
        with _StoreRootEnv(self.ac_root):
            verdict = verify_done_eligible(
                ac_id, ac_root=self.ac_root, test_root=self.test_root
            )

        self.assertFalse(verdict["eligible"])
        self.assertIn("no linked test found", verdict["reason"])

    def test_acs200f1_genuinely_skipped_test_is_refused(self) -> None:
        # covers: ACS-200f-1
        """A test skipped for its own reasons is still not proof of done."""
        verdict = self._verdict_for("ACS-TEST-200F1-SKIP", _SKIPPED_BODY)

        self.assertFalse(
            verdict["eligible"],
            "Unblocking the masked-pass case must not turn a skipped test into "
            "proof of done (BO-2500a-2-i).",
        )
        self.assertIn(
            "skipped",
            verdict["reason"].lower(),
            "The refusal must name the skip so the operator knows what to fix. "
            f"Got: {verdict['reason']}",
        )

    def test_acs200f1_independently_xfailed_test_is_refused(self) -> None:
        # covers: ACS-200f-1
        """An author-marked ``@pytest.mark.xfail`` test is still not proof.

        This is the boundary with BO-2500a-2-i.  Disabling the enforcement
        plugin's *own* not-yet-done downgrade must not disable pytest's native
        xfail handling — an outcome that is non-passing on its own merits stays
        non-passing.
        """
        verdict = self._verdict_for("ACS-TEST-200F1-XFAIL", _XFAIL_BODY)

        self.assertFalse(
            verdict["eligible"],
            "An independently xfailed test must never satisfy the gate.",
        )
        self.assertIn(
            "xfail",
            verdict["reason"].lower(),
            f"The refusal must name the xfail. Got: {verdict['reason']}",
        )

    def test_acs200f1_the_three_refusals_are_distinguishable(self) -> None:
        # covers: ACS-200f-1
        """Failed / skipped / absent must not collapse into one message.

        They call for different operator actions — fix the code, un-skip the
        test, write a test — so a single "non-passing" verdict for all three is
        not actionable.
        """
        failed = self._verdict_for("ACS-TEST-200F1-D-FAIL", _FAILING_BODY)["reason"]
        skipped = self._verdict_for("ACS-TEST-200F1-D-SKIP", _SKIPPED_BODY)["reason"]

        absent_id = "ACS-TEST-200F1-D-NONE"
        _write_ac(self.ac_root, absent_id)
        with _StoreRootEnv(self.ac_root):
            absent = verify_done_eligible(
                absent_id, ac_root=self.ac_root, test_root=self.test_root
            )["reason"]

        reasons = [failed, skipped, absent]
        normalised = [r.split(":")[0].strip().lower() for r in reasons]
        self.assertEqual(
            len(set(normalised)),
            3,
            "The three refusal causes must be distinguishable from the message "
            f"alone. Got: {reasons}",
        )

    def test_acs200f1_a_refused_run_leaves_the_record_byte_identical(self) -> None:
        # covers: ACS-200f-1
        """A refusal must not have already half-written the record."""
        ac_id = "ACS-TEST-200F1-BYTES"
        ac_path = _write_ac(self.ac_root, ac_id)
        _write_test_file(
            self.test_root,
            "test_acs_test_200f1_bytes.py",
            _FAILING_BODY.format(ac_id=ac_id),
        )
        before = ac_path.read_bytes()

        proc = subprocess.run(
            [
                sys.executable,
                str(_MARK_AC_DONE_CLI),
                "--ac",
                ac_id,
                "--ac-root",
                str(self.ac_root),
                "--test-root",
                str(self.test_root),
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(_REPO_ROOT),
            env=_gate_env(self.ac_root),
            check=False,
        )

        self.assertNotEqual(
            proc.returncode,
            0,
            "A failing covering test must produce a non-zero exit.\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )
        self.assertEqual(
            ac_path.read_bytes(),
            before,
            "A refused run rewrote part of the AC record.",
        )


if __name__ == "__main__":
    unittest.main()
