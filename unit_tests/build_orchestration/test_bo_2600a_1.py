"""
MODULE: unit_tests/build_orchestration/test_bo_2600a_1.py
GOAL: RED test stubs for BO-2600a-1 — resolve_connected_build_set with the
      new exclude_structural_parent keyword-only parameter.

=== Interface contract under test ===

Target:
    resolve_connected_build_set(
        ac_id: str,
        *,
        ac_root: Path,
        exclude_structural_parent: bool = False,   ← NEW (not yet implemented)
    ) -> list[str]

in scripts/build_orchestration/fast_lane.py.

New behaviour:
    When exclude_structural_parent=True, the transitive depends_on walk skips
    any dependency dep where dep == derive_parent_id(node)
    (derive_parent_id from scripts/ac_store/ac_parent_id.py).
    The subtree union (traverse_ac_tree) is unaffected by the flag.
    With exclude_structural_parent=False (the default) the function behaves
    identically to the pre-change implementation.

=== Red baseline ===

Tests 1, 2, and 4 pass exclude_structural_parent=True — a kwarg that does not
yet exist. These tests fail with:
    TypeError: resolve_connected_build_set() got an unexpected keyword argument
    'exclude_structural_parent'
until python-coder adds the parameter. The TypeError IS the intended red state.

Test 3 (test_default_false_preserves_existing_behavior) calls the function
with its current default signature and asserts the existing behavior. It may
pass today — see the red_baseline note in the test-writer sign-off comment.

=== Fixture authenticity ===

All AC YAML fixtures are written with yaml.safe_dump (not hand-typed YAML
literals), following the pattern established in test_fast_lane_connected.py.
AC ids (BO-9000a, BO-9000a-1, BO-9000a-2, BO-8888a, BO-8888a-1) are chosen so
that derive_parent_id produces the correct structural parent:
    derive_parent_id("BO-9000a-1") == "BO-9000a"   → structural parent dep
    derive_parent_id("BO-9000a-1") != "BO-8888a-1"  → genuine peer dep
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path wiring — make fast_lane and ac_parent_id importable
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"

for _p in (_MODULE_DIR, _AC_STORE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ---------------------------------------------------------------------------
# Imports
# resolve_connected_build_set exists in fast_lane.py; the new kwarg does not.
# derive_parent_id is used to sanity-check fixture ID choices at setUp time.
# ---------------------------------------------------------------------------

from fast_lane import resolve_connected_build_set  # noqa: E402
from ac_parent_id import derive_parent_id  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helper (mirrors test_fast_lane_connected.py — fixture-authenticity)
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    level: str,
    work_status: str,
    readiness: str = "approved",
    depends_on: list | None = None,
    covered_by: list | None = None,
) -> Path:
    """Write a minimal AC YAML file using yaml.safe_dump (fixture-authenticity mandate).

    Mirrors the helper in test_fast_lane_connected.py: no hand-typed YAML,
    always serialised via yaml.safe_dump.

    Args:
        ac_root: Root of the synthetic AC store.
        ac_id: AC identifier.
        level: "L0", "L1", "L2", or "L3".
        work_status: "todo" or "done".
        readiness: "approved", "draft", or "reviewed" (default: "approved").
        depends_on: List of AC ids this AC depends on.
        covered_by: List of child AC ids (for parent nodes).

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": level,
        "status": "active",
        "work_status": work_status,
        "readiness": readiness,
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": depends_on if depends_on is not None else [],
        "covered_by": covered_by if covered_by is not None else [],
        "amended_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path = subdir / f"{ac_id}.yaml"
    # Fixture-authenticity mandate: use yaml.safe_dump, never a hand-typed literal.
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tests for BO-2600a-1
# ---------------------------------------------------------------------------


class TestExcludeStructuralParent(unittest.TestCase):
    """BO-2600a-1 — resolve_connected_build_set(exclude_structural_parent=True).

    All tests that pass the new kwarg are RED (TypeError) until python-coder
    adds the exclude_structural_parent parameter to resolve_connected_build_set.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _build_shared_fixture(self) -> None:
        """Build the AC tree shared by tests 1 and 2.

        Tree layout (using ids whose parent derivation is correct by construction):

            BO-9000a  (L1) — covered_by: [BO-9000a-1, BO-9000a-2]
              BO-9000a-1  (L2) — depends_on: [BO-9000a, BO-8888a-1]
              BO-9000a-2  (L2) — no deps

            BO-8888a  (L1) — covered_by: [BO-8888a-1]
              BO-8888a-1  (L2) — no deps  (genuine peer prerequisite)

        Structural-parent invariants verified here so a future id rename breaks
        loudly rather than silently skipping the parent-vs-peer distinction:
            derive_parent_id("BO-9000a-1") == "BO-9000a"   ← structural parent dep
            derive_parent_id("BO-9000a-1") != "BO-8888a-1" ← genuine peer dep
        """
        assert derive_parent_id("BO-9000a-1") == "BO-9000a", (
            "Fixture invariant violated: 'BO-9000a' must be the structural "
            "parent of 'BO-9000a-1' (derive_parent_id check)."
        )
        assert derive_parent_id("BO-9000a-1") != "BO-8888a-1", (
            "Fixture invariant violated: 'BO-8888a-1' must NOT be the structural "
            "parent of 'BO-9000a-1' — it is a genuine peer dep."
        )

        _write_ac(
            self.ac_root,
            "BO-9000a",
            level="L1",
            work_status="todo",
            covered_by=["BO-9000a-1", "BO-9000a-2"],
        )
        _write_ac(
            self.ac_root,
            "BO-9000a-1",
            level="L2",
            work_status="todo",
            depends_on=["BO-9000a", "BO-8888a-1"],
        )
        _write_ac(
            self.ac_root,
            "BO-9000a-2",
            level="L2",
            work_status="todo",
        )
        _write_ac(
            self.ac_root,
            "BO-8888a",
            level="L1",
            work_status="todo",
            covered_by=["BO-8888a-1"],
        )
        _write_ac(
            self.ac_root,
            "BO-8888a-1",
            level="L2",
            work_status="todo",
        )

    def test_exclude_structural_parent_skips_parent_dep(self) -> None:
        # covers: BO-2600a-1
        """AC-2: with exclude_structural_parent=True a dep equal to derive_parent_id(node)
        is NOT expanded into the build set.

        Fixture: BO-9000a-1 (L2) has depends_on: ["BO-9000a", "BO-8888a-1"].
        derive_parent_id("BO-9000a-1") == "BO-9000a" — structural parent dep.

        With exclude_structural_parent=True:
          - "BO-9000a" is recognised as the structural parent of BO-9000a-1 → skipped.
          - Its leaves (BO-9000a-2) are NOT added to the build set via the deps walk.
          - "BO-9000a-2" must therefore NOT appear in the result.

        DEFECT: the exclude_structural_parent kwarg does not yet exist.
        TypeError: resolve_connected_build_set() got an unexpected keyword argument
        'exclude_structural_parent' IS the intended red state.

        To make this green:
          1. Add `exclude_structural_parent: bool = False` to the signature.
          2. Inside the depends_on walk, when flag is True, skip any dep where
             dep == derive_parent_id(node).
        """
        self._build_shared_fixture()

        result = resolve_connected_build_set(
            "BO-9000a-1",
            ac_root=self.ac_root,
            exclude_structural_parent=True,
        )

        self.assertIsInstance(result, list)
        self.assertIn(
            "BO-9000a-1",
            result,
            "The target leaf BO-9000a-1 must still be in the result "
            "(it enters via the subtree union, not the deps walk).",
        )
        self.assertNotIn(
            "BO-9000a-2",
            result,
            "BO-9000a-2 must NOT be in the result when exclude_structural_parent=True. "
            "The only path to BO-9000a-2 is via expanding BO-9000a (the structural "
            "parent dep of BO-9000a-1), which is skipped. "
            "(BO-2600a-1: structural parent dep is not expanded into the build set.)",
        )

    def test_exclude_structural_parent_keeps_peer_deps(self) -> None:
        # covers: BO-2600a-1
        """AC-3: genuine (non-structural-parent) depends_on prerequisites are still
        included when exclude_structural_parent=True.

        Fixture: BO-9000a-1 depends_on ["BO-9000a", "BO-8888a-1"].
          - "BO-9000a" == derive_parent_id("BO-9000a-1") → structural parent → skipped.
          - "BO-8888a-1" != derive_parent_id("BO-9000a-1") → genuine peer → NOT skipped.

        BO-8888a-1 must appear in the result even when the flag is True.

        DEFECT: the exclude_structural_parent kwarg does not yet exist.
        TypeError is the intended red state.

        To make this green: only skip deps that equal derive_parent_id(node).
        Genuine peer deps (any dep whose id differs from derive_parent_id(node))
        must still be walked and included.
        """
        self._build_shared_fixture()

        result = resolve_connected_build_set(
            "BO-9000a-1",
            ac_root=self.ac_root,
            exclude_structural_parent=True,
        )

        self.assertIn(
            "BO-8888a-1",
            result,
            "Genuine peer prerequisite BO-8888a-1 must be included even when "
            "exclude_structural_parent=True — only the structural parent dep "
            "(derive_parent_id(node)) is skipped, not all deps. "
            "(BO-2600a-1 AC-3: non-structural-parent deps are still included.)",
        )

    def test_default_false_preserves_existing_behavior(self) -> None:
        # covers: BO-2600a-1
        """AC-1/AC-5: with the default (exclude_structural_parent omitted / False)
        the function behaves identically to today — every depends_on entry is walked.

        Fixture:
          BO-9000a (L1) — covered_by: [BO-9000a-1, BO-9000a-2]
            BO-9000a-1 (L2) — depends_on: ["BO-9000a"]  (structural parent dep)
            BO-9000a-2 (L2) — no deps

        Without the flag (default=False), BO-9000a is expanded into its leaves:
        BO-9000a-2 is added to the result via the deps walk (existing behavior).

        NOTE: This test may pass today because the function already exists without
        the new param. It is included as a backward-compatibility regression guard
        — it must stay green after python-coder adds the flag so that existing
        callers that omit the flag are entirely unaffected.
        """
        _write_ac(
            self.ac_root,
            "BO-9000a",
            level="L1",
            work_status="todo",
            covered_by=["BO-9000a-1", "BO-9000a-2"],
        )
        _write_ac(
            self.ac_root,
            "BO-9000a-1",
            level="L2",
            work_status="todo",
            depends_on=["BO-9000a"],
        )
        _write_ac(
            self.ac_root,
            "BO-9000a-2",
            level="L2",
            work_status="todo",
        )

        # Call without the new flag — uses the default (False) and must match pre-change behavior.
        result = resolve_connected_build_set("BO-9000a-1", ac_root=self.ac_root)

        self.assertIn(
            "BO-9000a-1",
            result,
            "Target leaf BO-9000a-1 must be in the result.",
        )
        self.assertIn(
            "BO-9000a-2",
            result,
            "BO-9000a-2 must be in the result with default flag (False): "
            "BO-9000a (structural parent dep) is expanded into its leaves via the "
            "existing behavior, adding BO-9000a-2 to the build set. "
            "(BO-2600a-1 AC-5: default=False preserves existing every-dep-is-walked behavior.)",
        )

    def test_children_present_when_parent_excluded(self) -> None:
        # covers: BO-2600a-1
        """AC-4: the AC's own subtree children still enter the set even when the
        structural parent is excluded from the depends_on walk.

        Fixture:
          BO-9000a (L1) — covered_by: [BO-9000a-1, BO-9000a-2]
            BO-9000a-1 (L2) — depends_on: ["BO-9000a"]  (structural parent dep)
            BO-9000a-2 (L2) — no deps

        Call: resolve_connected_build_set("BO-9000a", ..., exclude_structural_parent=True)

        Step 1 — subtree union of BO-9000a:
            traverse_ac_tree("BO-9000a") → {BO-9000a-1, BO-9000a-2}
            Both children enter the build_set here, before any deps walk.

        Step 2 — depends_on walk:
            For BO-9000a-1: dep "BO-9000a" == derive_parent_id("BO-9000a-1") → SKIPPED.
            For BO-9000a-2: no deps.

        Expected result: [BO-9000a-1, BO-9000a-2]
            Both children are present because they entered via the subtree union
            (step 1), not the deps walk (step 2). The flag only affects step 2.

        DEFECT: the exclude_structural_parent kwarg does not yet exist.
        TypeError is the intended red state.

        To make this green:
            The subtree union (traverse_ac_tree call in step 1) must remain
            entirely unchanged. Only the deps walk (step 2) is affected by the flag.
        """
        _write_ac(
            self.ac_root,
            "BO-9000a",
            level="L1",
            work_status="todo",
            covered_by=["BO-9000a-1", "BO-9000a-2"],
        )
        _write_ac(
            self.ac_root,
            "BO-9000a-1",
            level="L2",
            work_status="todo",
            depends_on=["BO-9000a"],
        )
        _write_ac(
            self.ac_root,
            "BO-9000a-2",
            level="L2",
            work_status="todo",
        )

        result = resolve_connected_build_set(
            "BO-9000a",
            ac_root=self.ac_root,
            exclude_structural_parent=True,
        )

        self.assertIsInstance(result, list)
        self.assertIn(
            "BO-9000a-1",
            result,
            "BO-9000a-1 must be in the result even when exclude_structural_parent=True: "
            "it enters via the subtree union of BO-9000a (step 1), not the deps walk. "
            "(BO-2600a-1 AC-4: subtree children still enter the set.)",
        )
        self.assertIn(
            "BO-9000a-2",
            result,
            "BO-9000a-2 must be in the result even when exclude_structural_parent=True: "
            "it enters via the subtree union of BO-9000a (step 1). "
            "(BO-2600a-1 AC-4: excluding structural parent never drops the AC's real children.)",
        )


    def test_structural_parent_skipped_at_every_hop(self) -> None:
        # covers: BO-2600a-1
        """AC-2 multi-hop (cross-tree, DISCRIMINATING): the structural-parent skip uses
        derive_parent_id(node) — evaluated per worklist node — NOT the fixed
        derive_parent_id(ac_id).  This fixture produces different results for the
        two variants, making the test a genuine regression guard.

        Fixture:
          BO-9000a  (L1) — covered_by: [BO-9000a-1]
            BO-9000a-1  (L2) — depends_on: ["BO-8888a-1"]   ← cross-tree peer (first hop)

          BO-8888a  (L1) — covered_by: [BO-8888a-1, BO-8888a-2]
            BO-8888a-1  (L2) — depends_on: ["BO-8888a"]     ← BO-8888a-1's OWN structural parent (second hop)
            BO-8888a-2  (L2) — no deps                       ← detectable expansion child

        Call: resolve_connected_build_set("BO-9000a-1", ..., exclude_structural_parent=True)

        Walk trace — CORRECT impl (derive_parent_id(node)):
          Hop 1 — node = "BO-9000a-1":
            dep "BO-8888a-1": derive_parent_id("BO-9000a-1") = "BO-9000a" ≠ "BO-8888a-1"
            → genuine cross-tree peer — NOT skipped; BO-8888a-1 added.

          Hop 2 — node = "BO-8888a-1" (INTERMEDIATE, cross-tree):
            dep "BO-8888a": derive_parent_id("BO-8888a-1") = "BO-8888a" == "BO-8888a"
            → structural parent of the CURRENT node — SKIPPED.
            BO-8888a is NOT expanded → BO-8888a-2 stays out of the result.

        Walk trace — BUGGY impl (derive_parent_id(ac_id) anchored to root):
          Hop 2 — node = "BO-8888a-1":
            dep "BO-8888a": derive_parent_id(ac_id="BO-9000a-1") = "BO-9000a" ≠ "BO-8888a"
            → NOT skipped (wrong — "BO-8888a" is BO-8888a-1's parent, not BO-9000a-1's)
            BO-8888a IS expanded → BO-8888a-2 ADDED to result (BUG).

        Discriminating assertion: "BO-8888a-2" must NOT be in result.
            Correct impl → absent (BO-8888a skipped at second hop) ✓
            Buggy impl   → present (BO-8888a not skipped at second hop) — test FAILS on buggy
        """
        # Fixture-authenticity invariant checks.
        assert derive_parent_id("BO-9000a-1") == "BO-9000a", (
            "Fixture invariant: BO-9000a-1's structural parent must be BO-9000a."
        )
        assert derive_parent_id("BO-8888a-1") == "BO-8888a", (
            "Fixture invariant: BO-8888a-1's structural parent must be BO-8888a."
        )
        assert derive_parent_id("BO-9000a-1") != "BO-8888a", (
            "Fixture invariant: BO-9000a-1's structural parent must differ from "
            "BO-8888a — the two families must be distinct so the discriminating "
            "assertion separates correct from buggy impl."
        )

        # Root family: BO-9000a-1 reaches BO-8888a-1 as a cross-tree peer dep.
        _write_ac(
            self.ac_root,
            "BO-9000a",
            level="L1",
            work_status="todo",
            covered_by=["BO-9000a-1"],
        )
        _write_ac(
            self.ac_root,
            "BO-9000a-1",
            level="L2",
            work_status="todo",
            depends_on=["BO-8888a-1"],  # cross-tree peer dep (first hop)
        )

        # Other family: BO-8888a-1 has its OWN structural parent dep (BO-8888a).
        _write_ac(
            self.ac_root,
            "BO-8888a",
            level="L1",
            work_status="todo",
            covered_by=["BO-8888a-1", "BO-8888a-2"],
        )
        _write_ac(
            self.ac_root,
            "BO-8888a-1",
            level="L2",
            work_status="todo",
            depends_on=["BO-8888a"],    # BO-8888a-1's structural parent (second hop)
        )
        _write_ac(
            self.ac_root,
            "BO-8888a-2",
            level="L2",
            work_status="todo",
            # No deps — only reachable via expanding BO-8888a.
        )

        result = resolve_connected_build_set(
            "BO-9000a-1",
            ac_root=self.ac_root,
            exclude_structural_parent=True,
        )

        self.assertIsInstance(result, list)
        self.assertIn(
            "BO-8888a-1",
            result,
            "BO-8888a-1 must be in the result: it is a genuine cross-tree peer dep of "
            "BO-9000a-1 (first hop). derive_parent_id('BO-9000a-1') == 'BO-9000a' != "
            "'BO-8888a-1' — not a structural parent dep, so NOT skipped. "
            "(BO-2600a-1 AC-3: genuine peer deps are still included.)",
        )
        self.assertIn(
            "BO-9000a-1",
            result,
            "The root target BO-9000a-1 must be in the result.",
        )
        # Discriminating assertion — fails on buggy derive_parent_id(ac_id) impl:
        self.assertNotIn(
            "BO-8888a-2",
            result,
            "BO-8888a-2 must NOT be in the result. "
            "Correct impl: at hop 2, node='BO-8888a-1', dep='BO-8888a', "
            "derive_parent_id(node='BO-8888a-1')='BO-8888a' == dep → SKIPPED; "
            "BO-8888a not expanded → BO-8888a-2 absent. "
            "Buggy impl (derive_parent_id(ac_id='BO-9000a-1')='BO-9000a' ≠ 'BO-8888a'): "
            "dep NOT skipped → BO-8888a expanded → BO-8888a-2 PRESENT (bug detected). "
            "(BO-2600a-1: structural-parent skip applies per-node, not anchored to root ac_id.)",
        )


    def test_cross_tree_composite_peer_is_expanded_not_skipped(self) -> None:
        # covers: BO-2600a-1
        """AC-2/AC-3 discriminating: a cross-tree COMPOSITE dep that is NOT the
        structural parent must be EXPANDED (not skipped) when exclude_structural_parent=True.

        This test discriminates between the CORRECT implementation and a WRONG
        alternative — "skip any composite (non-leaf) dep" — that passes every
        existing single-hop test because in those fixtures every composite dep
        happens to also be the structural parent.

        Fixture:
          BO-7777a  (L1) — covered_by: [BO-7777a-1]
            BO-7777a-1  (L2) — depends_on: ["BO-6666a"]
                                              ^ COMPOSITE (L1) but derive_parent_id("BO-7777a-1")
                                                == "BO-7777a" != "BO-6666a" → NOT the structural parent

          BO-6666a  (L1) — covered_by: [BO-6666a-1, BO-6666a-2]
            BO-6666a-1  (L2) — no deps
            BO-6666a-2  (L2) — no deps

        Call: resolve_connected_build_set("BO-7777a-1", ..., exclude_structural_parent=True)

        CORRECT impl (skip only dep == derive_parent_id(node)):
          node = "BO-7777a-1", dep = "BO-6666a"
          derive_parent_id("BO-7777a-1") = "BO-7777a" ≠ "BO-6666a" → NOT skipped.
          BO-6666a is composite + not done → expanded via traverse_ac_tree
          → BO-6666a-1 and BO-6666a-2 enter the build set.
          BO-6666a-1 IN result ✓   BO-6666a-2 IN result ✓

        BUGGY impl ("skip any composite dep"):
          node = "BO-7777a-1", dep = "BO-6666a"
          BO-6666a is composite (L1) → skipped entirely.
          BO-6666a-1 NOT in result ✗   BO-6666a-2 NOT in result ✗
          → assertIn BO-6666a-1 FAILS (bug detected).
        """
        # Verify structural-parent invariants for the fixture ids.
        assert derive_parent_id("BO-7777a-1") == "BO-7777a", (
            "Fixture invariant: BO-7777a-1's structural parent must be BO-7777a."
        )
        assert derive_parent_id("BO-7777a-1") != "BO-6666a", (
            "Fixture invariant: BO-6666a must NOT be the structural parent of "
            "BO-7777a-1 — it is a cross-tree composite peer dep."
        )

        _write_ac(
            self.ac_root,
            "BO-7777a",
            level="L1",
            work_status="todo",
            covered_by=["BO-7777a-1"],
        )
        _write_ac(
            self.ac_root,
            "BO-7777a-1",
            level="L2",
            work_status="todo",
            depends_on=["BO-6666a"],    # cross-tree composite peer (NOT the structural parent)
        )
        _write_ac(
            self.ac_root,
            "BO-6666a",
            level="L1",
            work_status="todo",
            covered_by=["BO-6666a-1", "BO-6666a-2"],
        )
        _write_ac(
            self.ac_root,
            "BO-6666a-1",
            level="L2",
            work_status="todo",
        )
        _write_ac(
            self.ac_root,
            "BO-6666a-2",
            level="L2",
            work_status="todo",
        )

        result = resolve_connected_build_set(
            "BO-7777a-1",
            ac_root=self.ac_root,
            exclude_structural_parent=True,
        )

        self.assertIsInstance(result, list)
        self.assertIn(
            "BO-7777a-1",
            result,
            "The root target BO-7777a-1 must be in the result.",
        )
        # Discriminating assertions — both fail on the "skip any composite" buggy impl:
        self.assertIn(
            "BO-6666a-1",
            result,
            "BO-6666a-1 must be in the result. BO-6666a is a cross-tree composite peer "
            "dep of BO-7777a-1; derive_parent_id('BO-7777a-1')='BO-7777a' != 'BO-6666a' "
            "so it must NOT be skipped — it must be expanded into its leaves. "
            "A buggy 'skip any composite dep' impl would omit BO-6666a-1. "
            "(BO-2600a-1 AC-3: only the structural-parent dep is skipped, not all composites.)",
        )
        self.assertIn(
            "BO-6666a-2",
            result,
            "BO-6666a-2 must be in the result. BO-6666a (composite cross-tree peer) must "
            "be expanded into ALL its not-done leaves including BO-6666a-2. "
            "(BO-2600a-1: genuine composite peer deps are fully expanded, not skipped.)",
        )


if __name__ == "__main__":
    unittest.main()
