"""
MODULE: test_ki_cg_010_roadmap_schema_path
GOAL: Regression test for KI-CG-010 -- check-roadmap-schema never validated
    docs/roadmap.json because its schema path never existed, and repairing
    the path alone would have made docs/roadmap.json immediately
    uncommittable, so both halves (path + schema extension) must land
    together.
BUSINESS CONTEXT: check_roadmap_schema.SCHEMA_RELATIVE was
    "leafcutter/config/roadmap.schema.json", a path that has never existed;
    the schema has always lived at <project_root>/config/roadmap.schema.json.
    Because the path never resolved, main() hit its "schema not found;
    skipping" fail-open branch on every run, so the schema has validated
    nothing since the hook was written. Fixing the path alone exposes a
    SECOND problem: docs/roadmap.json (this repo's real roadmap) carries a
    root-level "last_updated" field and a per-phase "components" field that
    the schema's additionalProperties:false blocks did not allow -- 9
    violations (1 root + 8 phases) against the current 8-phase roadmap.
ARCHITECTURE: Loads check_roadmap_schema.py directly from its SOURCE
    location (templates/scripts/commit_guardian/) via importlib. Validates
    the REAL, on-disk docs/roadmap.json against the REAL, on-disk
    config/roadmap.schema.json -- no synthetic roadmap fixture -- per the
    project's real-artifact spot-check convention. A separate negative
    control proves the schema still rejects genuinely invalid content (not
    just permissively accepting everything).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_roadmap_schema.py"
)


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "check_roadmap_schema_test_shim", str(_HOOK_PATH)
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class TestSchemaRelativeResolvesToRealFile(unittest.TestCase):
    """SCHEMA_RELATIVE must point at this repo's real, shipped schema."""

    def test_schema_relative_is_project_root_relative_config_path(self):
        mod = _load_hook_module()
        self.assertEqual(
            mod.SCHEMA_RELATIVE,
            "config/roadmap.schema.json",
            "SCHEMA_RELATIVE must be 'config/roadmap.schema.json' -- "
            "'leafcutter/config/roadmap.schema.json' has never existed in "
            "any layout (KI-CG-010).",
        )

    def test_schema_relative_resolves_to_a_real_file_in_this_repo(self):
        mod = _load_hook_module()
        resolved = _REPO_ROOT / mod.SCHEMA_RELATIVE
        self.assertTrue(
            resolved.is_file(),
            f"SCHEMA_RELATIVE resolved to {resolved}, which does not exist. "
            "check_roadmap_schema always fails open (advisory skip) "
            "whenever this file is absent.",
        )


class TestRealRoadmapValidatesCleanAgainstRealSchema(unittest.TestCase):
    """This repo's real docs/roadmap.json must validate with zero errors
    against this repo's real, now-extended config/roadmap.schema.json.
    """

    def test_real_roadmap_has_zero_schema_errors(self):
        """
        Before KI-CG-010's schema-extension half, this exact real roadmap.json
        produces 9 errors (1 root 'last_updated' unexpected + 8 phase-item
        'components' unexpected, one per phase) against the schema as it
        stood -- proving the schema alone, independent of the path bug, was
        also broken. Both files are read directly off disk; no fixture.
        """
        schema = json.loads((_REPO_ROOT / "config" / "roadmap.schema.json").read_text())
        roadmap = json.loads((_REPO_ROOT / "docs" / "roadmap.json").read_text())

        validator = jsonschema.Draft7Validator(schema)
        errors = list(validator.iter_errors(roadmap))

        self.assertEqual(
            errors, [],
            "docs/roadmap.json must validate cleanly against "
            "config/roadmap.schema.json. Errors found:\n"
            + "\n".join(f"  - [{list(e.absolute_path)}] {e.message}" for e in errors),
        )


class TestHookEndToEndAgainstRealArtifacts(unittest.TestCase):
    """The hook's own main() must actually pass on the real roadmap/schema pair."""

    def test_main_exits_zero_with_no_fail_message_on_real_files(self):
        """
        Runs check_roadmap_schema.main() with _is_roadmap_staged monkeypatched
        to True (no real git index mutation) and _find_root pointed at this
        repo's real root, so it reads the REAL docs/roadmap.json and REAL
        config/roadmap.schema.json end to end.
        """
        import io
        from contextlib import redirect_stderr

        mod = _load_hook_module()
        mod._is_roadmap_staged = lambda: True
        mod._find_root = lambda: _REPO_ROOT

        buf = io.StringIO()
        with redirect_stderr(buf):
            with self.assertRaises(SystemExit) as ctx:
                mod.main()

        self.assertEqual(ctx.exception.code, 0)
        stderr_text = buf.getvalue()
        self.assertNotIn(
            "advisory", stderr_text.lower(),
            f"Hook printed an advisory/skip message against real, on-disk "
            f"files -- schema or roadmap failed to resolve. stderr:\n{stderr_text}",
        )
        self.assertNotIn("FAIL", stderr_text)

    def test_main_still_blocks_on_a_genuinely_invalid_roadmap(self):
        """Negative control: the now-fixed schema must still REJECT content
        that violates it, proving the fix did not turn validation into a
        no-op that accepts everything. Uses a scratch tmp_path copy of the
        real schema plus a deliberately invalid roadmap -- no writes to any
        project directory.
        """
        mod = _load_hook_module()
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            (fake_root / "config").mkdir(parents=True)
            (fake_root / "docs").mkdir(parents=True)
            schema_text = (_REPO_ROOT / "config" / "roadmap.schema.json").read_text()
            (fake_root / "config" / "roadmap.schema.json").write_text(schema_text)
            bad_roadmap = {
                "current_phase": "phase_1",
                "current_outcome": "irrelevant",
                "phases": [
                    {
                        "id": "phase_1",
                        "title": "x",
                        "exit_criteria": [],
                        "tickets_advancing_outcome": [],
                    }
                ],
                "not_a_real_field": "must be rejected by additionalProperties:false",
            }
            (fake_root / "docs" / "roadmap.json").write_text(json.dumps(bad_roadmap))

            mod._is_roadmap_staged = lambda: True
            mod._find_root = lambda: fake_root

            with self.assertRaises(SystemExit) as ctx:
                mod.main()

            self.assertEqual(
                ctx.exception.code, 1,
                "Hook must exit 1 (block the commit) on a roadmap.json that "
                "genuinely violates the schema.",
            )


if __name__ == "__main__":
    unittest.main()
