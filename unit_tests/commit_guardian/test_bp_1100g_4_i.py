"""
MODULE: unit_tests/commit_guardian/test_bp_1100g_4_i.py
COVERS: BP-1100g-4-i

GOAL: RED-baseline tests locking the accepted-paste invariance of the
    promise-versus-claim check (BP-1100g-4): a promise answered only by a
    pre-existing test that was given the ``# covers:`` / ``# angle:`` tag
    pair and changed in no other respect is NOT refused, the outcome for
    that pasted claim is byte-identical to the outcome for a genuine
    entry-point-invoking claim (including through a wholesale swap of the
    claiming test's body), and the success wording is exactly "promised and
    claimed" — never "reached", "proven", "verified", or "done". No path to
    that outcome may open, read, parse, tokenize, import-for-inspection, or
    pattern-match the claiming test's BODY (BO-2900a-2's boundary): the only
    permitted read of a test file is the tag collection BP-1100g-3's
    ``collect_test_tag_records`` already performs.

BUSINESS CONTEXT: BP-1100g-4 built ``extract_promised_kinds``,
    ``build_claim_index``, ``find_unmatched_promises``, and
    ``format_refusal`` in ``check_proof_promise_claim.py``. This AC is a
    constraint on that mechanism, not a new feature: it demands the
    comparison stay a pure function of two tag declarations, never of a
    test's source text, and pins the exact accepted-paste wording so a
    later change cannot quietly start reporting an execution fact from a
    string comparison.

ARCHITECTURE: Interface under test — same module as BP-1100g-4, imported
    here (for the non-subprocess tests) via the ``scripts/commit_guardian``
    symlink into the DEPLOYED copy, matching this repo's existing
    convention for commit_guardian modules:

    extract_promised_kinds, build_claim_index, find_unmatched_promises,
    format_refusal — see ``templates/scripts/commit_guardian/
    check_proof_promise_claim.py`` for the full contract (BP-1100g-4).

    The reachability test additionally exercises the DEPLOYED hook via
    ``run_hook.py`` as pre-commit would invoke it, under a fresh throwaway
    git repository (``git init`` in a tempdir) so ``find_project_root()``'s
    ``git rev-parse --show-toplevel`` resolves to the isolated tree rather
    than to this repository's own — meaning the scanned claim files are
    real, disposable, on-disk artifacts and never touch this repo's own
    test tree.

=== Red baseline ===

    Expected RED reason at authoring time: none of these tests require any
    NEW production code — ``check_proof_promise_claim.py`` (BP-1100g-4) was
    already implemented as a pure tag-only comparison with no body
    inspection anywhere in its call graph, so the invariance this AC pins
    may already hold by construction. If so, these tests serve as the
    permanent regression lock for that invariance and will report
    green-at-baseline; that outcome is itself the signal this AC exists to
    make legible, not a defect in the tests. See the completion comment for
    the actual verification-run outcome.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "scripts" / "commit_guardian"
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"

if str(_AC_STORE_DIR) not in sys.path:
    sys.path.insert(0, str(_AC_STORE_DIR))
if str(_COMMIT_GUARDIAN_DIR) not in sys.path:
    sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))

_SUBPROCESS_TIMEOUT_SECONDS = 60

from done_proof import collect_test_tag_records  # noqa: E402

_FORBIDDEN_OUTCOME_WORDS = ("reached", "proven", "verified", "done")


def _build_ticket_fixture(descriptors: list[dict]) -> str:
    """Build a real ``## Test Requirements`` ticket fragment via the REAL serializer.

    Mirrors exactly what ``generate_ticket_from_ac.py``'s
    ``_build_test_requirements_section`` emits: ``yaml.dump({"tests": ...},
    default_flow_style=False, allow_unicode=True, sort_keys=False)`` fenced
    under a ``## Test Requirements`` heading. Uses the real PyYAML serializer
    (never a hand-typed YAML string) per the fixture-authenticity convention.

    Args:
        descriptors: List of test descriptor dicts (the same shape
            ``generate_ticket_from_ac.py`` produces).

    Returns:
        A minimal but real ticket markdown fragment containing a properly
        fenced ``## Test Requirements`` section.
    """
    block = yaml.dump(
        {"tests": descriptors},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).rstrip()
    return "\n".join(
        [
            "---",
            "title: zz-bp-1100g-4-i fixture ticket",
            "---",
            "",
            "## Test Requirements",
            "",
            "```yaml",
            block,
            "```",
            "",
        ]
    )


def _write_claim_file(
    directory: Path, filename: str, functions: list[tuple[str, list[str], list[str]]]
) -> Path:
    """Write a real on-disk test file carrying covers/angle tags, tag-only body.

    Each entry in *functions* is ``(func_name, covers_ids, angles)``. Tags are
    placed on the line directly above the ``def`` — one of the three accepted
    positions the shared scanner recognises. The body is a fixed trivial
    ``assert True`` for every function, modelling a "pre-existing test given
    the claim and changed in no other respect" — the pasted-claim shape this
    AC's mechanism must not distinguish from a genuine one.

    Args:
        directory: Directory to write the file into.
        filename: File name to write.
        functions: List of (function name, covers ids, angles) tuples.

    Returns:
        Path to the written file.
    """
    lines: list[str] = []
    for func_name, covers_ids, angles in functions:
        for covers_id in covers_ids:
            lines.append(f"# covers: {covers_id}")
        for angle in angles:
            lines.append(f"# angle: {angle}")
        lines.append(f"def {func_name}():")
        lines.append("    assert True")
        lines.append("")
    path = directory / filename
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class TestPastedClaimIsNotRefusedAndWordedPromisedAndClaimed(unittest.TestCase):
    """test_spec: test_bp_1100g_4_i_pasted_claim_is_not_refused_and_is_worded_as_promised_and_claimed
    (angle: criterion). A promise answered only by a pre-existing,
    tag-only-modified test is not refused, and the outcome is exactly
    "promised and claimed" with none of reached/proven/verified/done."""

    def test_bp_1100g_4_i_pasted_claim_is_not_refused_and_is_worded_as_promised_and_claimed(
        self,
    ) -> None:
        # covers: BP-1100g-4-i
        # angle: criterion
        """A plan promising 'reachability' for one stated behaviour, answered
        only by a pre-existing test given the tag pair and changed in no
        other respect, is NOT refused and is worded exactly 'promised and
        claimed'."""
        from check_proof_promise_claim import (
            build_claim_index,
            extract_promised_kinds,
            find_unmatched_promises,
            format_refusal,
        )

        ac_id = "ZZ-BP1100G4I-DEMO1"
        behaviour_text = "the zz demo one widget is reached the way the product is really used"
        ticket_content = _build_ticket_fixture(
            [
                {
                    "name": "test_zz_demo1_reachability",
                    "file": "unit_tests/zz/test_demo1.py",
                    "covers": [ac_id],
                    "asserts": behaviour_text,
                    "framework": "unittest",
                    "type": "integration",
                    "angle": "reachability",
                }
            ]
        )

        promises = extract_promised_kinds(ticket_content)
        self.assertEqual(
            {(p["ac_id"], p["angle"]) for p in promises},
            {(ac_id, "reachability")},
            f"extract_promised_kinds must recover the promised pair: got {promises!r}",
        )

        with tempfile.TemporaryDirectory() as tmp:
            test_root = Path(tmp)
            _write_claim_file(
                test_root,
                "test_demo1_pasted_claim.py",
                [("test_demo1_direct_import_pre_existing", [ac_id], ["reachability"])],
            )
            records = collect_test_tag_records(test_root)

        claims = build_claim_index(records)
        self.assertEqual(
            claims.get(ac_id),
            {"reachability"},
            f"a pasted-tag test must still register a claim: got {claims!r}",
        )

        violations = find_unmatched_promises(promises, claims)
        self.assertEqual(
            violations,
            [],
            f"a promise answered by a pasted-tag pre-existing test must not "
            f"be refused: {violations!r}",
        )

        refusal = format_refusal(violations)
        self.assertEqual(
            refusal,
            "promised and claimed",
            f"the success outcome must be worded exactly 'promised and claimed': {refusal!r}",
        )
        lowered = refusal.lower()
        for forbidden in _FORBIDDEN_OUTCOME_WORDS:
            self.assertNotIn(
                forbidden,
                lowered,
                f"refusal text must never use the word {forbidden!r}: {refusal!r}",
            )


class TestOutcomeIsByteIdenticalUnderAWholesaleBodySwap(unittest.TestCase):
    """test_spec: test_bp_1100g_4_i_outcome_is_byte_identical_under_a_wholesale_body_swap
    (angle: real_artifact). Real on-disk test files, three different bodies,
    same tag pair — the outcome bytes must never move."""

    def test_bp_1100g_4_i_outcome_is_byte_identical_under_a_wholesale_body_swap(
        self,
    ) -> None:
        # covers: BP-1100g-4-i
        # angle: real_artifact
        """Write real test files to disk carrying the same tag — a genuine
        entry-point-invoking body, an unrelated body, and a third wholesale
        replacement — and assert the check's outcome bytes are identical
        across all three. Any implementation that inspects the claiming
        test's body fails this."""
        from check_proof_promise_claim import (
            build_claim_index,
            extract_promised_kinds,
            find_unmatched_promises,
            format_refusal,
        )

        ac_id = "ZZ-BP1100G4I-SWAP"
        angle = "reachability"
        behaviour_text = "the zz swap widget is reached the way the product is really used"
        ticket_content = _build_ticket_fixture(
            [
                {
                    "name": "test_zz_swap",
                    "file": "unit_tests/zz/test_swap.py",
                    "covers": [ac_id],
                    "asserts": behaviour_text,
                    "framework": "unittest",
                    "type": "integration",
                    "angle": angle,
                }
            ]
        )
        promises = extract_promised_kinds(ticket_content)
        self.assertTrue(promises, f"the fixture ticket must yield a promise: {promises!r}")

        def _outcome_for_content(content: str) -> str:
            with tempfile.TemporaryDirectory() as tmp:
                test_root = Path(tmp)
                (test_root / "test_zz_swap_claim.py").write_text(content, encoding="utf-8")
                records = collect_test_tag_records(test_root)
            claims = build_claim_index(records)
            violations = find_unmatched_promises(promises, claims)
            return format_refusal(violations)

        # The tag pair must sit directly above the `def` line in every
        # variant (one of the three accepted positions) — any statement
        # (e.g. an import) between the tags and the def would orphan the
        # tag, so imports/helpers are placed BEFORE the tag block.
        genuine_content = (
            "import subprocess\n"
            "import sys\n"
            f"# covers: {ac_id}\n"
            f"# angle: {angle}\n"
            "def test_zz_swap_genuine_entry_point():\n"
            "    result = subprocess.run([sys.executable, '-c', 'pass'], check=False)\n"
            "    assert result.returncode == 0\n"
        )
        unrelated_content = (
            f"# covers: {ac_id}\n"
            f"# angle: {angle}\n"
            "def test_zz_swap_unrelated():\n"
            "    x = 1 + 1\n"
            "    assert x == 2\n"
        )
        wholesale_third_content = (
            "class HelperNotATest:\n"
            "    def compute(self):\n"
            "        return object()\n"
            "\n"
            "\n"
            f"# covers: {ac_id}\n"
            f"# angle: {angle}\n"
            "def test_zz_swap_third_wholesale():\n"
            "    helper = HelperNotATest()\n"
            "    assert helper.compute() is not None\n"
        )

        outcome_genuine = _outcome_for_content(genuine_content)
        outcome_unrelated = _outcome_for_content(unrelated_content)
        outcome_third = _outcome_for_content(wholesale_third_content)

        self.assertEqual(
            outcome_genuine,
            "promised and claimed",
            f"a matched promise must not be refused: {outcome_genuine!r}",
        )
        self.assertEqual(
            outcome_genuine.encode("utf-8"),
            outcome_unrelated.encode("utf-8"),
            "the outcome bytes must be identical regardless of the claiming "
            f"test's body: genuine={outcome_genuine!r} unrelated={outcome_unrelated!r}",
        )
        self.assertEqual(
            outcome_genuine.encode("utf-8"),
            outcome_third.encode("utf-8"),
            "the outcome bytes must stay identical through a wholesale body "
            f"swap: genuine={outcome_genuine!r} third={outcome_third!r}",
        )


class TestInvarianceHoldsThroughTheDeployedHook(unittest.TestCase):
    """test_spec: test_bp_1100g_4_i_invariance_holds_through_the_deployed_hook
    (angle: reachability). PRODUCTION ENTRY POINT: the invariance must hold
    on the path that actually gates a commit, not only in the library."""

    def _run_deployed_hook(
        self, deployed_run_hook: Path, deployed_hook: Path, repo: Path, ticket_path: Path
    ) -> subprocess.CompletedProcess:
        """Invoke the deployed hook via run_hook.py exactly as pre-commit would.

        Args:
            deployed_run_hook: Path to the deployed ``run_hook.py`` wrapper.
            deployed_hook: Path to the deployed ``check_proof_promise_claim.py``.
            repo: Working directory — a throwaway git repository so
                ``find_project_root()`` resolves to it rather than to this
                repository's own root.
            ticket_path: Path to the staged ticket file to pass as argv.

        Returns:
            The completed subprocess result.
        """
        return subprocess.run(
            [sys.executable, str(deployed_run_hook), str(deployed_hook), str(ticket_path)],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )

    def test_bp_1100g_4_i_invariance_holds_through_the_deployed_hook(self) -> None:
        # covers: BP-1100g-4-i
        # angle: reachability
        """A pasted-claim case and a genuine-claim case, each run through the
        real deployed hook under an isolated throwaway git repository,
        produce identical exit codes and identical output — both worded
        exactly 'promised and claimed'."""
        deployed_run_hook = _REPO_ROOT / ".leafcutter" / "scripts" / "commit_guardian" / "run_hook.py"
        deployed_hook = (
            _REPO_ROOT / ".leafcutter" / "scripts" / "commit_guardian" / "check_proof_promise_claim.py"
        )
        self.assertTrue(
            deployed_run_hook.is_file(),
            f"deployed run_hook.py wrapper not found at {deployed_run_hook}",
        )
        self.assertTrue(
            deployed_hook.is_file(),
            f"deployed check_proof_promise_claim.py not found at {deployed_hook} — "
            "a missing deployed module is a failure, not a reason to skip",
        )

        ac_id = "ZZ-BP1100G4I-DEPLOYEDINVARIANCE"
        angle = "reachability"
        behaviour_text = (
            "the zz deployed invariance widget is reached the way the "
            "product is really used"
        )
        ticket_fixture = _build_ticket_fixture(
            [
                {
                    "name": "test_zz_deployed_invariance",
                    "file": "unit_tests/zz/test_deployed_invariance.py",
                    "covers": [ac_id],
                    "asserts": behaviour_text,
                    "framework": "unittest",
                    "type": "integration",
                    "angle": angle,
                }
            ]
        )

        def _git_init(repo: Path) -> None:
            subprocess.run(
                ["git", "init", "-q"],
                cwd=str(repo),
                check=True,
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            )

        # Case A: pasted claim — a pre-existing-style test given only the tag.
        with tempfile.TemporaryDirectory() as tmp_a:
            repo_a = Path(tmp_a)
            _git_init(repo_a)
            ticket_a = repo_a / "TICKET-zz-bp1100g4i-pasted.md"
            ticket_a.write_text(ticket_fixture, encoding="utf-8")
            claim_a = repo_a / "test_zz_pasted.py"
            claim_a.write_text(
                f"# covers: {ac_id}\n"
                f"# angle: {angle}\n"
                "def test_zz_pasted_direct_import_pre_existing():\n"
                "    assert True\n",
                encoding="utf-8",
            )
            result_a = self._run_deployed_hook(deployed_run_hook, deployed_hook, repo_a, ticket_a)

        # Case B: genuine claim — a test that actually invokes a real entry point.
        with tempfile.TemporaryDirectory() as tmp_b:
            repo_b = Path(tmp_b)
            _git_init(repo_b)
            ticket_b = repo_b / "TICKET-zz-bp1100g4i-genuine.md"
            ticket_b.write_text(ticket_fixture, encoding="utf-8")
            claim_b = repo_b / "test_zz_genuine.py"
            # The tag pair must sit directly above the `def` line (one of
            # the three accepted positions) — imports go BEFORE the tags so
            # they do not orphan the tag block.
            claim_b.write_text(
                "import subprocess\n"
                "import sys\n"
                f"# covers: {ac_id}\n"
                f"# angle: {angle}\n"
                "def test_zz_genuine_invokes_real_entry_point():\n"
                "    result = subprocess.run([sys.executable, '-c', 'pass'], check=False)\n"
                "    assert result.returncode == 0\n",
                encoding="utf-8",
            )
            result_b = self._run_deployed_hook(deployed_run_hook, deployed_hook, repo_b, ticket_b)

        self.assertEqual(
            result_a.returncode,
            0,
            f"pasted-claim case must not be refused. stdout={result_a.stdout!r} "
            f"stderr={result_a.stderr!r}",
        )
        self.assertEqual(
            result_b.returncode,
            0,
            f"genuine-claim case must not be refused. stdout={result_b.stdout!r} "
            f"stderr={result_b.stderr!r}",
        )
        self.assertEqual(
            result_a.returncode,
            result_b.returncode,
            "the deployed hook's exit code must be identical for a pasted "
            "claim and a genuine claim",
        )
        self.assertEqual(
            result_a.stdout,
            result_b.stdout,
            "the deployed hook's output must be byte-identical for a pasted "
            f"claim and a genuine claim: A={result_a.stdout!r} B={result_b.stdout!r}",
        )
        self.assertEqual(
            result_a.stdout.strip(),
            "promised and claimed",
            f"the deployed hook's success wording must be exactly 'promised "
            f"and claimed': {result_a.stdout!r}",
        )


if __name__ == "__main__":
    unittest.main()
