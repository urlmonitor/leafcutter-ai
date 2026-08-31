"""
MODULE: unit_tests/commit_guardian/test_bp_1100g_4.py
COVERS: BP-1100g-4

GOAL: RED test stubs for the promise-versus-claim gate — a commit-time check
    that refuses a piece of work whose plan promised a kind of proof (a
    Test Requirements descriptor's ``angle`` value) for a stated behaviour,
    but whose test tree carries no matching claim (a ``# covers:`` +
    ``# angle:`` pair on the same test function) for that (ac_id, angle)
    pair. The promise set is the denominator: a kind never promised is never
    named in a refusal, and a plan promising nothing is never refused.

BUSINESS CONTEXT: BP-1100g-3 built the CLAIM side (the second tag axis,
    ``collect_test_tag_records`` in ``scripts/ac_store/done_proof.py``,
    collected from real on-disk test files). This ticket builds the PROMISE
    side (the ``## Test Requirements`` descriptors a ticket/AC declares) and
    the comparison between the two. The hard boundary (BO-2900a-2): reading a
    test FILE to collect its tag is the scanner's job and is permitted;
    opening, parsing, tokenizing, importing-for-inspection, or regexing a
    test's BODY to judge what it does is forbidden on every path to the
    outcome. This check only ever consults two authored declarations: the
    promised (ac_id, angle) pairs from a ticket's ``## Test Requirements``
    block, and the claimed (ac_id, angle) pairs ``collect_test_tag_records``
    already collects.

ARCHITECTURE: Interface contract under test (to be implemented by
    python-coder in ``templates/scripts/commit_guardian/check_proof_promise_claim.py``,
    imported here — for the non-"_deployed"-suffixed tests — via the
    ``scripts/commit_guardian`` symlink into the DEPLOYED copy, matching this
    repo's existing convention for commit_guardian modules (see
    ``unit_tests/commit_guardian/test_bo2500b5_done_proof_default_scan_root.py``).
    That means these "unit" tests only go green once python-coder has both
    authored the module under ``templates/`` AND run
    ``python scripts/build.py --target-dir .`` to redeploy it):

    extract_promised_kinds(ticket_content: str) -> list[dict]
        Parses the fenced YAML block under a ticket's own
        ``## Test Requirements`` heading (the same ``tests:`` array shape
        ``generate_ticket_from_ac.py`` emits: ``name``, ``file``, ``covers``
        (list[str]), ``asserts``, ``framework``, ``type``, ``angle``).
        Returns one promise dict per (descriptor, covers-id) pair:
            {"ac_id": str, "angle": str, "behaviour": str}
        ``behaviour`` is the descriptor's own ``asserts`` text (Scope
        correction 3's fallback: the AC leaf + this per-descriptor text
        stands in for a true per-Then-clause reference). A descriptor with
        no ``angle`` or no ``covers`` entries contributes no promise.

    build_claim_index(records: list[dict]) -> dict[str, set[str]]
        Given the per-function records ``collect_test_tag_records`` already
        produces (``{"covers": list[str], "angles": list[str], ...}``),
        returns ``{ac_id: {claimed angle, ...}}``. A claim exists only when a
        SINGLE record (one test function) carries BOTH a covers id and an
        angle together — a function with covers but no angle tag (or an
        angle but no covers tag) contributes no claim for either axis alone.

    find_unmatched_promises(promises: list[dict], claims: dict[str, set[str]]) -> list[dict]
        The promise set is the denominator: iterates PROMISES only, never
        the claim set or the full permitted-angle vocabulary. For every
        promised (ac_id, angle) not present in
        ``claims.get(ac_id, set())``, emits exactly one violation dict
        matching the ticket's ``config_schema_fragment.refusal_entry``
        shape:
            {"ac_id": str, "behaviour": str, "missing_kind": str}
        An angle that was never promised for a given ac_id never appears in
        the output, for that ac_id or any other.

    format_refusal(violations: list[dict]) -> str
        Human-readable text. Empty ``violations`` -> exactly
        ``"promised and claimed"`` (Wording section: the outcome is
        established, never worded as reached / proven / verified / done).
        Non-empty -> one line per violation naming the ac_id, the behaviour,
        and the missing_kind by name (actionable: "the reader has to be
        able to go and write the specific missing test").

    main(argv: list[str] | None = None) -> int
        CLI entry point. ``argv`` is the list of staged ticket ``.md`` file
        paths (the pre-commit "pass_filenames" convention — the literal
        command line named by this AC's test_spec is
        ``run_hook.py check_proof_promise_claim.py <staged paths>``). Reads
        each ticket, extracts its promised kinds, scans the project's test
        tree (default: project root, matching check_done_proof.py's own
        default) via ``done_proof.collect_test_tag_records`` for the claim
        side, and prints ``format_refusal()``'s output. Returns 1 when any
        violation is found, 0 otherwise (including when no ticket promises
        anything at all).

    Hook registration (REGISTRATION IS PART OF THE WORK): the hook id
    ``check-proof-promise-claim`` (following this repo's
    ``check_<module>.py`` -> ``check-<module-with-dashes>`` id convention,
    e.g. ``check_done_proof.py`` -> ``check-done-proof``) must appear in
    ``templates/scripts/commit_guardian/commit_guardian.json``'s ``hooks``
    array, so that after a build it also appears in the deployed
    ``scripts/commit_guardian/commit_guardian.json`` (via the
    ``scripts/commit_guardian -> ../.leafcutter/scripts/commit_guardian``
    symlink) — an unregistered gate never runs.

=== Red baseline ===

    RED today: ``check_proof_promise_claim.py`` does not exist anywhere
    (neither under ``templates/`` nor deployed), so the module-level import
    below raises ModuleNotFoundError for every non-"_deployed" test, and the
    deployed-hook / hook-registration assertions in the two integration
    tests fail for the same underlying reason (nothing to import, nothing
    registered, nothing deployed).
"""

from __future__ import annotations

import json
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

# The permitted angle-kind vocabulary, read fresh from the single authoritative
# source (BP-1100g-1 / config/ac_store_schema.json) via done_proof's own
# loader — never restated as a hand-typed literal here (the exact anti-drift
# discipline BP-1100g-3's own DECISION HISTORY calls out).
from done_proof import (  # noqa: E402
    _load_permitted_angle_kinds,
    collect_test_tag_records,
)

# ...but pass the schema path EXPLICITLY rather than relying on the loader's
# module-level default. `_PERMITTED_ANGLES_SCHEMA_PATH` is built from
# `Path(__file__).resolve()` with hand-counted parents, so it resolves against
# whichever copy of done_proof.py is already in sys.modules. When a
# earlier-collected sibling test (e.g.
# test_bo2500b5_done_proof_default_scan_root.py) has imported check_done_proof
# through the `scripts/commit_guardian -> .leafcutter/scripts/commit_guardian`
# symlink, done_proof resolves inside `.leafcutter/`, the default path becomes
# `.leafcutter/config/ac_store_schema.json` (which is not deployed), and the
# loader fail-softs to an EMPTY set. That made this file pass in isolation and
# fail in directory order — the sys.modules-shadowing trap recorded as KI-TQ-004.
#
# Passing the real path keeps the anti-drift intent intact (still the one
# authoritative file, still no hand-typed literal) while making the read
# independent of import order. The underlying resolution defect in done_proof.py
# is REAL and out of scope here (this ticket's out_of_scope forbids touching it);
# it is filed separately — in the deployed layout every valid angle is reported
# as unrecognised.
_AC_STORE_SCHEMA_PATH = _REPO_ROOT / "config" / "ac_store_schema.json"


def _build_ticket_fixture(descriptors: list[dict]) -> str:
    """Build a real ``## Test Requirements`` ticket fragment via the REAL serializer.

    Mirrors exactly what ``generate_ticket_from_ac.py``'s
    ``_build_test_requirements_section`` emits: ``yaml.dump({"tests": ...},
    default_flow_style=False, allow_unicode=True, sort_keys=False)`` fenced
    under a ``## Test Requirements`` heading. Uses the real PyYAML serializer
    (never a hand-typed YAML string) per the fixture-authenticity convention —
    a hand-typed fixture reproduces the author's own mental model of the
    format, which is exactly the bias that let files_touched ship as a
    silent no-op across seven tickets (EPIC-PhantomDoneFilesTouched).

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
            "title: zz-bp-1100g-4 fixture ticket",
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


def _write_claim_file(directory: Path, filename: str, functions: list[tuple[str, list[str], list[str]]]) -> Path:
    """Write a real on-disk test file carrying covers/angle tags, project-convention style.

    Each entry in *functions* is ``(func_name, covers_ids, angles)``. Tags are
    placed on the line directly above the ``def`` — one of the three accepted
    positions the shared scanner recognises — so this is scanned by the real
    ``collect_test_tag_records`` exactly as a real contributor would write it.

    Args:
        directory: Directory to write the file into.
        filename: File name (must start with ``test_`` for pytest discovery,
            though discovery is irrelevant here — only the scanner reads it).
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


class TestPromiseWithoutClaimIsRefusedNamingWorkBehaviourAndKind(unittest.TestCase):
    """test_spec: test_bp_1100g_4_promise_without_claim_is_refused_naming_work_behaviour_and_kind
    (angle: criterion). Also covers AC-1, AC-2, AC-3 of BP-1100g-4's Gherkin:
    a claim exists for the first kind only, so the second is refused, and the
    refusal names the piece of work (ac_id), the stated behaviour, and the
    missing kind."""

    def test_bp_1100g_4_promise_without_claim_is_refused_naming_work_behaviour_and_kind(
        self,
    ) -> None:
        # covers: BP-1100g-4
        # angle: criterion
        """AC-1/AC-2/AC-3: a plan promising criterion AND reachability for one
        stated behaviour, with a test tree claiming criterion only, is
        refused — and the refusal names the ac_id, the behaviour, and the
        word 'reachability' by name."""
        from check_proof_promise_claim import (
            extract_promised_kinds,
            find_unmatched_promises,
            format_refusal,
        )

        ac_id = "ZZ-BP1100G4-DEMO1"
        behaviour_text = "the widget parses zz demo one input correctly"
        ticket_content = _build_ticket_fixture(
            [
                {
                    "name": "test_zz_demo1_criterion",
                    "file": "unit_tests/zz/test_demo1.py",
                    "covers": [ac_id],
                    "asserts": behaviour_text,
                    "framework": "unittest",
                    "type": "unit",
                    "angle": "criterion",
                },
                {
                    "name": "test_zz_demo1_reachability",
                    "file": "unit_tests/commit_guardian/test_demo1.py",
                    "covers": [ac_id],
                    "asserts": behaviour_text,
                    "framework": "unittest",
                    "type": "integration",
                    "angle": "reachability",
                },
            ]
        )

        promises = extract_promised_kinds(ticket_content)
        self.assertEqual(
            {(p["ac_id"], p["angle"]) for p in promises},
            {(ac_id, "criterion"), (ac_id, "reachability")},
            f"extract_promised_kinds must recover both promised (ac_id, angle) "
            f"pairs from the real fenced YAML block: got {promises!r}",
        )

        with tempfile.TemporaryDirectory() as tmp:
            test_root = Path(tmp)
            _write_claim_file(
                test_root,
                "test_demo1_claim.py",
                [("test_has_criterion_claim_only", [ac_id], ["criterion"])],
            )
            records = collect_test_tag_records(test_root)

        from check_proof_promise_claim import build_claim_index

        claims = build_claim_index(records)
        self.assertEqual(
            claims.get(ac_id),
            {"criterion"},
            f"a test tagged covers:{ac_id} + angle:criterion only must claim "
            f"exactly {{'criterion'}} for {ac_id}: got {claims!r}",
        )

        violations = find_unmatched_promises(promises, claims)
        self.assertEqual(
            len(violations),
            1,
            f"exactly one promised kind (reachability) has no matching claim: {violations!r}",
        )
        violation = violations[0]
        self.assertEqual(violation["ac_id"], ac_id)
        self.assertEqual(violation["missing_kind"], "reachability")
        self.assertIn(behaviour_text, violation["behaviour"])

        refusal = format_refusal(violations)
        self.assertIn(ac_id, refusal)
        self.assertIn("reachability", refusal)
        self.assertIn(behaviour_text, refusal)
        # Wording — the outcome is never worded as reached, proven, verified,
        # or done, and never the generic placeholder an implementer writes
        # first.
        lowered = refusal.lower()
        for forbidden in ("reached", "proven", "verified"):
            self.assertNotIn(
                forbidden,
                lowered,
                f"refusal text must never use the word {forbidden!r}: {refusal!r}",
            )
        self.assertNotIn(
            "proof requirements not met",
            lowered,
            f"refusal text must not be the generic placeholder: {refusal!r}",
        )


class TestUnpromisedKindIsNeverNamedInARefusal(unittest.TestCase):
    """test_spec: test_bp_1100g_4_unpromised_kind_is_never_named_in_a_refusal
    (angle: boundary). Also covers AC-4 and AC-5: the denominator rule across
    three shapes — promise-one, promise-all, promise-none."""

    def _promises_for(self, ac_id: str, angle_behaviours: list[tuple[str, str]]) -> list[dict]:
        """Build real promise dicts via extract_promised_kinds + the real serializer."""
        from check_proof_promise_claim import extract_promised_kinds

        descriptors = [
            {
                "name": f"test_zz_{ac_id.lower().replace('-', '_')}_{angle}",
                "file": "unit_tests/zz/test_boundary.py",
                "covers": [ac_id],
                "asserts": behaviour,
                "framework": "unittest",
                "type": "unit",
                "angle": angle,
            }
            for angle, behaviour in angle_behaviours
        ]
        ticket_content = _build_ticket_fixture(descriptors)
        return extract_promised_kinds(ticket_content)

    def test_bp_1100g_4_unpromised_kind_is_never_named_in_a_refusal(self) -> None:
        # covers: BP-1100g-4
        # angle: boundary
        """AC-4/AC-5: a plan promising one kind, a plan promising every
        permitted kind, and a plan promising none. No kind outside the
        promise set appears in any refusal, and the promise-none case
        produces no refusal at all."""
        from check_proof_promise_claim import (
            build_claim_index,
            find_unmatched_promises,
            format_refusal,
        )

        permitted_angles = _load_permitted_angle_kinds(_AC_STORE_SCHEMA_PATH)
        self.assertTrue(
            permitted_angles,
            "the permitted angle-kind schema must be loadable for this test "
            f"to be meaningful ({_AC_STORE_SCHEMA_PATH})",
        )

        # --- Shape (a): promise ONE kind, claim NONE. ---
        ac_one = "ZZ-BP1100G4-BOUND-ONE"
        promises_one = self._promises_for(ac_one, [("criterion", "one behaviour")])
        violations_one = find_unmatched_promises(promises_one, {})
        self.assertEqual(len(violations_one), 1)
        self.assertEqual(violations_one[0]["missing_kind"], "criterion")
        refusal_one = format_refusal(violations_one)
        self.assertIn("criterion", refusal_one)
        for other_angle in permitted_angles - {"criterion"}:
            self.assertNotIn(
                other_angle,
                refusal_one,
                f"a kind never promised for {ac_one} ({other_angle!r}) must never "
                f"appear in its refusal: {refusal_one!r}",
            )

        # --- Shape (b): promise EVERY permitted kind, claim all of them. ---
        ac_all = "ZZ-BP1100G4-BOUND-ALL"
        promises_all = self._promises_for(
            ac_all, [(angle, "all-kinds behaviour") for angle in sorted(permitted_angles)]
        )
        with tempfile.TemporaryDirectory() as tmp:
            test_root = Path(tmp)
            _write_claim_file(
                test_root,
                "test_boundary_all_claim.py",
                [("test_claims_every_kind", [ac_all], sorted(permitted_angles))],
            )
            records_all = collect_test_tag_records(test_root)
        claims_all = build_claim_index(records_all)
        self.assertEqual(claims_all.get(ac_all), set(permitted_angles))
        violations_all = find_unmatched_promises(promises_all, claims_all)
        self.assertEqual(
            violations_all,
            [],
            f"a plan whose every promised kind has a matching claim must not "
            f"be refused: {violations_all!r}",
        )
        self.assertEqual(
            format_refusal(violations_all),
            "promised and claimed",
            "the success outcome must be worded exactly 'promised and claimed' "
            "(never reached/proven/verified/done)",
        )

        # --- Shape (c): promise NONE. ---
        promises_none = self._promises_for("ZZ-BP1100G4-BOUND-NONE", [])
        self.assertEqual(promises_none, [])
        violations_none = find_unmatched_promises(promises_none, {})
        self.assertEqual(
            violations_none,
            [],
            "a plan promising nothing must produce no refusal at all",
        )
        self.assertEqual(format_refusal(violations_none), "promised and claimed")


class TestKnownBadInputBlocksThroughTheDeployedHook(unittest.TestCase):
    """test_spec: test_bp_1100g_4_known_bad_input_blocks_through_the_deployed_hook
    (angle: reachability). PRODUCTION ENTRY POINT test, per BO-2900a-2 / this
    AC's own test_spec: run the deployed hook via the deployed run_hook.py
    wrapper against a real staged ticket, and assert the hook id is
    registered in the hooks manifest — an unregistered gate never runs."""

    def test_bp_1100g_4_known_bad_input_blocks_through_the_deployed_hook(self) -> None:
        # covers: BP-1100g-4
        # angle: reachability
        """AC-2/AC-3 (reachability): the deployed hook, invoked exactly as
        pre-commit would invoke it, exits non-zero and names the missing
        kind by name when a staged ticket promises a kind for an ac_id that
        no test in the tree claims. Also asserts hook-manifest registration
        directly (registration is part of the work)."""
        manifest_path = _REPO_ROOT / "scripts" / "commit_guardian" / "commit_guardian.json"
        self.assertTrue(
            manifest_path.is_file(),
            f"hooks manifest not found at {manifest_path} — run "
            "`python scripts/build.py --target-dir .` first",
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hooks_list = manifest.get("hooks_manifest", {}).get("hooks", [])
        hook_ids = {h.get("id") for h in hooks_list}
        self.assertIn(
            "check-proof-promise-claim",
            hook_ids,
            f"hook id 'check-proof-promise-claim' is not registered in "
            f"{manifest_path} (found ids: {sorted(i for i in hook_ids if i)}) — "
            "an unregistered gate never runs and passes its own grep-shaped "
            "tests",
        )

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

        with tempfile.TemporaryDirectory() as tmp:
            ticket_path = Path(tmp) / "TICKET-zz-bp1100g4-deployed.md"
            ticket_path.write_text(
                _build_ticket_fixture(
                    [
                        {
                            "name": "test_zz_neverclaimed_reachability",
                            "file": "unit_tests/zz/test_neverclaimed.py",
                            "covers": ["ZZ-BP1100G4-NEVERCLAIMED"],
                            "asserts": "the never-claimed behaviour is reachable end to end",
                            "framework": "unittest",
                            "type": "integration",
                            "angle": "reachability",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(deployed_run_hook),
                    str(deployed_hook),
                    str(ticket_path),
                ],
                cwd=str(_REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            )

        combined_output = result.stdout + result.stderr
        self.assertNotEqual(
            result.returncode,
            0,
            "the deployed hook must exit non-zero when a staged ticket "
            f"promises a kind with no matching claim anywhere in the test "
            f"tree. stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            "reachability",
            combined_output,
            f"the refusal must name the missing kind by name. output={combined_output!r}",
        )
        self.assertIn(
            "ZZ-BP1100G4-NEVERCLAIMED",
            combined_output,
            f"the refusal must name the piece of work (ac_id). output={combined_output!r}",
        )


class TestRealGeneratedPlanPipedIntoTheRealCheck(unittest.TestCase):
    """test_spec: test_bp_1100g_4_real_generated_plan_piped_into_the_real_check
    (angle: seam). Also covers AC-6: both sides of the comparison are real,
    independently-produced declarations — the real generator's ticket output
    and the real scanner's claim output — never hand-built promise or claim
    dicts."""

    def test_bp_1100g_4_real_generated_plan_piped_into_the_real_check(self) -> None:
        # covers: BP-1100g-4
        # angle: seam
        """AC-6: generate a real ticket via generate_ticket_from_ac.py
        --dry-run for a real AC in the store (BP-1100g-3, which authors a
        multi-angle test_spec), scan a real on-disk test tree with the real
        BP-1100g-3 scanner, and feed both real outputs into
        find_unmatched_promises — never a hand-built promise or claim dict."""
        from check_proof_promise_claim import (
            build_claim_index,
            extract_promised_kinds,
            find_unmatched_promises,
        )

        generator = _AC_STORE_DIR / "generate_ticket_from_ac.py"
        self.assertTrue(generator.is_file(), f"real generator not found at {generator}")

        result = subprocess.run(
            [sys.executable, str(generator), "--ac", "BP-1100g-3", "--dry-run"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            result.returncode,
            0,
            "the real ticket generator must dry-run successfully for a real "
            f"AC in the store. stdout={result.stdout!r} stderr={result.stderr!r}",
        )

        promises = extract_promised_kinds(result.stdout)
        promised_angles = {p["angle"] for p in promises if p["ac_id"] == "BP-1100g-3"}
        self.assertTrue(
            promised_angles,
            "the real generator's dry-run output for BP-1100g-3 must contain "
            f"at least one promised angle for BP-1100g-3 itself: {promises!r}",
        )

        # Real claim side: a real on-disk test file, written to a fresh temp
        # tree, scanned by the real collect_test_tag_records. Deliberately
        # omits ONE of the promised angles so the seam produces a real,
        # observable violation rather than a vacuous always-empty result.
        missing_angle = sorted(promised_angles)[0]
        claimed_angles = sorted(promised_angles - {missing_angle})
        with tempfile.TemporaryDirectory() as tmp:
            test_root = Path(tmp)
            _write_claim_file(
                test_root,
                "test_seam_claim.py",
                [("test_claims_all_but_one", ["BP-1100g-3"], claimed_angles)],
            )
            records = collect_test_tag_records(test_root)

        claims = build_claim_index(records)
        violations = find_unmatched_promises(promises, claims)
        violation_kinds = {
            (v["ac_id"], v["missing_kind"]) for v in violations if v["ac_id"] == "BP-1100g-3"
        }
        self.assertIn(
            ("BP-1100g-3", missing_angle),
            violation_kinds,
            f"the deliberately-unclaimed promised angle {missing_angle!r} for "
            f"BP-1100g-3 must surface as a real violation from the real "
            f"generator + real scanner seam: {violations!r}",
        )


if __name__ == "__main__":
    unittest.main()
