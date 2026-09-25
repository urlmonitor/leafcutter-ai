"""
MODULE: test_uxp_700c_3
GOAL: Pin UXP-700c-3 -- the record's checker (docs/product-truth/scripts/
    validate_product_truth.py) runs by itself, as one of the project's
    automatic checks, at the moment the record or a file it points at
    changes; its verdict IS the verdict those checks report (no advisory
    downgrade); and a change touching neither the record nor anything it
    points at never runs it.
BUSINESS CONTEXT: architect-review + adr-author (ADR-049) found the checker
    ALREADY registered (check-product-truth-validate, in both
    .pre-commit-config.yaml and hooks_manifest.hooks[]) with a HAND-WRITTEN
    files: regex correct only "by coincidence" -- the checker's
    resolvable-pointer surface is today exactly one kind (an
    acceptance-criterion id; product_truth_checks.is_resolvable_pointer_
    target()). ADR-049 sub-decision 2 requires that coincidence replaced with
    a DERIVED relationship: product_truth_checks.py exports a named
    source-of-truth for the checker's own resolvable-pointer roots, and every
    test below computes the expected trigger regex FROM that export -- never
    restating it as a literal -- so a pointer kind becoming resolvable
    without the gate widening in the same commit is an assertion failure
    here, not a silent GE-120 "green must mean checked" drift.
ARCHITECTURE: Required NEW symbols this ticket adds to
    docs/product-truth/scripts/product_truth_checks.py (zero hits for either
    name as of authoring -- every test below is expected to fail on import
    until python-coder adds them):

        RESOLVABLE_POINTER_TRIGGER_PATTERNS: tuple[str, ...]
            One anchored regex alternative per resolvable-pointer root: the
            record's own root ("^docs/product-truth/") plus one alternative
            per resolvable pointer KIND (today:
            "^docs/acceptance-criteria/.*\\.yaml$"). ADR-049 sub-decision 3:
            widening is_resolvable_pointer_target() to recognise a new kind
            MUST add that kind's root here in the SAME commit (unless its
            `unless` clause applies).

        def resolvable_pointer_trigger_pattern() -> str
            Returns "(" + "|".join(RESOLVABLE_POINTER_TRIGGER_PATTERNS) + ")"
            -- the union regex the hook's files: scope MUST equal in
            .pre-commit-config.yaml AND both commit_guardian.json copies
            (ADR-049 Operational note: identical in all three).

    Test-file layout (the exact three tests named in this ticket's Test
    Requirements / UXP-700c-3.yaml test_spec):
      * TestRecordCheckerIsRegisteredAmongTheProjectsAutomaticChecks --
        angle: reachability. Reads the REAL .pre-commit-config.yaml and both
        REAL commit_guardian.json copies and asserts each configured files:
        value equals the DERIVED pattern (never a literal restatement, per
        this AC's own test_rationale: "reading the configuration, not
        calling the checker directly"). Then invokes the REAL
        check-hook-trigger-reachability CLI -- this project's own dedicated
        production entry point for "is this gate's files: scope reachable
        against real tracked paths" (BP-100k-4 / ADR-049 sub-decision 8) --
        against a synthetic HOOK_TEST_CONFIG registry holding ONLY the real,
        verbatim entry, proving the registration genuinely activates.

        completion_manifest.reachability_entry_point_answer:
          result: resolved
          entry_point: "python scripts/commit_guardian/check_hook_trigger_reachability.py
            (CLI via subprocess, main() guarded by if __name__ == '__main__':),
            invoked against a HOOK_TEST_CONFIG registry containing ONLY the
            real, verbatim check-product-truth-validate hooks_manifest entry
            -- this project's own dedicated production answer to 'is a
            registered gate's files: scope reachable from real tracked
            paths' (BP-100k-4 / ADR-049 sub-decision 8)."
      * TestAChangeToAPointedAtFileRunsTheRecordChecker -- angle: seam. Pipes
        a REAL, on-disk pointed-at file (a synthetic AC-store YAML, built
        like test_uxp_700b_2.py's `_make_store` -- copying the REAL checker
        + its REAL sibling modules into a tempdir) through the REAL
        run_hook.py dispatch wrapper, and asserts (a) the real checker
        genuinely executed (no `RESULT: not_run`, and its own "resolved N AC
        pointer(s)" line proves it inspected the pointed-at file), and (b)
        the wrapper's exit status equals the checker's verdict when that
        verdict is `failed` (a deliberately BROKEN second pointer forces
        this) -- ADR-049 sub-decision 4 / AC-2's no-fail-open contract,
        architect-review's own flagged SECOND-ORDER RISK on this AC, proven
        with a genuine failing verdict rather than a trivial 0-equals-0.
      * TestAnUnrelatedChangeDoesNotRunTheRecordChecker -- angle: boundary.
        ADR-049 sub-decision 6: AC-3's assertion "MUST be made against the
        configured trigger scope ... and MUST NOT be made by instrumenting
        process launches" -- so this test launches nothing. It asserts the
        DERIVED pattern does NOT match a plainly unrelated file plus two
        deliberate NEAR-MISSES (one per alternative), and DOES still match
        the record's own root and a real pointer-kind path (positive
        control against a vacuously-narrowed pattern).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"
_SCRIPTS_DIR = _PT_SRC / "scripts"
_HOOK_ID = "check-product-truth-validate"

_CG_DIR = _REPO_ROOT / "scripts" / "commit_guardian"
_MANIFEST_SRC = _CG_DIR / "commit_guardian.json"
_MANIFEST_TEMPLATES = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json"
_PRECOMMIT_CONFIG = _REPO_ROOT / ".pre-commit-config.yaml"
_RUN_HOOK_SRC = _CG_DIR / "run_hook.py"
_CHECK_OUTCOME_SRC = _CG_DIR / "check_outcome.py"
_REACHABILITY_CLI = _CG_DIR / "check_hook_trigger_reachability.py"

# The scripts directory is not on the default path; add it so we can import,
# mirroring test_uxp_700c_1.py's / test_uxp_700c_2.py's convention for this
# same docs/product-truth/scripts location.
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Expected to fail (ImportError) until python-coder adds both symbols to
# product_truth_checks.py -- see ARCHITECTURE above for their exact contract.
from product_truth_checks import (  # noqa: E402
    RESOLVABLE_POINTER_TRIGGER_PATTERNS,  # noqa: F401  (imported for the attribute-error red state; unused directly)
    resolvable_pointer_trigger_pattern,
)


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _manifest_hook_entry(manifest_path: Path, hook_id: str) -> dict:
    """Read one REAL, on-disk hooks_manifest entry verbatim (never hand-typed)."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for hook in manifest.get("hooks_manifest", {}).get("hooks", []):
        if hook.get("id") == hook_id:
            return hook
    raise AssertionError(f"{hook_id!r} is not registered in {manifest_path} -- this test "
                          "must be updated, not deleted, if the hook is intentionally renamed")


def _precommit_hook_entry(hook_id: str) -> dict:
    """Read one REAL, on-disk .pre-commit-config.yaml hook entry verbatim."""
    config = yaml.safe_load(_PRECOMMIT_CONFIG.read_text(encoding="utf-8"))
    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            if hook.get("id") == hook_id:
                return hook
    raise AssertionError(f"{hook_id!r} is not registered in {_PRECOMMIT_CONFIG}")


def _checker_args_tail(entry_command: str) -> list[str]:
    """The REAL checker-arg tail a genuine commit hands to run_hook.py."""
    tokens = entry_command.split()
    run_hook_index = next(i for i, tok in enumerate(tokens) if tok.endswith("run_hook.py"))
    return tokens[run_hook_index + 1:]


def _copy_run_hook_tree(tmp: Path) -> Path:
    """Copy the REAL run_hook.py + check_outcome.py into a fresh tempdir."""
    scripts_dir = tmp / "wrapper_scripts"
    scripts_dir.mkdir(parents=True)
    shutil.copy2(_RUN_HOOK_SRC, scripts_dir / "run_hook.py")
    shutil.copy2(_CHECK_OUTCOME_SRC, scripts_dir / "check_outcome.py")
    return scripts_dir


def _journey(n: int, implements: list[str]) -> dict:
    return {
        "id": f"fixture-product/journey-{n}", "component": "fixture-product", "name": f"journey-{n}",
        "summary": "fixture journey for UXP-700c-3", "kind": "user", "source": "mock", "status": "active",
        "readiness": "draft", "version": 1, "entities": [],
        "steps": [{"id": "act", "label": "act", "human": "the actor acts", "order": 1, "implements": implements}],
        "branches": [],
    }


def _build_fixture_store(root: Path, implements: list[str]) -> Path:
    """A minimal, REAL, on-disk product-truth store (mirrors test_uxp_700b_2.py's
    `_make_store`): copies the REAL checker + its REAL sibling modules and
    schemas verbatim, then authors one flow whose step `implements` the given
    pointer targets. `AC-REAL-1` always exists in the fixture AC store;
    `implements` may also name a target that does NOT exist there, to force a
    real, failed verdict."""
    pt = root / "docs" / "product-truth"
    shutil.copytree(_SCRIPTS_DIR, pt / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_PT_SRC / "schemas", pt / "schemas")
    for place in ("flows/fixture-product", "mock-data", "mockups", "classifier"):
        (pt / place).mkdir(parents=True)
    (pt / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")

    ac_dir = root / "docs" / "acceptance-criteria" / "fixture-product"
    ac_dir.mkdir(parents=True)
    (ac_dir / "AC-REAL-1.yaml").write_text(
        yaml.safe_dump({"id": "AC-REAL-1", "work_status": "todo"}), encoding="utf-8"
    )

    flows_dir = pt / "flows" / "fixture-product"
    (flows_dir / "journey-1.flow.json").write_text(
        json.dumps(_journey(1, implements), indent=2) + "\n", encoding="utf-8"
    )
    (pt / "index.json").write_text(json.dumps({
        "artifacts": [{"id": "fixture-product/journey-1", "type": "flow", "component": "fixture-product",
                       "path": "flows/fixture-product/journey-1.flow.json", "status": "active",
                       "readiness": "draft", "version": 1}],
        "entity_registry": [],
    }, indent=2) + "\n", encoding="utf-8")
    return pt


# --------------------------------------------------------------------------- #
# AC-1 (reachability): the checker is registered among the automatic checks,
# with a file scope that includes the record.
# --------------------------------------------------------------------------- #
class TestRecordCheckerIsRegisteredAmongTheProjectsAutomaticChecks(unittest.TestCase):
    def test_record_checker_is_registered_among_the_projects_automatic_checks(self):
        # covers: UXP-700c-3
        # angle: reachability
        expected_pattern = resolvable_pointer_trigger_pattern()

        manifest_entry = _manifest_hook_entry(_MANIFEST_SRC, _HOOK_ID)
        self.assertEqual(
            manifest_entry.get("files"), expected_pattern,
            "scripts/commit_guardian/commit_guardian.json's files: scope for "
            f"{_HOOK_ID} must be DERIVED from product_truth_checks's own exported "
            "resolvable-pointer roots (ADR-049 sub-decision 2), not a hand-restated "
            f"literal; configured={manifest_entry.get('files')!r} expected={expected_pattern!r}"
        )

        templates_entry = _manifest_hook_entry(_MANIFEST_TEMPLATES, _HOOK_ID)
        self.assertEqual(
            templates_entry.get("files"), expected_pattern,
            "the templates/ mirror must stay identical to the deployed manifest "
            "(ADR-049 Operational note: kept identical in all three files)"
        )

        precommit_entry = _precommit_hook_entry(_HOOK_ID)
        self.assertEqual(
            precommit_entry.get("files"), expected_pattern,
            ".pre-commit-config.yaml's files: scope must match the same derived pattern"
        )

        self.assertNotEqual(
            manifest_entry.get("always_run"), True,
            "ADR-049 sub-decision 5: the hook MUST NOT be always_run -- activation "
            "is decided statically from the derived regex, never by the checker "
            "deciding internally whether it applies"
        )

        # Real production entry point: this project's own dedicated answer to
        # "is a registered gate's files: scope reachable from real tracked
        # paths", run against a synthetic registry holding ONLY the real,
        # verbatim check-product-truth-validate entry.
        #
        # completion_manifest.reachability_entry_point_answer:
        #   result: resolved
        #   entry_point: "python scripts/commit_guardian/check_hook_trigger_reachability.py
        #     (CLI via subprocess, main() guarded by if __name__ == '__main__':)
        #     run against a HOOK_TEST_CONFIG registry containing ONLY the real,
        #     verbatim check-product-truth-validate hooks_manifest entry -- the
        #     project's own dedicated production entry point for this exact
        #     question (BP-100k-4 / ADR-049 sub-decision 8)."
        synthetic_registry = {"hooks_manifest": {"hooks": [manifest_entry]}}
        with tempfile.TemporaryDirectory() as tmp_name:
            config_path = Path(tmp_name) / "hook_test_config.json"
            config_path.write_text(json.dumps(synthetic_registry), encoding="utf-8")
            env = os.environ.copy()
            env["HOOK_TEST_CONFIG"] = str(config_path)
            result = subprocess.run(
                [sys.executable, str(_REACHABILITY_CLI)],
                cwd=str(_REPO_ROOT), capture_output=True, text=True, timeout=30, env=env,
            )

        self.assertEqual(
            result.returncode, 0,
            "check_hook_trigger_reachability.py must report the record checker's "
            "own trigger scope reachable against this repository's real tracked "
            f"paths; stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        self.assertIn(
            "unreachable=0", result.stderr,
            f"expected a clean, zero-unreachable reachability verdict; stderr={result.stderr!r}"
        )


# --------------------------------------------------------------------------- #
# AC-1 (execution) + AC-2 (verdict propagation): offering a change to a file
# the record points at causes the checker to run, and its verdict -- even a
# failing one -- IS the verdict the wrapper reports; no fail-open.
# --------------------------------------------------------------------------- #
class TestAChangeToAPointedAtFileRunsTheRecordChecker(unittest.TestCase):
    def test_a_change_to_a_pointed_at_file_runs_the_record_checker(self):
        # covers: UXP-700c-3
        # angle: seam
        pointed_at_path = "docs/acceptance-criteria/fixture-product/AC-REAL-1.yaml"
        self.assertRegex(
            pointed_at_path, resolvable_pointer_trigger_pattern(),
            "fixture setup bug: the file used to prove 'runs' must itself match "
            "the DERIVED resolvable-pointer trigger scope"
        )

        real_entry = _manifest_hook_entry(_MANIFEST_SRC, _HOOK_ID)
        checker_args = _checker_args_tail(real_entry["entry"])
        self.assertEqual(
            Path(checker_args[0]).name, "validate_product_truth.py",
            "the entry must name the REAL production checker, not a synthetic stand-in"
        )

        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            pt = _build_fixture_store(tmp, implements=["AC-REAL-1", "AC-BOGUS-404"])

            generate_result = subprocess.run(
                [sys.executable, str(pt / "scripts" / "generate_product_truth.py")],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(
                generate_result.returncode, 0,
                f"fixture setup: generate_product_truth.py must succeed; "
                f"stdout={generate_result.stdout!r} stderr={generate_result.stderr!r}"
            )

            wrapper_dir = _copy_run_hook_tree(tmp)
            wrapper_result = subprocess.run(
                [sys.executable, str(wrapper_dir / "run_hook.py"), *checker_args],
                cwd=str(tmp), capture_output=True, text=True, timeout=30,
            )

        wrapper_combined = wrapper_result.stdout + wrapper_result.stderr

        self.assertNotIn(
            "RESULT: not_run", wrapper_combined,
            "offering a change to a file the record points at must actually "
            f"launch the real checker, not report not_run; got {wrapper_combined!r}"
        )
        self.assertIn(
            "resolved 1 AC pointer(s)", wrapper_combined,
            "the real checker must have actually INSPECTED the pointed-at AC "
            "file, not merely been launched and exited without doing the work; "
            f"got {wrapper_combined!r}"
        )
        self.assertIn(
            "AC-BOGUS-404", wrapper_combined,
            f"the real checker's own broken-pointer report must surface through "
            f"the wrapper unchanged; got {wrapper_combined!r}"
        )
        self.assertNotEqual(
            wrapper_result.returncode, 0,
            "ADR-049 sub-decision 4 / AC-2: the wrapper's own exit status IS the "
            "checker's verdict -- a run the checker reports 'failed' MUST block "
            f"the commit, never be downgraded to an advisory pass; got exit="
            f"{wrapper_result.returncode} combined={wrapper_combined!r}"
        )


# --------------------------------------------------------------------------- #
# AC-3 (boundary): a change touching neither the record nor anything it
# points at does not run the checker -- proven against the configured
# trigger scope itself (ADR-049 sub-decision 6), never by instrumenting a
# process launch.
# --------------------------------------------------------------------------- #
class TestAnUnrelatedChangeDoesNotRunTheRecordChecker(unittest.TestCase):
    def test_an_unrelated_change_does_not_run_the_record_checker(self):
        # covers: UXP-700c-3
        # angle: boundary
        compiled = re.compile(resolvable_pointer_trigger_pattern())

        unrelated_paths = [
            # Plainly unrelated -- the populated "does not match" middle.
            "README.md",
            "unit_tests/product_truth/test_uxp_700c_3.py",
            # Near-miss on the record's own root: shares the literal prefix
            # but the root is NOT terminated by "/", so it must not match.
            "docs/product-truthiness/notes.md",
            # Near-miss on the AC-id pointer kind: right directory, wrong
            # extension (the checker only resolves ".yaml", never ".yml").
            "docs/acceptance-criteria/fixture-product/AC-REAL-1.yml",
        ]
        for path in unrelated_paths:
            self.assertIsNone(
                compiled.search(path),
                f"{path!r} touches neither the record nor a resolvable pointer "
                "target it names -- the derived trigger scope must NOT match it, "
                "or the record's checker would run on a change AC-3 requires it "
                f"not to; pattern={compiled.pattern!r}"
            )

        # And the positive control: the record's own root, and a real
        # resolvable-pointer-kind path, MUST still match -- otherwise this
        # test would be vacuously true by an over-narrowed pattern.
        for path in ("docs/product-truth/flows/fixture-product/journey-1.flow.json",
                     "docs/acceptance-criteria/fixture-product/AC-REAL-1.yaml"):
            self.assertIsNotNone(
                compiled.search(path),
                f"{path!r} IS a file the record points at (or the record "
                f"itself) -- the derived pattern must match it; pattern={compiled.pattern!r}"
            )


if __name__ == "__main__":
    unittest.main()
