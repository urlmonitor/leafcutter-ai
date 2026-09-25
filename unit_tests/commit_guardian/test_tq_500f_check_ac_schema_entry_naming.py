"""
MODULE: unit_tests/commit_guardian/test_tq_500f_check_ac_schema_entry_naming.py
COVERS: TQ-500f-1, TQ-500f-2-i

REVIEW-FINDING FOLLOW-UP: the earlier TQ-500f-1 / TQ-500f-2-i test batch drove
only the standalone CLI (scripts/ac_store/validate_ac_schema.py). A review
found the entry-naming logic that answers TQ-500f-1's "message names the
entry, the field 'angle' and the permitted values" and TQ-500f-2-i's "message
names the entry, 'must_catch', and which rule failed" requirements was added
ONLY to scripts/ac_store/_ac_schema_test_spec_validators.py, which is wired
into validate_ac_schema.py alone (confirmed: `grep -rn
test_spec_entry_errors scripts/commit_guardian/` finds nothing). The REAL
commit gate — scripts/commit_guardian/check_ac_schema.py, via
scripts/commit_guardian/_ac_schema_validators.py's validate_with_jsonschema()
— still prints jsonschema's raw generic message
("... is not valid under any of the given schemas"), which names neither the
offending test_spec entry nor the field. This file drives THAT real hook
script directly (never the standalone CLI, never a hand-rolled reimplementation
of its logic) to prove the gap.

RED BASELINE (2026-09-25, confirmed live via direct probes against the real
hook before this file was written): angle: discriminating, must_catch: [],
must_catch: ['   '], and must_catch: 'x' are all correctly REJECTED (exit 1)
by the real hook today — config/ac_store_schema.json already carries the
widened enum/property (TQ-500f-1 / TQ-500f-2 landed on the schema side ahead
of this batch) — but in every case stderr is the bare jsonschema dump:
    "<path>: [{'name': 'test_gate_blocks_on_missing_input', ...}] is not
     valid under any of the given schemas"
containing neither the string "angle" nor "must_catch" nor any rule keyword,
and naming the entry only by accident (as part of the raw dict repr, not as
a deliberate "entry X" statement) — the rule-keyword and clean-message
assertions below are what is actually red.

HARNESS: mirrors the established pattern in this same directory's
test_check_ac_schema.py (HOOK_ROOT pointed at a throwaway tempfile.
TemporaryDirectory(), config/ac_store_schema.json copied in so jsonschema
validation is active, HOOK_TEST_STAGED_FILES naming the probe file
absolutely). tempfile.TemporaryDirectory() cleans itself up unconditionally
(even on assertion failure) — no real repo file is ever written or staged.
Fixture AC dicts are serialized with yaml.safe_dump (never a hand-typed YAML
string), per the fixture-authenticity convention.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_SCRIPT = _REPO_ROOT / "scripts" / "commit_guardian" / "check_ac_schema.py"
SCHEMA_FILE = _REPO_ROOT / "config" / "ac_store_schema.json"

_ENTRY_NAME = "test_gate_blocks_on_missing_input"

#: Fields proven to satisfy this hook's full jsonschema pass (mirrors the
#: sibling test_check_ac_schema.py's own _VALID_AC_YAML shape exactly, so a
#: failure here can only be attributed to the test_spec entry under test).
_BASE_FIELDS = {
    "component": "finalize",
    "components": ["finalize"],
    "status": "active",
    "created_by": "tickets/test.md",
    "priority": "medium",
    "readiness": "draft",
}


def _ac_dict(ac_id: str, test_spec_entry: dict) -> dict:
    record: dict = dict(_BASE_FIELDS)
    record["id"] = ac_id
    record["title"] = "TQ-500f entry-naming probe"
    record["criteria"] = "Given x\nWhen y\nThen z\n"
    record["test_spec"] = [test_spec_entry]
    return record


def _write_temp_store(root: Path, ac_id: str, test_spec_entry: dict) -> Path:
    """Build a throwaway store at *root*: a real schema copy + one real AC file.

    Returns the absolute path to the written AC YAML.
    """
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCHEMA_FILE, config_dir / "ac_store_schema.json")

    ac_dir = root / "docs" / "acceptance-criteria"
    ac_dir.mkdir(parents=True, exist_ok=True)
    path = ac_dir / f"{ac_id}.yaml"
    path.write_text(
        yaml.safe_dump(_ac_dict(ac_id, test_spec_entry), sort_keys=False),
        encoding="utf-8",
    )
    return path


def _run_hook(root: Path, staged_path: Path) -> subprocess.CompletedProcess:
    """Run the REAL check_ac_schema.py hook as a subprocess.

    HOOK_ROOT points the hook at the throwaway store; HOOK_TEST_STAGED_FILES
    is the staged-file test seam (documented in check_ac_schema.py's own
    _get_staged_ac_paths docstring) naming exactly the one probe file.
    HOOK_NO_GIT neutralises Phase 2 (implements_pattern preservation, which
    otherwise falls back to a REAL `git diff --cached` against this actual
    repo's index) so nothing from the real working tree's staged state can
    leak into this test's output.
    """
    env = os.environ.copy()
    env["HOOK_ROOT"] = str(root)
    env["HOOK_TEST_STAGED_FILES"] = str(staged_path)
    env["HOOK_NO_GIT"] = "1"
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        timeout=60,
    )


class TestHookRejectsMisspelledAngleWithEntryNaming:
    """angle: failure — the REAL commit-gate hook (production entry point)
    must name the entry, the field, and the permitted list on rejection."""

    def test_hook_rejects_misspelled_angle_with_entry_naming(self) -> None:
        # covers: TQ-500f-1
        # angle: failure
        """WRONG VERSION THIS CATCHES: the entry-naming logic added only to
        scripts/ac_store/_ac_schema_test_spec_validators.py (wired solely
        into validate_ac_schema.py) never being wired into
        scripts/commit_guardian/_ac_schema_validators.py /
        check_ac_schema.py — the REAL commit gate. Confirmed live: the hook
        already rejects 'discriminating' (exit 1, HOOK SAW THE FILE — see
        the file-count assertion), but stderr today is jsonschema's bare
        '... is not valid under any of the given schemas', containing none
        of 'angle', a clean per-entry statement, or the permitted list."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ac_path = _write_temp_store(
                root,
                "ZZP-910",
                {
                    "name": _ENTRY_NAME,
                    "target_dir": "unit_tests/ac_store/",
                    "angle": "discriminating",
                },
            )
            result = _run_hook(root, ac_path)

        assert result.returncode != 0, (
            f"angle: discriminating must be rejected by the real hook.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        stderr = result.stderr

        # Proof the hook actually saw (and processed) this exact file, not a
        # silently-empty staged-file list defaulting to a trivial pass.
        assert "1 file(s) failed validation" in stderr, (
            f"hook must report exactly one failed file (proves it saw the "
            f"staged probe, not zero files): {stderr}"
        )
        assert "ZZP-910.yaml" in stderr, (
            f"hook output must name the probe file it validated: {stderr}"
        )

        assert _ENTRY_NAME in stderr, (
            f"rejection message must name the offending test_spec entry "
            f"{_ENTRY_NAME!r}:\n{stderr}"
        )
        assert "angle" in stderr, (
            f"rejection message must name the field 'angle':\n{stderr}"
        )
        assert "discrimination" in stderr, (
            f"rejection message must list the permitted values, including "
            f"'discrimination':\n{stderr}"
        )
        assert "criterion" in stderr and "reachability" in stderr, (
            f"rejection message must list the FULL permitted set, not just "
            f"'discrimination' in isolation:\n{stderr}"
        )


class TestHookRejectsMalformedMustCatchWithRuleNaming:
    """angle: failure — parametrized over the three malformed shapes named in
    the AC's Given (empty list, blank-only entry, scalar instead of list)."""

    @pytest.mark.parametrize(
        "ac_id,must_catch,rule_keyword",
        [
            ("ZZP-911", [], "empty"),
            ("ZZP-912", ["   "], "blank"),
            ("ZZP-913", "x", "list"),
        ],
        ids=["empty_list", "blank_only_entry", "scalar_not_list"],
    )
    def test_hook_rejects_malformed_must_catch_with_rule_naming(
        self, ac_id: str, must_catch, rule_keyword: str
    ) -> None:
        # covers: TQ-500f-2-i
        # angle: failure
        """WRONG VERSION THIS CATCHES: same gap as above, for must_catch —
        the real hook already rejects all three malformed shapes (confirmed
        live, exit 1 in each case) but the message is the same generic
        jsonschema dump, saying nothing about WHICH rule failed (empty list
        / blank entry / not a list) — exactly the ambiguity TQ-500f-2-i's
        Then clause forbids ('A raw JSON-schema error dump that does not say
        which rule failed does not satisfy this')."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ac_path = _write_temp_store(
                root,
                ac_id,
                {
                    "name": _ENTRY_NAME,
                    "target_dir": "unit_tests/ac_store/",
                    "must_catch": must_catch,
                },
            )
            result = _run_hook(root, ac_path)

        assert result.returncode != 0, (
            f"must_catch={must_catch!r} must be rejected by the real hook.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        stderr = result.stderr

        assert "1 file(s) failed validation" in stderr, (
            f"hook must report exactly one failed file (proves it saw the "
            f"staged probe): {stderr}"
        )
        assert f"{ac_id}.yaml" in stderr, (
            f"hook output must name the probe file it validated: {stderr}"
        )

        assert _ENTRY_NAME in stderr, (
            f"rejection message must name the offending test_spec entry "
            f"{_ENTRY_NAME!r}:\n{stderr}"
        )
        assert "must_catch" in stderr, (
            f"rejection message must name the field 'must_catch':\n{stderr}"
        )
        assert rule_keyword in stderr.lower(), (
            f"rejection message must say which rule failed (expected the "
            f"word {rule_keyword!r}):\n{stderr}"
        )


class TestHookAcceptsValidDiscriminationAndMustCatch:
    """angle: criterion — the adversarial control: a well-formed entry using
    both new fields together must be accepted outright."""

    def test_hook_accepts_valid_discrimination_and_must_catch(self) -> None:
        # covers: TQ-500f-1
        # covers: TQ-500f-2-i
        # angle: criterion
        """WRONG VERSION THIS CATCHES: a fix that adds entry-naming to the
        real hook by accident REJECTING every angle/must_catch value (e.g. a
        botched rewrite of validate_with_jsonschema that always raises) —
        the returncode == 0 assertion below is the control that a
        blanket-reject 'fix' would fail. Also proves the harness genuinely
        exercises real validation rather than trivially always passing: the
        sibling test immediately below runs the SAME plumbing with one
        required field removed and demands it fail."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ac_path = _write_temp_store(
                root,
                "ZZP-914",
                {
                    "name": _ENTRY_NAME,
                    "target_dir": "unit_tests/ac_store/",
                    "angle": "discrimination",
                    "must_catch": ["revert the fix"],
                },
            )
            result = _run_hook(root, ac_path)

        assert result.returncode == 0, (
            f"a well-formed angle: discrimination + must_catch entry must be "
            f"accepted by the real hook.\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    def test_harness_control_same_plumbing_still_rejects_a_broken_file(self) -> None:
        # covers: TQ-500f-1
        # angle: criterion
        """Same HOOK_ROOT/HOOK_TEST_STAGED_FILES/HOOK_NO_GIT plumbing as the
        exit-0 test above, but with 'criteria' (a required field) deleted —
        proves a 0-exit result above is a real pass and not an artifact of
        the staged-file seam silently finding nothing to validate."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _ac_dict(
                "ZZP-915",
                {
                    "name": _ENTRY_NAME,
                    "target_dir": "unit_tests/ac_store/",
                    "angle": "discrimination",
                    "must_catch": ["revert the fix"],
                },
            )
            del record["criteria"]
            config_dir = root / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCHEMA_FILE, config_dir / "ac_store_schema.json")
            ac_dir = root / "docs" / "acceptance-criteria"
            ac_dir.mkdir(parents=True, exist_ok=True)
            ac_path = ac_dir / "ZZP-915.yaml"
            ac_path.write_text(
                yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
            )
            result = _run_hook(root, ac_path)

        assert result.returncode != 0, (
            "the same plumbing, minus the required 'criteria' field, must "
            f"still be rejected by the real hook — proves the harness "
            f"genuinely validates rather than vacuously passing.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "1 file(s) failed validation" in result.stderr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
