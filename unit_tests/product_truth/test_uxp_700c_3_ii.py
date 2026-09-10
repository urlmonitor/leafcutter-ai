"""
MODULE: test_uxp_700c_3_ii
GOAL: Pin the "a gate that did not run is reported, and never counts as a gate
    that passed" contract (UXP-700c-3-ii) onto the commit-guardian dispatch
    wrapper that starts the record's checker
    (docs/product-truth/scripts/validate_product_truth.py, DECLARED in
    templates/scripts/commit_guardian/commit_guardian.json's hooks_manifest
    as the check-product-truth-validate hook, entry: "python
    {{config.output_root}}/scripts/commit_guardian/run_hook.py
    docs/product-truth/scripts/validate_product_truth.py --quiet").
BUSINESS CONTEXT: UXP-700c-3-ii's own notes cite PRIOR ART already reproduced
    in this repo: check_ac_parent_covered_by.py printed a fail-open WARNING
    and exited 0 (a "checked and sound" shape) when it could not even import
    a helper it needed — the same defect class this AC guards against one
    level up, for a checker that never started at all (skipped / disabled /
    could-not-start), rather than one that started but could not finish its
    own inspection. The AC's notes are explicit: "Reuse GE-120's vocabulary
    here; do not mint a second one" — this ticket therefore extends
    check_outcome.py (the GE-120a-1 shared could-not-check vocabulary module)
    with a NEW outcome distinct from its existing OUTCOME_OK /
    OUTCOME_COULD_NOT_CHECK / OUTCOME_NOTHING_TO_INSPECT values, rather than
    overloading any of those for a check that never got the chance to run at
    all.

    WORKTREE NOTE (discovered during test authoring, 2026-09-09): this
    ticket's own architect-review comment states the checker is already
    "wired into commit_guardian ... check-product-truth-validate id in
    .pre-commit-config.yaml". Direct verification against THIS repo/branch
    (leafcutter-ai, epic/uxp-700-product-truth — the branch this ticket file
    and its `source_ac` YAML actually live on) shows that is not yet true
    here: `grep -c check-product-truth-validate .pre-commit-config.yaml`
    returns 0, and the AC's own direct parent, UXP-700c-3 ("the record's
    checker runs by itself"), still shows every one of its own agents as
    `needed` in its ticket
    (tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/24_TICKET-20260909-UXP-700c-3.md)
    — matching UXP-700c-3's OWN "EVIDENCE" note verbatim ("There is no entry
    for it in .pre-commit-config.yaml and no CI step. It is not wired to
    anything."). What DOES already exist here, and is what this ticket's own
    fix actually touches per architect-review's design note, is the
    DECLARATIVE metadata layer: check-product-truth-validate is registered in
    templates/scripts/commit_guardian/commit_guardian.json's hooks_manifest
    (confirmed by direct read, 2026-09-09) — the same manifest run_hook.py
    already reads (for `tier`, via `_load_manifest_tiers()`) and where the
    "enabled" flag this ticket's disabled-reason test needs actually lives.
    Every test below therefore resolves the real checker identity against
    commit_guardian.json (the manifest — the layer this fix operates on),
    never against .pre-commit-config.yaml (the rendered, not-yet-synced
    projection UXP-700c-3 is separately responsible for).
ARCHITECTURE: Per architect-review (2026-09-09 17:18, this ticket's own
    Comments): the three "does not execute" reasons this AC names —
    skipped, disabled, could not start — are properties of the DISPATCH
    WRAPPER (run_hook.py) and the config it reads, NOT of
    validate_product_truth.py's own internals; "disabled" and "skipped" are
    observable BEFORE the checker script ever runs, and "could not start"
    can arise either at that same wrapper layer or inside run_hook.py's own
    subprocess dispatch. The canonical source for the wrapper in THIS repo
    (leafcutter-ai is the framework's own source; it uses
    scripts/commit_guardian/run_hook.py directly for its own dogfooded hooks
    — no `.leafcutter/` deployment prefix, since this repo is the source
    template being authored, not a build.py consumer) is
    templates/scripts/commit_guardian/run_hook.py — confirmed byte-for-byte
    identical (modulo line endings) to scripts/commit_guardian/run_hook.py,
    the copy THIS repo's own .pre-commit-config.yaml entries invoke for
    every OTHER already-wired hook (ADR-001 template/deployed parity).

    Required NEW symbols this ticket adds (none exist yet in either
    check_outcome.py or run_hook.py as of this test file's authoring —
    grep confirms zero hits for "not_run" / "OUTCOME_NOT_RUN" /
    "emit_not_run" anywhere in scripts/commit_guardian/ or
    templates/scripts/commit_guardian/ — every test below is expected to
    fail until python-coder adds them, in BOTH mirrored copies):

        check_outcome.OUTCOME_NOT_RUN: str = "not_run"

        check_outcome.emit_not_run(checker: str, reason: str) -> None
            Prints "RESULT: not_run checker=<checker> reason=<reason>" to
            stdout. `reason` MUST be one of "skipped", "disabled",
            "could_not_start" — the three reasons this AC's own Gherkin
            names verbatim. This is a DIFFERENT machine-readable `RESULT:`
            line than the ok/could_not_check/nothing_to_inspect vocabulary
            check_outcome.py already declares (AC-2: "that report is not
            the report produced when the record was checked and found
            sound") and it names the checker in the line itself (AC-3).

        run_hook.py's main(), extended to:
          * consult the hooks_manifest entry (commit_guardian.json, deployed
            beside run_hook.py, already read for `tier` by the existing
            _load_manifest_tiers()) for the target script's own `enabled`
            field (default True — mirrors every other enabled-flag consumer
            already in this component, e.g. check_hook_trigger_reachability.py's
            `entry.get("enabled") is False` convention) BEFORE resolving the
            worktree python or launching the delegated check at all.
            enabled: false -> emit_not_run(target, "disabled") and return
            without ever spawning the delegated check's own subprocess (a
            disabled check is an intentional operator decision — it must not
            itself fail the commit; only the report must distinguish it from
            a pass).
          * report emit_not_run(target, "could_not_start") when the
            delegated check's own process cannot actually be started (this
            test file exercises the "target script/module is missing"
            member of that condition — CPython's own "can't open file"
            exit, currently exit 2 with nothing on stdout and no RESULT:
            line at all, confirmed by direct execution against the current,
            unmodified file as of this test's authoring). This case DOES
            fail the commit — it is a genuine defect, not an operator
            choice — so the exit code must stay non-zero.

    Test-file layout (all four tests are "type: integration" per this AC's
    own test_spec/Test-Requirements entries — every test below invokes
    run_hook.py's REAL CLI via subprocess, never a bare import of an
    internal helper):
      * TestDisabledCheckerReportedAsNotRun — angle: failure. A COPY of
        run_hook.py + check_outcome.py (real files, copied verbatim so the
        test can supply its own commit_guardian.json without touching the
        repo's real manifest) is run against a synthetic "sound" checker
        script, with that checker's hooks_manifest entry carrying
        `"enabled": false`. Confirmed by direct execution (2026-09-09)
        that the CURRENT, unmodified run_hook.py ignores `enabled` entirely
        and simply runs the checker, printing its stdout with exit 0 — no
        RESULT: line at all. RED until the disabled-short-circuit exists.
      * TestUnstartableCheckerReportedAsNotRun — angle: failure. The REAL,
        unmodified templates/scripts/commit_guardian/run_hook.py (no
        copying needed — nothing about it is overridden) is invoked with a
        target script path that does not exist on disk. Confirmed by
        direct execution (2026-09-09) that the CURRENT, unmodified
        run_hook.py exits 2 with CPython's own "can't open file" message on
        stderr and NOTHING on stdout — no RESULT: line, no mention of
        "could_not_start". RED until the missing-target case is detected
        and reported through check_outcome's vocabulary.
      * TestNotRunReportDiffersFromCheckedAndSound — angle: boundary. Runs
        the SAME copied run_hook.py tree twice against the SAME synthetic
        checker script — once with its manifest entry disabled (not-run),
        once enabled (checked-and-sound) — and asserts the two runs'
        stdout are distinguishable from each other by more than exit code:
        the not-run run must carry the RESULT: not_run vocabulary and the
        checked-and-sound run must never carry it.
      * TestReachability — angle: reachability. Reads the REAL
        templates/scripts/commit_guardian/commit_guardian.json (a real
        on-disk artifact, not a hand-typed literal) to find
        check-product-truth-validate's own registered `entry:` command
        VERBATIM, extracts its checker-script argument tail
        ("docs/product-truth/scripts/validate_product_truth.py --quiet"),
        and replays that EXACT tail against a disabled-manifest copy of
        run_hook.py — proving the fix is reachable through the identical
        argument list a real commit will eventually trigger once
        UXP-700c-3 (this AC's own depends_on) syncs it into
        .pre-commit-config.yaml, naming the REAL production checker
        (validate_product_truth.py), not a synthetic stand-in.

        completion_manifest.reachability_entry_point_answer:
          result: resolved
          entry_point: "python templates/scripts/commit_guardian/run_hook.py
            <checker-args-copied-verbatim-from-commit_guardian.json's own
            check-product-truth-validate entry> (CLI via subprocess, main()
            guarded by if __name__ == '__main__':). This is the SAME
            dispatch wrapper every other already-wired hook in this repo's
            .pre-commit-config.yaml invokes (mirrored byte-for-byte, modulo
            line endings, at scripts/commit_guardian/run_hook.py). Per
            architect-review's 2026-09-09 comment on this ticket, the three
            'does not execute' reasons are properties of THIS wrapper's own
            dispatch, not of validate_product_truth.py's internals, so this
            wrapper — not the checker script — is the correct entry point
            to pin. The checker-arg tail is read from
            commit_guardian.json (the manifest this fix's own `enabled`
            flag lives on) rather than .pre-commit-config.yaml, because
            direct verification against this repo/branch found the hook
            declared in the manifest but not yet synced into
            .pre-commit-config.yaml — that sync is UXP-700c-3's own,
            separate, still-`needed` responsibility, not this AC's."
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CG_SRC = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_RUN_HOOK_SRC = _CG_SRC / "run_hook.py"
_CHECK_OUTCOME_SRC = _CG_SRC / "check_outcome.py"
_MANIFEST_SRC = _CG_SRC / "commit_guardian.json"

_SOUND_CHECKER_BODY = (
    "print('checked and sound')\n"
    "import sys\n"
    "sys.exit(0)\n"
)


def _copy_run_hook_tree(tmp: Path) -> Path:
    """Copy the REAL run_hook.py + check_outcome.py (canonical templates/
    source) into a fresh tempdir so a test can supply its own
    commit_guardian.json (read by run_hook.py from beside itself) without
    ever touching the repo's real manifest."""
    scripts_dir = tmp / "scripts_dir"
    scripts_dir.mkdir(parents=True)
    shutil.copy2(_RUN_HOOK_SRC, scripts_dir / "run_hook.py")
    shutil.copy2(_CHECK_OUTCOME_SRC, scripts_dir / "check_outcome.py")
    return scripts_dir


def _write_manifest(scripts_dir: Path, hook_entry: str, enabled: bool) -> None:
    manifest = {
        "hooks_manifest": {
            "hooks": [
                {
                    "id": "check-fixture-checker",
                    "entry": hook_entry,
                    "enabled": enabled,
                }
            ]
        }
    }
    (scripts_dir / "commit_guardian.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def _write_sound_checker(tmp: Path, relative_path: str) -> None:
    checker_path = tmp / relative_path
    checker_path.parent.mkdir(parents=True, exist_ok=True)
    checker_path.write_text(_SOUND_CHECKER_BODY, encoding="utf-8")


def _run_run_hook(scripts_dir: Path, cwd: Path, extra_args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(scripts_dir / "run_hook.py"), *extra_args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _real_check_product_truth_validate_entry() -> str:
    """Read the REAL, on-disk hooks_manifest entry for
    check-product-truth-validate out of commit_guardian.json (a real
    artifact, read verbatim — never hand-typed; Fixture Authenticity Rule).
    """
    manifest = json.loads(_MANIFEST_SRC.read_text(encoding="utf-8"))
    for hook in manifest.get("hooks_manifest", {}).get("hooks", []):
        if hook.get("id") == "check-product-truth-validate":
            return hook["entry"]
    raise AssertionError(
        "check-product-truth-validate is no longer registered in the real "
        f"{_MANIFEST_SRC} — this test must be updated, not deleted, if that "
        "hook is intentionally renamed/removed"
    )


class TestDisabledCheckerReportedAsNotRun(unittest.TestCase):
    """angle: failure — a checker disabled in configuration must be reported
    as not_run, naming the checker and the "disabled" reason, without
    itself failing the commit."""

    def test_disabled_record_checker_is_reported_as_not_run(self):
        # covers: UXP-700c-3-ii
        # angle: failure
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            scripts_dir = _copy_run_hook_tree(tmp)
            _write_sound_checker(tmp, "fixture/sound_checker.py")
            _write_manifest(
                scripts_dir,
                hook_entry="python run_hook.py fixture/sound_checker.py",
                enabled=False,
            )

            result = _run_run_hook(scripts_dir, tmp, ["fixture/sound_checker.py"])

        combined = result.stdout + result.stderr
        self.assertIn(
            "RESULT: not_run",
            combined,
            "a checker disabled in configuration must emit the not_run "
            f"report; got stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            "checker=sound_checker.py",
            combined,
            "the report must name the checker so a reader can tell which "
            "check is missing rather than only that one is",
        )
        self.assertIn(
            "reason=disabled",
            combined,
            "the report must name which of the three reasons applied",
        )
        self.assertEqual(
            result.returncode,
            0,
            "a check disabled by configuration is an intentional operator "
            "decision — it must not itself fail the commit; only the "
            f"report distinguishes it from a pass. stdout={result.stdout!r}",
        )


class TestUnstartableCheckerReportedAsNotRun(unittest.TestCase):
    """angle: failure — a checker that cannot even start must be reported as
    not_run, naming the checker and the "could_not_start" reason, and this
    case IS a genuine failure (non-zero exit)."""

    def test_unstartable_record_checker_is_reported_as_not_run(self):
        # covers: UXP-700c-3-ii
        # angle: failure
        missing_target = "docs/product-truth/scripts/definitely_missing_checker_UXP700c3ii.py"

        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            result = subprocess.run(
                [sys.executable, str(_RUN_HOOK_SRC), missing_target],
                cwd=str(tmp),
                capture_output=True,
                text=True,
                timeout=30,
            )

        combined = result.stdout + result.stderr
        self.assertIn(
            "RESULT: not_run",
            combined,
            "a checker that cannot start must emit the not_run report; got "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            "checker=definitely_missing_checker_UXP700c3ii.py",
            combined,
            "the report must name the checker so a reader can tell which "
            "check is missing rather than only that one is",
        )
        self.assertIn(
            "reason=could_not_start",
            combined,
            "the report must name which of the three reasons applied",
        )
        self.assertNotEqual(
            result.returncode,
            0,
            "an unlaunchable checker is a genuine defect, not an operator "
            f"choice — it must not exit as if the commit were clean. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )


class TestNotRunReportDiffersFromCheckedAndSound(unittest.TestCase):
    """angle: boundary — the not-run report must be distinguishable from
    the report produced when the same checker actually ran and was found
    sound, not merely differ by exit code."""

    def test_not_run_report_differs_from_the_checked_and_sound_report(self):
        # covers: UXP-700c-3-ii
        # angle: boundary
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            scripts_dir = _copy_run_hook_tree(tmp)
            _write_sound_checker(tmp, "fixture/sound_checker.py")

            _write_manifest(
                scripts_dir,
                hook_entry="python run_hook.py fixture/sound_checker.py",
                enabled=False,
            )
            not_run_result = _run_run_hook(scripts_dir, tmp, ["fixture/sound_checker.py"])

            _write_manifest(
                scripts_dir,
                hook_entry="python run_hook.py fixture/sound_checker.py",
                enabled=True,
            )
            checked_and_sound_result = _run_run_hook(scripts_dir, tmp, ["fixture/sound_checker.py"])

        self.assertIn(
            "RESULT: not_run",
            not_run_result.stdout + not_run_result.stderr,
            "the disabled run must carry the not_run report; got "
            f"stdout={not_run_result.stdout!r} stderr={not_run_result.stderr!r}",
        )
        self.assertNotIn(
            "RESULT: not_run",
            checked_and_sound_result.stdout + checked_and_sound_result.stderr,
            "a checker that actually ran and was found sound must NEVER "
            "carry the not_run report — this is the caller-observable "
            "distinction AC-2 requires. got stdout="
            f"{checked_and_sound_result.stdout!r} "
            f"stderr={checked_and_sound_result.stderr!r}",
        )
        self.assertNotEqual(
            not_run_result.stdout,
            checked_and_sound_result.stdout,
            "the two reports must not be textually identical",
        )


class TestReachability(unittest.TestCase):
    """angle: reachability — the not-run report must be provable through
    run_hook.py's real CLI entry point, invoked with the EXACT argument
    tail commit_guardian.json's own check-product-truth-validate manifest
    entry registers, naming the real production checker
    (validate_product_truth.py) rather than a synthetic stand-in."""

    def test_uxp_700c_3_ii_reachable_from_entry_point(self):
        # covers: UXP-700c-3-ii
        # angle: reachability
        #
        # completion_manifest.reachability_entry_point_answer:
        #   result: resolved
        #   entry_point: "python templates/scripts/commit_guardian/run_hook.py
        #     <checker-args-copied-verbatim-from-commit_guardian.json's
        #     check-product-truth-validate manifest entry> (CLI via
        #     subprocess, main() guarded by if __name__ == '__main__':) —
        #     the SAME dispatch wrapper every other already-wired hook in
        #     this repo's own .pre-commit-config.yaml invokes."
        self.assertTrue(
            _MANIFEST_SRC.is_file(),
            f"real commit_guardian.json not found at {_MANIFEST_SRC}",
        )
        entry_command = _real_check_product_truth_validate_entry()

        # entry_command looks like:
        #   "python {{config.output_root}}/scripts/commit_guardian/run_hook.py
        #    docs/product-truth/scripts/validate_product_truth.py --quiet"
        # Extract everything AFTER "run_hook.py" — the REAL checker-arg tail
        # a genuine commit hands to run_hook.py — copied verbatim, not
        # hand-typed.
        tokens = entry_command.split()
        run_hook_index = next(
            i for i, tok in enumerate(tokens) if tok.endswith("run_hook.py")
        )
        checker_args = tokens[run_hook_index + 1 :]
        self.assertTrue(
            checker_args,
            f"could not extract a checker-arg tail from entry={entry_command!r}",
        )
        # The real registered entry names the checker by a path; run_hook.py
        # reports the checker by basename (mirrors _target_script_name's
        # existing Path(args[0]).name convention) — resolve that here too.
        checker_basename = Path(checker_args[0]).name
        self.assertEqual(checker_basename, "validate_product_truth.py")

        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            scripts_dir = _copy_run_hook_tree(tmp)
            _write_manifest(
                scripts_dir,
                hook_entry=entry_command,
                enabled=False,
            )

            result = _run_run_hook(scripts_dir, tmp, checker_args)

        combined = result.stdout + result.stderr
        self.assertIn(
            "RESULT: not_run",
            combined,
            "invoking run_hook.py with the EXACT argument tail the real "
            "manifest registers must produce the not_run report when the "
            f"real checker's hook is disabled; got stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        self.assertIn(
            f"checker={checker_basename}",
            combined,
            "the report must name the REAL production checker, "
            "validate_product_truth.py, not a synthetic stand-in",
        )
        self.assertIn("reason=disabled", combined)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
