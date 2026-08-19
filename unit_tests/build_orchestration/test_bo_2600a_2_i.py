"""
MODULE: unit_tests/build_orchestration/test_bo_2600a_2_i.py
GOAL: RED behavioral test for BO-2600a-2-i — the fast-lane ship workflow's
      select_connected invocation must pass --exclude-structural-parent, so
      pointing the fast lane at one leaf AC does not balloon the resolved
      build set into the whole not-done subtree of that leaf's structural
      L0/L1 parent.

=== Defect under test ===

Target: templates/workflows-js/fast-lane-ship.js, the `selectConnectedInvocation`
template literal (~line 306-307):

    const selectConnectedInvocation =
      `python3 ${gateScript} select_connected --ac ${targetAc} --ac-root ${acStoreRoot}`;

This omits --exclude-structural-parent. resolve_connected_build_set()
(scripts/build_orchestration/fast_lane.py, capability landed and tested by
BO-2600a-1/BO-2600a-2 — both already `work_status: done`) walks EVERY
depends_on entry as a genuine prerequisite unless the flag suppresses
structural-parent entries specifically. A leaf AC that names its own L0/L1
parent in depends_on (a common authoring pattern — the parent as an
"umbrella" dependency) therefore has that parent's ENTIRE not-done subtree
pulled into the connected build set, recursively — the reported symptom
(one AC resolving to fifteen).

=== Why this is a BEHAVIORAL test, not a grep ===

Per this repo's CLAUDE.md ("Gate / Workflow ACs — Verify Behaviorally, Not by
Grep"), a test that only checks whether the source string
"--exclude-structural-parent" appears in fast-lane-ship.js would pass on dead
code — e.g. a flag concatenated into a comment, or into an invocation that is
built but never actually run through the resolver. Instead this test:

  1. Drives the REAL fast-lane-ship.js control flow under the E2 workflow
     engine harness (run_workflow_under_e2), so the `selectConnectedInvocation`
     template literal is interpolated by the actual JS runtime (targetAc,
     gateScript, acStoreRoot substituted for real) — not re-typed by hand here.
  2. Extracts the composed command's ARGUMENT TOKENS from the captured
     Resolve-phase agent() prompt (a real runtime artifact of step 1).
  3. Re-issues those tokens — preserving verbatim whether
     --exclude-structural-parent is present — against the REAL
     scripts/build_orchestration/fast_lane.py CLI, pointed at a synthetic AC
     store fixture built with yaml.safe_dump under tmp_path (per the Fixture
     Authenticity Rule — AC YAML is a serialized format, never hand-typed).
  4. Asserts on the RESOLVED AC ID SET the real resolver returns — never on
     the command text itself.

The script path / --ac / --ac-root VALUES the JS composes are worktree-
relative (they only exist inside a freshly-created fast-lane worktree that
this unit test does not create) and are substituted for runnable
equivalents; only the FLAG TOKENS are carried through unmodified from the
real composed command. This is the behavioral analogue of what a human
would do by hand: read what the workflow actually tells the agent to run,
then run it for real against a controlled fixture.

=== Red baseline ===

test_ac1_fast_lane_resolved_set_excludes_structural_parent_subtree
    RED today. fast-lane-ship.js's composed command lacks
    --exclude-structural-parent, so the real resolver run with the extracted
    (flag-less) tokens expands the fixture target's structural parent
    (BO-9500a) into its full not-done subtree, pulling in the two sibling
    leaves (BO-9500a-2, BO-9500a-3) that this test asserts must NOT appear.

test_dropping_the_flag_reproduces_the_ballooned_set
    Negative control (per BO-2600a-2-i's test_spec). Invokes the REAL
    resolver directly (bypassing the JS workflow entirely) over the SAME
    fixture WITHOUT --exclude-structural-parent and asserts the returned set
    is STRICTLY LARGER and includes the sibling leaves. This is expected to
    pass immediately (--exclude-structural-parent itself was already
    implemented and tested by BO-2600a-1/BO-2600a-2, both `work_status:
    done`) — it exists to pin the size difference to the flag itself, so
    that an implementation which returns a small set for an unrelated reason
    (empty store, load failure) cannot masquerade as satisfying the positive
    test above.

=== Fixture authenticity ===

All AC YAML fixtures are written with yaml.safe_dump (never a hand-typed
YAML literal), mirroring test_bo_2600a_1.py / test_bo_2600a_2.py.

Fixture AC ids:
    BO-9500a       (L1) — covered_by: [BO-9500a-1, BO-9500a-2, BO-9500a-3]
    BO-9500a-1     (L2) — depends_on: [BO-9500a]  (its OWN structural parent)
    BO-9500a-2     (L2) — no deps (sibling — must NOT be pulled in)
    BO-9500a-3     (L2) — no deps (sibling — must NOT be pulled in)

    derive_parent_id("BO-9500a-1") == "BO-9500a"  → structural parent dep
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"

for _p in (_UNIT_TESTS_DIR, _MODULE_DIR, _AC_STORE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# unit_tests/ must be on sys.path for the shared E2 harness (mirrors
# unit_tests/workflows/test_bo_2300_pause_resume.py's wiring).
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

# Fixture invariant check only — no production behavior depends on this import.
from ac_parent_id import derive_parent_id  # noqa: E402

_FAST_LANE_SHIP_JS = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"
_REAL_FAST_LANE_PY = _MODULE_DIR / "fast_lane.py"

_RESOLVE_LABEL = "resolve-connected"
_WORKTREE_LABEL = "fastlane-worktree"

_HARNESS_TIMEOUT = 30
_SUBPROCESS_TIMEOUT = 30

# Matches the literal command line fast-lane-ship.js's Resolve-phase prompt
# embeds between "... (a list of AC ids):\n" and the following blank line.
_CMD_RE = re.compile(
    r"Run this single Bash command and parse its JSON stdout \(a list of AC ids\):"
    r"\n\s*(?P<cmd>python3 .+?)\n\n",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Fixture helpers (fixture-authenticity mandate: yaml.safe_dump only)
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
    """Write a minimal AC YAML file using yaml.safe_dump.

    Mirrors the identically-named helper in test_bo_2600a_1.py and
    test_bo_2600a_2.py. Never a hand-typed YAML literal.
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
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Extraction + real-execution helpers
# ---------------------------------------------------------------------------


def _extract_resolve_command(target_ac: str) -> str:
    """Drive the REAL fast-lane-ship.js control flow and return the literal
    select_connected command line it composes for the Resolve phase.

    The harness's default worktree-agent stub has no `worktree_path` key,
    which fast-lane-ship.js treats as a hard failure before the Resolve
    phase ever dispatches — so a deterministic worktree_path is supplied via
    label_responses to let the real interpolation of gateScript / targetAc /
    acStoreRoot actually happen and the Resolve agent() call actually fire.
    """
    result = run_workflow_under_e2(
        _FAST_LANE_SHIP_JS,
        timeout=_HARNESS_TIMEOUT,
        args={"ac": target_ac},
        label_responses={
            _WORKTREE_LABEL: {
                "worktree_path": "/dummy/fastlane-worktree",
                "branch": f"fast-lane/{target_ac.lower()}",
                "created": True,
            },
        },
    )
    if result.error:
        raise AssertionError(f"Harness error driving fast-lane-ship.js: {result.error}")

    resolve_calls = [c for c in result.agent_calls if c.label == _RESOLVE_LABEL]
    if not resolve_calls:
        raise AssertionError(
            "fast-lane-ship.js did not dispatch the Resolve phase agent "
            f"(label {_RESOLVE_LABEL!r}). Dispatched labels: "
            f"{[c.label for c in result.agent_calls]}"
        )

    prompt = resolve_calls[0].prompt
    if not isinstance(prompt, str):
        raise AssertionError(
            f"Resolve phase prompt must be an instruction string, got {type(prompt).__name__}"
        )

    match = _CMD_RE.search(prompt)
    if match is None:
        raise AssertionError(
            "Could not locate the select_connected command line in the Resolve "
            f"phase prompt. Prompt head: {prompt[:400]!r}"
        )
    return match.group("cmd")


def _run_real_resolver_from_composed_tokens(
    composed_cmd: str, *, ac_root: Path, target_ac: str
) -> list[str]:
    """Run the REAL fast_lane.py select_connected CLI using the argument
    TOKENS the JS workflow actually composed — preserving verbatim whether
    --exclude-structural-parent is present — but substituting the script
    path / --ac / --ac-root VALUES for ones this test can actually execute
    (the JS-composed values are worktree-relative and only exist inside a
    freshly-created fast-lane worktree).

    Returns the parsed JSON list of resolved AC ids.
    """
    tokens = shlex.split(composed_cmd)

    argv = [sys.executable, str(_REAL_FAST_LANE_PY), "select_connected"]
    if "--exclude-structural-parent" in tokens:
        argv.append("--exclude-structural-parent")
    argv += ["--ac", target_ac, "--ac-root", str(ac_root)]

    proc = subprocess.run(  # noqa: S603
        argv, capture_output=True, text=True, timeout=_SUBPROCESS_TIMEOUT
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"select_connected must exit 0. Got {proc.returncode}.\n"
            f"argv={argv}\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}\n"
            "composed command tokens (from fast-lane-ship.js): "
            f"{tokens}"
        )
    return json.loads(proc.stdout.strip())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFastLaneShipExcludeStructuralParent(unittest.TestCase):
    """BO-2600a-2-i: fast-lane-ship.js's select_connected invocation must
    pass --exclude-structural-parent so a leaf pointed at directly does not
    balloon into its structural parent's whole not-done subtree.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _build_fixture(self) -> None:
        """Build the fixture tree:

            BO-9500a  (L1) — covered_by: [BO-9500a-1, BO-9500a-2, BO-9500a-3]
              BO-9500a-1  (L2) — depends_on: [BO-9500a]  (own structural parent)
              BO-9500a-2  (L2) — no deps  (sibling — must NOT be pulled in)
              BO-9500a-3  (L2) — no deps  (sibling — must NOT be pulled in)

        Fixture invariant: derive_parent_id("BO-9500a-1") == "BO-9500a".
        """
        assert derive_parent_id("BO-9500a-1") == "BO-9500a", (
            "Fixture invariant: 'BO-9500a' must be the structural parent of "
            "'BO-9500a-1' — ensure the fixture IDs are correct."
        )

        _write_ac(
            self.ac_root,
            "BO-9500a",
            level="L1",
            work_status="todo",
            covered_by=["BO-9500a-1", "BO-9500a-2", "BO-9500a-3"],
        )
        _write_ac(
            self.ac_root,
            "BO-9500a-1",
            level="L2",
            work_status="todo",
            depends_on=["BO-9500a"],
        )
        _write_ac(
            self.ac_root,
            "BO-9500a-2",
            level="L2",
            work_status="todo",
        )
        _write_ac(
            self.ac_root,
            "BO-9500a-3",
            level="L2",
            work_status="todo",
        )

    def test_ac1_fast_lane_resolved_set_excludes_structural_parent_subtree(self) -> None:
        # covers: BO-2600a-2-i
        """AC-1: pointing the fast lane at BO-9500a-1 does not balloon the
        build set into BO-9500a's whole not-done subtree.

        Drives the REAL fast-lane-ship.js control flow, extracts the token
        list its Resolve phase actually composed for select_connected, and
        re-runs those tokens against the REAL resolver on a fixture store.
        Asserts on the RESOLVED SET, never on the command text.

        DEFECT (red state today): fast-lane-ship.js's selectConnectedInvocation
        template literal (~line 306-307) omits --exclude-structural-parent, so
        the extracted tokens lack the flag, and the real resolver — run with
        those exact tokens — expands BO-9500a-1's structural parent (BO-9500a)
        into its full not-done subtree, pulling in BO-9500a-2 and BO-9500a-3.

        To make this green: add --exclude-structural-parent to the
        selectConnectedInvocation template literal in
        templates/workflows-js/fast-lane-ship.js.
        """
        self._build_fixture()

        composed_cmd = _extract_resolve_command("BO-9500a-1")
        resolved = _run_real_resolver_from_composed_tokens(
            composed_cmd, ac_root=self.ac_root, target_ac="BO-9500a-1"
        )

        self.assertIn(
            "BO-9500a-1",
            resolved,
            "Target leaf BO-9500a-1 must be in the resolved set — it enters "
            f"via the subtree union regardless of the flag. Got: {resolved}",
        )

        self.assertNotIn(
            "BO-9500a-2",
            resolved,
            "BO-9500a-2 must NOT be in the resolved set. The only path to it "
            "is via expanding BO-9500a (the structural parent dep of "
            "BO-9500a-1); fast-lane-ship.js's composed select_connected "
            "invocation must pass --exclude-structural-parent to suppress "
            f"that expansion. Resolved set: {resolved}",
        )

        self.assertNotIn(
            "BO-9500a-3",
            resolved,
            "BO-9500a-3 must NOT be in the resolved set (same reasoning as "
            f"BO-9500a-2 — this is the reported '1 AC resolves to 15' symptom). "
            f"Resolved set: {resolved}",
        )

    def test_dropping_the_flag_reproduces_the_ballooned_set(self) -> None:
        # covers: BO-2600a-2-i
        """Negative control (per BO-2600a-2-i's test_spec): the SAME fixture,
        resolved by the REAL resolver directly WITHOUT
        --exclude-structural-parent, returns a STRICTLY LARGER set that
        includes BO-9500a's other children.

        This pins the size difference in the positive test above to the flag
        itself: without this control, a positive-test implementation that
        returns a small set for an unrelated reason (empty store, load
        failure) would appear to satisfy the AC.

        Expected to PASS immediately: --exclude-structural-parent's underlying
        capability (resolve_connected_build_set / the select_connected CLI
        flag) was already implemented and tested by BO-2600a-1 and BO-2600a-2
        (both work_status: done) — only the fast-lane-ship.js CALLER is
        missing it, which is what the positive test above exercises.
        """
        self._build_fixture()

        argv = [
            sys.executable,
            str(_REAL_FAST_LANE_PY),
            "select_connected",
            "--ac", "BO-9500a-1",
            "--ac-root", str(self.ac_root),
        ]
        proc = subprocess.run(  # noqa: S603
            argv, capture_output=True, text=True, timeout=_SUBPROCESS_TIMEOUT
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"select_connected (no flag) must exit 0. Got {proc.returncode}.\n"
            f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}",
        )
        resolved_without_flag = json.loads(proc.stdout.strip())

        self.assertIn(
            "BO-9500a-2",
            resolved_without_flag,
            "Without --exclude-structural-parent, BO-9500a (the structural "
            "parent dep of BO-9500a-1) IS expanded into its leaves, so "
            f"BO-9500a-2 must be present. Got: {resolved_without_flag}",
        )
        self.assertIn(
            "BO-9500a-3",
            resolved_without_flag,
            "Without --exclude-structural-parent, BO-9500a-3 must also be "
            f"present (same expansion as BO-9500a-2). Got: {resolved_without_flag}",
        )

        # Strictly larger than the flagged (correct) resolution: {BO-9500a-1}
        # plus at least the two siblings pulled in by the unflagged expansion.
        self.assertGreater(
            len(resolved_without_flag),
            1,
            "The unflagged resolution must be STRICTLY LARGER than the "
            "single-target set {'BO-9500a-1'} the flagged resolution "
            f"produces. Got: {resolved_without_flag}",
        )


if __name__ == "__main__":
    unittest.main()
