"""
MODULE: test_ge_124g_1
GOAL: Prove GE-124g-1 -- a front-end declaration or element pin is never
      written into an AC record's `covered_by`; component-level declarations
      belong in `declared_by`, element pins in `pinned_by`.
COVERS: GE-124g-1

Every behavioural test runs the REAL entry points as subprocesses:
  * the commit hook  templates/scripts/commit_guardian/check_ac_schema.py
  * the standalone   scripts/ac_store/validate_ac_schema.py
against AC records written to disk with yaml.safe_dump (never hand-typed YAML).
Each failing case asserts the criterion id, the offending value and the field
the value belongs in -- and each is paired with a control record that must pass.

A test that ends red with an ImportError-shaped failure is not used here: the
tests reach the existing validators and fail on their exit code / message.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.conftest import load_fixture

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCHEMA_SRC = _REPO_ROOT / "config" / "ac_store_schema.json"
_HOOK = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ac_schema.py"
_STANDALONE = _REPO_ROOT / "scripts" / "ac_store" / "validate_ac_schema.py"

_AC_ID = "GE-9999a-1"
_FRONTEND_PATH = "frontend/src/components/KmAdminPanel.tsx"
_PIN_SLUG = "decl-km-adm-004-save-button"
_TEST_REFS = [
    "frontend/src/components/KmAdminPanel.test.tsx::renders the save button",
    "frontend/src/components/__tests__/KmAdminPanel.tsx::saves on click",
    "frontend/src/components/KmAdminPanel.stories.tsx::default story",
]


def _refusal_findings(output: str) -> list[str]:
    """The per-criterion findings of a validator run, minus the variable file path.

    Both entry points print one `<path>: criterion <id>: <message>` line per
    finding; the path prefix differs between them and holds a temp directory, so
    each finding is cut at the word `criterion` and compared exactly.
    """
    return [line[line.index("criterion "):] for line in output.splitlines() if "criterion " in line]


def _expected_refusal(value: str, field: str) -> str:
    """The exact refusal GE-124g-1 requires: criterion id, offending value, correct field."""
    return f"criterion {_AC_ID}: covered_by entry '{value}' is not coverage; it belongs in {field} (GE-124g-1)"


def _base_record() -> dict:
    """The real-format base AC record (from the JSON fixture)."""
    return copy.deepcopy(load_fixture("ge_124g_1/base_ac"))


class _Store:
    """A temp repo root holding one AC record written by yaml.safe_dump."""

    def __init__(self, record: dict) -> None:
        self.tmp = tempfile.mkdtemp(prefix="ge124g1_")
        self.root = Path(self.tmp)
        (self.root / "config").mkdir()
        shutil.copy(_SCHEMA_SRC, self.root / "config" / "ac_store_schema.json")
        store_dir = self.root / "docs" / "acceptance-criteria" / "guardrail-engine"
        store_dir.mkdir(parents=True)
        self.path = store_dir / f"{_AC_ID}.yaml"
        self.path.write_text(yaml.safe_dump(record, sort_keys=True), encoding="utf-8")

    def cleanup(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_hook(self) -> subprocess.CompletedProcess:
        """Run the commit-hook entry point the way the hook runner does."""
        env = dict(os.environ)
        env.update(
            HOOK_ROOT=str(self.root),
            HOOK_TEST_STAGED_FILES=str(self.path),
            HOOK_NO_GIT="1",
        )
        return subprocess.run(
            [sys.executable, str(_HOOK)], cwd=str(self.root), env=env,
            capture_output=True, text=True, timeout=120,
        )

    def run_standalone(self) -> subprocess.CompletedProcess:
        """Run the standalone validator CLI on the record."""
        return subprocess.run(
            [sys.executable, str(_STANDALONE), str(self.path)],
            cwd=str(self.root), capture_output=True, text=True, timeout=120,
        )


class TestGe124g1(unittest.TestCase):
    def setUp(self) -> None:
        self._stores: list[_Store] = []

    def tearDown(self) -> None:
        for store in self._stores:
            store.cleanup()

    def _store(self, record: dict) -> _Store:
        store = _Store(record)
        self._stores.append(store)
        return store

    def _both(self, record: dict) -> list[tuple[str, subprocess.CompletedProcess]]:
        store = self._store(record)
        return [("hook", store.run_hook()), ("standalone", store.run_standalone())]

    def test_ge_124g_1_declaration_and_pin_populate_their_own_fields_and_leave_covered_by_untouched(self):
        # covers: GE-124g-1
        # angle: criterion
        """AC-1/AC-2/AC-3/AC-4/AC-5: declared_by / pinned_by hold the declaration and
        the pin; covered_by and implemented_by are unchanged (all four asserted)."""
        record = _base_record()
        record["declared_by"] = [_FRONTEND_PATH]
        record["pinned_by"] = [_PIN_SLUG]
        before = copy.deepcopy(record)
        store = self._store(record)
        for name, proc in (("hook", store.run_hook()), ("standalone", store.run_standalone())):
            self.assertEqual(proc.returncode, 0, f"{name}: {proc.stdout}{proc.stderr}")
        after = yaml.safe_load(store.path.read_text(encoding="utf-8"))
        self.assertEqual(after["declared_by"], [_FRONTEND_PATH])
        self.assertEqual(after["pinned_by"], [_PIN_SLUG])
        self.assertEqual(after["covered_by"], before["covered_by"])
        self.assertEqual(after["implemented_by"], before["implemented_by"])
        # Control: the same values routed into covered_by instead must be refused.
        wrong = _base_record()
        wrong["covered_by"] = wrong["covered_by"] + [_FRONTEND_PATH, _PIN_SLUG]
        for name, proc in self._both(wrong):
            self.assertNotEqual(proc.returncode, 0, f"{name} accepted a declaration in covered_by")

    def test_ge_124g_1_covered_by_write_of_a_frontend_path_is_rejected_naming_the_correct_field(self):
        # covers: GE-124g-1
        # angle: failure
        """AC-6/AC-7: a front-end path in covered_by blocks (non-zero exit) and the
        message names the criterion, the value and declared_by; a pin slug names
        pinned_by. Run through both real entry points."""
        cases = [(_FRONTEND_PATH, "declared_by"), (_PIN_SLUG, "pinned_by")]
        for value, field in cases:
            record = _base_record()
            record["covered_by"] = record["covered_by"] + [value]
            for name, proc in self._both(record):
                out = proc.stdout + proc.stderr
                with self.subTest(entry=name, value=value):
                    self.assertEqual(proc.returncode, 1, out)
                    # Exactly one finding, naming the criterion, the value and only the right field.
                    self.assertEqual(_refusal_findings(out), [_expected_refusal(value, field)], out)
        # No opt-out: the rejection holds even when the record carries an escape-shaped key.
        sneaky = _base_record()
        sneaky["covered_by"] = sneaky["covered_by"] + [_FRONTEND_PATH]
        sneaky["allow_declaration_in_covered_by"] = True
        for name, proc in self._both(sneaky):
            self.assertEqual(proc.returncode, 1, f"{name}: {proc.stdout}{proc.stderr}")

    def test_ge_124g_1_a_legitimate_frontend_test_reference_in_covered_by_is_still_accepted(self):
        # covers: GE-124g-1
        # angle: boundary
        """Front-end test/story references stay valid in covered_by while a component
        path in the same list is rejected; the accepting record also uses declared_by,
        so it cannot pass before the new fields exist."""
        good = _base_record()
        good["covered_by"] = good["covered_by"] + _TEST_REFS
        good["declared_by"] = [_FRONTEND_PATH]
        for name, proc in self._both(good):
            self.assertEqual(proc.returncode, 0, f"{name} refused a test reference: {proc.stdout}{proc.stderr}")
        bad = _base_record()
        bad["covered_by"] = bad["covered_by"] + _TEST_REFS + [_FRONTEND_PATH]
        bad["declared_by"] = [_FRONTEND_PATH]
        for name, proc in self._both(bad):
            out = proc.stdout + proc.stderr
            self.assertEqual(proc.returncode, 1, f"{name}: {out}")
            # Exactly one finding: the component path. The three test references
            # sitting in the same covered_by list are not flagged.
            self.assertEqual(_refusal_findings(out), [_expected_refusal(_FRONTEND_PATH, "declared_by")], f"{name}: {out}")

    def test_ge_124g_1_new_fields_are_accepted_by_both_schema_validators(self):
        # covers: GE-124g-1
        # angle: real_artifact
        """declared_by / pinned_by (serialized with yaml.safe_dump) validate under the
        schema file, the hook and the standalone validator alike; non-array values
        are refused by both."""
        schema = json.loads(_SCHEMA_SRC.read_text(encoding="utf-8"))
        props = schema.get("properties", {})
        array_of_strings = {"type": "array", "items": {"type": "string"}, "uniqueItems": False, "default": []}
        for field in ("declared_by", "pinned_by", "covered_by", "implemented_by"):
            shape = {k: props[field][k] for k in array_of_strings}
            self.assertEqual(shape, array_of_strings, f"schema shape of {field}")
        # Optional fields; and the schema itself cannot tell a front-end path from
        # any string (items stay a bare string type), which is why the rejection
        # lives in the validators proven by the runs below.
        self.assertEqual(sorted(set(schema.get("required", [])) & {"declared_by", "pinned_by"}), [])
        self.assertEqual(props["covered_by"]["items"], {"type": "string"})
        record = _base_record()
        record["declared_by"] = [_FRONTEND_PATH]
        record["pinned_by"] = [_PIN_SLUG]
        for name, proc in self._both(record):
            self.assertEqual(proc.returncode, 0, f"{name}: {proc.stdout}{proc.stderr}")
        malformed = _base_record()
        malformed["declared_by"] = "not-a-list"
        for name, proc in self._both(malformed):
            self.assertNotEqual(proc.returncode, 0, f"{name} accepted a non-array declared_by")

    def test_ge_124g_1_reachable_from_entry_point(self):
        # covers: GE-124g-1
        # angle: reachability
        """The staged-commit hook (real subprocess, real argv-less hook entry) refuses a
        covered_by write of a front-end path and the refusal is its exit status."""
        record = _base_record()
        record["covered_by"] = record["covered_by"] + [_FRONTEND_PATH]
        proc = self._store(record).run_hook()
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 1, out)
        self.assertEqual(_refusal_findings(out), [_expected_refusal(_FRONTEND_PATH, "declared_by")], out)


if __name__ == "__main__":
    unittest.main()
