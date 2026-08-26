"""
MODULE: unit_tests/prompt_assembly/test_bp_1100g_1.py
COVERS: BP-1100g-1

GOAL (from the AC): the set of proof kinds ("angles") the planning side can
emit and the set of angle names templates/agents/test-writer.md TEACHES must
be the same set, no name the planning side can never emit may be one the
writer is taught either, and for each taught name the template must state
what distinguishes a proof of that kind from a proof of the behaviour alone.

THE SINGLE DEFINITION (per BO-2900g-3, work_status: done): the emittable set
is config/ac_store_schema.json's ``properties.test_spec`` array-branch item
schema, ``properties.angle.enum`` — NOT the ``_TEST_ANGLES`` frozenset copy in
scripts/ac_store/generate_ticket_from_ac.py (that copy is itself pinned to the
schema by BO-2900g-3's own cross-source test; reading it here would reproduce
the exact EPIC-ComputedQualityGates FP-1 layer-3 defect this AC exists to
prevent — a hook's allow-list and the config it mirrored, each tested against
its own copy).

THE ANCHOR CONTRACT THIS TEST FILE DEFINES (for templates/agents/test-writer.md,
edited by llm-expert — NOT this test file, and NEVER the deployed copy under
.claude/agents/ or .leafcutter/agents/, per the ticket's "Scope correction"):

    <!-- TAUGHT-TEST-ANGLES:START -->
    ```yaml
    criterion: <one sentence: what distinguishes a criterion-angle proof>
    reachability: <...>
    seam: <...>
    real_artifact: <...>
    deployed: <...>
    boundary: <...>
    failure: <...>
    ```
    <!-- TAUGHT-TEST-ANGLES:END -->

A single fenced YAML block between two fixed HTML-comment markers, one entry
per taught angle name, value = the one-sentence distinguishing rule for that
angle. This is machine-extractable and is the "single stable anchor" the
Implementation Notes require — prose that only mentions the names is NOT a
set and cannot be compared, and a taught set the checker cannot find is the
same as no taught set. BP-1100g-3's tag validation is expected to read this
same anchor.

RED BASELINE (2026-08-25): templates/agents/test-writer.md contains zero
occurrences of the word "angle" at HEAD, so the anchor does not exist yet and
every test below is expected to fail (ImportError-free but AssertionError on
comparison / anchor-not-found). llm-expert must add the anchor to
templates/agents/test-writer.md (never the deployed copy) to turn this suite
green; the deployed-copy test (Test 4) will re-fail on the very next
``build.py`` run if the anchor is ever added only to the deployed copy.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AC_SCHEMA_PATH = _REPO_ROOT / "config" / "ac_store_schema.json"
_TEMPLATE_PATH = _REPO_ROOT / "templates" / "agents" / "test-writer.md"
_BUILD_SCRIPT = _REPO_ROOT / "scripts" / "build.py"

_ANCHOR_START = "<!-- TAUGHT-TEST-ANGLES:START -->"
_ANCHOR_END = "<!-- TAUGHT-TEST-ANGLES:END -->"


def _emittable_angle_item_schema(schema: dict) -> dict:
    """Navigate to the test_spec[] item schema's ``angle`` property.

    Same navigation BO-2900g-3's own test (unit_tests/ac_store/test_bo_2900g_3.py)
    uses: ``test_spec`` is a ``oneOf`` with exactly one array branch.
    """
    test_spec = schema["properties"]["test_spec"]
    array_branches = [b for b in test_spec["oneOf"] if b.get("type") == "array"]
    assert len(array_branches) == 1, (
        "expected exactly one array branch in test_spec oneOf — schema shape "
        "has changed under this test"
    )
    return array_branches[0]["items"]


def _load_emittable_angles(schema_path: Path) -> set[str]:
    """Read the real, single-source-of-truth emittable angle set from disk.

    Raises (does not swallow) if the file is missing — a missing source must
    fail this test, never fall back to a hand-typed literal.
    """
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    item_schema = _emittable_angle_item_schema(schema)
    enum = item_schema.get("properties", {}).get("angle", {}).get("enum") or []
    return set(enum)


def _load_taught_angles(template_path: Path) -> dict:
    """Parse the taught-angle anchor out of a real test-writer.md on disk.

    Returns {} (not a raised error) when the anchor is entirely absent, so
    callers can report "the writer's taught set is empty" as a real,
    nameable mismatch rather than a crash. Raises if the file itself is
    missing — that is a real "no source" failure, distinct from "anchor not
    yet authored".
    """
    text = template_path.read_text(encoding="utf-8")
    if _ANCHOR_START not in text or _ANCHOR_END not in text:
        return {}
    block = text.split(_ANCHOR_START, 1)[1].split(_ANCHOR_END, 1)[0]
    match = re.search(r"```ya?ml\s*\n(.*?)```", block, re.DOTALL)
    if not match:
        return {}
    parsed = yaml.safe_load(match.group(1))
    return parsed if isinstance(parsed, dict) else {}


def _compare_angle_sets(emittable: set, taught: dict) -> list[str]:
    """Cross-source set-equality with per-name, per-side mismatch reporting.

    Every returned string names the specific angle AND the side that lacks
    it — "the sets differ" is explicitly disallowed by the AC.
    """
    mismatches: list[str] = []
    taught_names = set(taught.keys())
    for name in sorted(emittable - taught_names):
        mismatches.append(
            f"angle '{name}': emittable by the planning side (config/ac_store_schema.json "
            f"test_spec[].angle) but undefined for the test-writing side "
            f"(templates/agents/test-writer.md taught set)"
        )
    for name in sorted(taught_names - emittable):
        mismatches.append(
            f"angle '{name}': taught to the test-writing side "
            f"(templates/agents/test-writer.md) but the planning side "
            f"(config/ac_store_schema.json test_spec[].angle) can never emit it"
        )
    return mismatches


# ---------------------------------------------------------------------------
# Standalone comparator script, run as a genuinely fresh subprocess for the
# real_artifact angle (Test 2). Inlined rather than imported so the process
# boundary is real — a fresh `python -c` invocation, not importlib.reload().
# Fails loudly (non-zero exit + MISSING_SOURCE marker) when either source
# path is missing, rather than silently falling back to a literal.
# ---------------------------------------------------------------------------
_COMPARE_SCRIPT = textwrap.dedent(
    r"""
    import json, re, sys
    from pathlib import Path
    import yaml

    schema_path = Path(sys.argv[1])
    template_path = Path(sys.argv[2])

    if not schema_path.is_file():
        print(f"MISSING_SOURCE: {schema_path}", file=sys.stderr)
        sys.exit(2)
    if not template_path.is_file():
        print(f"MISSING_SOURCE: {template_path}", file=sys.stderr)
        sys.exit(2)

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    test_spec = schema["properties"]["test_spec"]
    array_branches = [b for b in test_spec["oneOf"] if b.get("type") == "array"]
    item_schema = array_branches[0]["items"]
    emittable = set(item_schema.get("properties", {}).get("angle", {}).get("enum") or [])

    text = template_path.read_text(encoding="utf-8")
    start, end = "<!-- TAUGHT-TEST-ANGLES:START -->", "<!-- TAUGHT-TEST-ANGLES:END -->"
    taught = {}
    if start in text and end in text:
        block = text.split(start, 1)[1].split(end, 1)[0]
        m = re.search(r"```ya?ml\s*\n(.*?)```", block, re.DOTALL)
        if m:
            parsed = yaml.safe_load(m.group(1))
            taught = parsed if isinstance(parsed, dict) else {}

    missing_from_taught = sorted(emittable - taught.keys())
    unemittable_taught = sorted(set(taught.keys()) - emittable)
    print(json.dumps({
        "emittable": sorted(emittable),
        "taught": sorted(taught.keys()),
        "missing_from_taught": missing_from_taught,
        "unemittable_taught": unemittable_taught,
    }))
    sys.exit(0 if not missing_from_taught and not unemittable_taught else 1)
    """
)


class TestTaughtSetEqualsEmittableSet(unittest.TestCase):
    """angle: criterion — the AC-literal happy path."""

    def test_bp_1100g_1_taught_set_equals_the_emittable_set(self) -> None:
        # covers: BP-1100g-1
        """Set-equality between the emittable angle enum (config/ac_store_schema.json
        test_spec[].angle) and the taught set in templates/agents/test-writer.md:
        no emittable name is undefined for the writer, and no taught name is
        unemittable. Each taught entry must also carry a non-empty
        distinguishing rule."""
        self.assertTrue(
            _AC_SCHEMA_PATH.is_file(),
            f"emittable-side source missing: {_AC_SCHEMA_PATH}",
        )
        self.assertTrue(
            _TEMPLATE_PATH.is_file(),
            f"taught-side source missing: {_TEMPLATE_PATH}",
        )

        emittable = _load_emittable_angles(_AC_SCHEMA_PATH)
        self.assertTrue(
            emittable,
            "config/ac_store_schema.json test_spec[].angle enum resolved empty — "
            "the emittable set has no well-defined left-hand side",
        )

        taught = _load_taught_angles(_TEMPLATE_PATH)
        self.assertTrue(
            taught,
            "templates/agents/test-writer.md has no <!-- TAUGHT-TEST-ANGLES:START/END "
            "--> anchor (or it parsed empty) — a taught set the checker cannot find "
            "is the same as no taught set",
        )

        mismatches = _compare_angle_sets(emittable, taught)
        self.assertEqual(
            mismatches,
            [],
            "taught set and emittable set disagree:\n" + "\n".join(mismatches),
        )

        for name, rule in taught.items():
            self.assertIsInstance(
                rule, str, f"angle '{name}' taught rule must be a string, got {type(rule)}"
            )
            self.assertTrue(
                rule.strip(),
                f"angle '{name}' must state a non-empty distinguishing rule the "
                f"writer can act on without further interpretation",
            )


class TestBothSetsAreReadFromTheirRealSources(unittest.TestCase):
    """angle: real_artifact — fresh-subprocess, no fixture copy of either side."""

    def test_bp_1100g_1_both_sets_are_read_from_their_real_sources(self) -> None:
        # covers: BP-1100g-1
        """Run the comparator in a genuinely fresh subprocess against the two
        real on-disk files (no fixture copy of either side) and assert it
        reports agreement."""
        result = subprocess.run(
            [sys.executable, "-c", _COMPARE_SCRIPT, str(_AC_SCHEMA_PATH), str(_TEMPLATE_PATH)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(
            result.returncode,
            0,
            "fresh-subprocess comparison of the two real on-disk sources must "
            f"agree.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["missing_from_taught"], [])
        self.assertEqual(payload["unemittable_taught"], [])

    def test_bp_1100g_1_missing_source_path_fails_loudly_not_a_literal_fallback(
        self,
    ) -> None:
        # covers: BP-1100g-1
        """If either real source path is missing, the comparator must fail
        (non-zero exit, MISSING_SOURCE marker) rather than silently falling
        back to a hand-typed literal set."""
        with tempfile.TemporaryDirectory() as tmp:
            nonexistent_schema = Path(tmp) / "does_not_exist_ac_store_schema.json"

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    _COMPARE_SCRIPT,
                    str(nonexistent_schema),
                    str(_TEMPLATE_PATH),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertNotEqual(
                result.returncode,
                0,
                "a missing emittable-side source must not be silently tolerated",
            )
            self.assertIn("MISSING_SOURCE", result.stderr)

            nonexistent_template = Path(tmp) / "does_not_exist_test-writer.md"
            result2 = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    _COMPARE_SCRIPT,
                    str(_AC_SCHEMA_PATH),
                    str(nonexistent_template),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertNotEqual(
                result2.returncode,
                0,
                "a missing taught-side source must not be silently tolerated",
            )
            self.assertIn("MISSING_SOURCE", result2.stderr)


class TestOneSidedNameAdditionIsReportedByNameAndSide(unittest.TestCase):
    """angle: failure — negative control on the mismatch-reporting contract."""

    def test_bp_1100g_1_name_added_only_to_emittable_side_is_named_and_attributed(
        self,
    ) -> None:
        # covers: BP-1100g-1
        """Add a name to a copy of the emittable (planning) side only; the
        report must name that specific angle and say the test-writing side
        lacks it."""
        schema = json.loads(_AC_SCHEMA_PATH.read_text(encoding="utf-8"))
        item_schema = _emittable_angle_item_schema(schema)
        item_schema["properties"]["angle"]["enum"].append("zz_probe_emittable_only")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_schema_path = Path(tmp) / "ac_store_schema.json"
            tmp_schema_path.write_text(json.dumps(schema), encoding="utf-8")

            emittable = _load_emittable_angles(tmp_schema_path)
            taught = _load_taught_angles(_TEMPLATE_PATH)
            mismatches = _compare_angle_sets(emittable, taught)

        joined = "\n".join(mismatches)
        self.assertIn(
            "zz_probe_emittable_only",
            joined,
            f"mismatch report must name the specific added angle:\n{joined}",
        )
        self.assertIn(
            "test-writing side",
            joined,
            f"mismatch report must state which side lacks the name:\n{joined}",
        )

    def test_bp_1100g_1_name_added_only_to_taught_side_is_named_and_attributed(
        self,
    ) -> None:
        # covers: BP-1100g-1
        """Swap the sides: add a name only to a copy of the taught side; the
        report must name that specific angle and say the planning side can
        never emit it."""
        emittable = _load_emittable_angles(_AC_SCHEMA_PATH)
        taught = dict(_load_taught_angles(_TEMPLATE_PATH))
        taught["zz_probe_taught_only"] = "a probe rule that exists only on the taught side"

        mismatches = _compare_angle_sets(emittable, taught)

        joined = "\n".join(mismatches)
        self.assertIn(
            "zz_probe_taught_only",
            joined,
            f"mismatch report must name the specific added angle:\n{joined}",
        )
        self.assertIn(
            "planning side",
            joined,
            f"mismatch report must state which side lacks the name:\n{joined}",
        )


class TestDeployedTestWriterTemplateCarriesTheTaughtSet(unittest.TestCase):
    """angle: reachability — production entry point is build.py; source-tree
    reads are structurally blind to a deploy-manifest gap."""

    def test_bp_1100g_1_deployed_test_writer_template_carries_the_taught_set(
        self,
    ) -> None:
        # covers: BP-1100g-1
        """PRODUCTION ENTRY POINT: run `python scripts/build.py --target-dir <tmp>`
        as a subprocess, then read the DEPLOYED .claude/agents/test-writer.md
        (the file the agent runtime actually loads) and assert its taught set
        equals the schema's emittable set. Editing only the deployed copy
        directly (never templates/) would pass a source-tree-only test but
        must FAIL here on the very next build, because build.py always
        regenerates the deployed copy from templates/."""
        self.assertTrue(
            _BUILD_SCRIPT.is_file(), f"build.py not found at {_BUILD_SCRIPT}"
        )

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            result = subprocess.run(
                [sys.executable, str(_BUILD_SCRIPT), "--target-dir", str(target)],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(_REPO_ROOT),
                timeout=120,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"build.py failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )

            deployed = target / ".claude" / "agents" / "test-writer.md"
            self.assertTrue(
                deployed.is_file(),
                f"deployed test-writer.md not found at {deployed} — build.py did "
                f"not deploy templates/agents/test-writer.md",
            )

            emittable = _load_emittable_angles(_AC_SCHEMA_PATH)
            taught = _load_taught_angles(deployed)
            self.assertTrue(
                taught,
                f"deployed {deployed} has no taught-angle anchor (or it parsed "
                f"empty) — the taught set must survive the build, not only exist "
                f"in templates/",
            )
            mismatches = _compare_angle_sets(emittable, taught)
            self.assertEqual(
                mismatches,
                [],
                "deployed test-writer.md's taught set diverges from the schema's "
                "emittable set:\n" + "\n".join(mismatches),
            )


if __name__ == "__main__":
    unittest.main()
