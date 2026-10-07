"""
Tests for TQ-600a-9-i -- "A shared preparation is never handed to a test
that writes to it, and never makes an assertion true by construction."

Source of truth: docs/acceptance-criteria/testing-quality/
TQ-600-suite-feedback-latency/TQ-600a-9-i.yaml (test_spec + test_rationale +
it_requirements). Where the ticket's derived ``## Test Requirements`` table
differs from the YAML, the YAML wins.

See ``_test_helpers_tq_600a_9.py``'s module docstring for the full ASSUMED
PRODUCTION CONTRACT. Tests 1-2 below use the WRITE group (the
consumer-install file's one test + four parametrised instances, each of
which mutates its own surface file after a shared pre-mutation build).
Tests 3-5 use the READ-ONLY four-way collision group (this AC's own notes:
"If the discrimination holds there, it holds for the two-way and three-way
groups"), reusing TQ-600a-9's break-property plugin mechanism.

RED TODAY, UNIFORMLY, for the same reason as TQ-600a-9: no builder call
site emits `deploy_executed` yet, so every count-based assertion below
(asserted FIRST in every test) measures 0 against a non-zero expectation.

All tests suffixed ``_MANUAL`` -- each spawns one or more real
`python scripts/build.py` subprocesses via real child pytest sessions.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ._test_helpers_tq_600a_9 import (
    _COLLISION_GROUP_TESTS,
    COLLISION_GROUP_FILE,
    COLLISION_GROUP_KEXPR,
    break_env,
    count_events,
    run_child_session,
    run_plain_once,
    write_collision_break_plugin,
)

_CONSUMER_INSTALL_FILE = "unit_tests/portability/test_inf_400c_4_i.py"
_SURFACE_IDS = ("signoff", "product-owner", "business-analyst", "it-po")
_LEGACY_LITERAL_SENTENCE = "Append to `debugging/logs/agent_telemetry.jsonl`"


def _surface_relpath(surface_id: str) -> str:
    if surface_id == "signoff":
        return ".leafcutter/skills/signoff/SKILL.md"
    return f".leafcutter/agents/{surface_id}.md"


class TestTQ600a9iCopyOnWriteIsolation(unittest.TestCase):
    """RED test stubs for TQ-600a-9-i. See module docstring for the
    assumed production contract these tests are pinned to."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    # ------------------------------------------------------------------
    # Test 1 -- criterion (WRITE group)
    # ------------------------------------------------------------------
    def test_tq600a_9_i_a_member_that_writes_receives_its_own_copy_MANUAL(self):
        # covers: TQ-600a-9-i
        # angle: criterion
        """Run the consumer-install file's write group with a real
        `--basetemp` so the produced trees survive the child session, then
        assert a file NONE of the five members ever mutates
        (`config/knowledge_sink.json`) is byte-identical across every
        produced tree -- proof they all trace back to the one producer, not
        to five independent builds that merely happen to agree. Shares ONE
        real run with sibling tests (incl. TQ-600a-9's own consumer-install
        descriptor) via `run_plain_once` -- see
        `_test_helpers_tq_600a_9.py`'s COST CONTAINMENT note."""
        result, log_path, basetemp = run_plain_once(
            "consumer_install_whole", _CONSUMER_INSTALL_FILE
        )
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        count = count_events(log_path)
        self.assertEqual(
            1,
            count,
            msg=(
                f"expected exactly 1 real pre-mutation build shared across "
                f"the write group, measured {count} from the execution log."
            ),
        )
        project_dirs = sorted(basetemp.rglob("project"))
        self.assertGreaterEqual(
            len(project_dirs),
            5,
            msg=f"expected >= 5 produced project trees under {basetemp}, found {project_dirs}",
        )
        sink_relpath = ".leafcutter/config/knowledge_sink.json"
        contents = {
            d: (d / sink_relpath).read_bytes()
            for d in project_dirs
            if (d / sink_relpath).is_file()
        }
        self.assertEqual(
            len(contents),
            len(project_dirs),
            msg=f"not every produced tree carries {sink_relpath}: {project_dirs}",
        )
        distinct = set(contents.values())
        self.assertEqual(
            1,
            len(distinct),
            msg=(
                "the never-mutated knowledge_sink.json differs across the "
                f"produced trees -- they do not trace back to one shared "
                f"producer. Trees: {list(contents.keys())}"
            ),
        )

    # ------------------------------------------------------------------
    # Test 2 -- discrimination (WRITE group)
    # ------------------------------------------------------------------
    def test_tq600a_9_i_a_mutation_by_one_member_is_invisible_to_the_next(self):
        # covers: TQ-600a-9-i
        # angle: discrimination
        """Execute the write group with `--basetemp` retained, then for
        each surface id, assert exactly ONE produced tree carries that
        surface's reverted (mutated) text and every OTHER produced tree
        still carries the original, un-reverted text for that SAME surface
        file.

        must_catch (TQ-600a-9-i.yaml):
          - the writing member is handed the shared artifact itself
            instead of a copy of it.
          - the member is handed a copy made by reference/symlink rather
            than by content, so a write through it reaches the shared
            tree.

        RED TODAY: the group is not shared at all yet (5 independent
        builds), so `count_events` below measures 0, not 1, and the test
        fails before reaching the per-surface comparison. Shares the SAME
        cached run as test 1 above (and TQ-600a-9's own descriptor) via
        `run_plain_once` -- inspecting a shared artifact read-only does not
        require a fresh process.
        """
        result, log_path, basetemp = run_plain_once(
            "consumer_install_whole", _CONSUMER_INSTALL_FILE
        )
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        count = count_events(log_path)
        self.assertEqual(
            1,
            count,
            msg=f"expected exactly 1 shared pre-mutation build, measured {count}.",
        )
        project_dirs = sorted(basetemp.rglob("project"))
        for surface_id in _SURFACE_IDS:
            relpath = _surface_relpath(surface_id)
            reverted_trees = [
                d
                for d in project_dirs
                if (d / relpath).is_file()
                and _LEGACY_LITERAL_SENTENCE in (d / relpath).read_text(encoding="utf-8")
            ]
            self.assertEqual(
                1,
                len(reverted_trees),
                msg=(
                    f"[{surface_id}] expected exactly one produced tree to "
                    f"carry the reverted text for {relpath!r}, found "
                    f"{reverted_trees} -- either the mutation leaked into "
                    "another member's copy (shared, not copied) or it never "
                    "landed at all."
                ),
            )

    # ------------------------------------------------------------------
    # Test 3 -- criterion (READ-ONLY collision group, three arrangements)
    # ------------------------------------------------------------------
    def test_tq600a_9_i_the_group_reaches_the_same_verdicts_in_three_arrangements_MANUAL(
        self,
    ):
        # covers: TQ-600a-9-i
        # angle: criterion
        """Run the four-way collision group in declaration order, in
        reverse, and each member alone -- three SEPARATE child sessions,
        each producing its own preparation -- and assert the set of
        pass/fail verdicts is identical across all three. The forward
        arrangement reuses the same cached run as TQ-600a-9's own
        descriptor (declaration order IS the plain run); reverse and each
        member alone are each a genuinely fresh process, per this
        descriptor's own requirement.

        RED TODAY: a returncode-equality check alone is satisfied today
        regardless of this AC (sharing changes build COUNTS, never
        pass/fail) -- confirmed while authoring this build set, where
        exactly that gap let this descriptor pass before any
        implementation existed. The forward run's build count is therefore
        asserted FIRST, tying this test to the same change as its siblings.
        """
        names = list(_COLLISION_GROUP_TESTS.values())
        reversed_kexpr = " or ".join(reversed(names))
        forward, fwd_log, _ = run_plain_once(
            "collision_group", COLLISION_GROUP_FILE, extra_args=["-k", COLLISION_GROUP_KEXPR]
        )
        fwd_count = count_events(fwd_log)
        self.assertEqual(
            2, fwd_count, msg=f"expected exactly 2 real builds, measured {fwd_count}."
        )
        env_rev = break_env(self.tmp_path / "plugin_unused", self.tmp_path / "exec_log_rev.jsonl")
        reverse = run_child_session(
            COLLISION_GROUP_FILE, extra_args=["-k", reversed_kexpr], env_overrides=env_rev
        )
        self.assertEqual(
            forward.returncode,
            reverse.returncode,
            msg=(
                "forward and reverse arrangements of the same four-way "
                f"group disagree: forward rc={forward.returncode}, "
                f"reverse rc={reverse.returncode}.\nforward stdout:\n"
                f"{forward.stdout}\nreverse stdout:\n{reverse.stdout}"
            ),
        )
        for name in names:
            env_alone = break_env(
                self.tmp_path / "plugin_unused", self.tmp_path / f"exec_log_{name}.jsonl"
            )
            alone = run_child_session(
                COLLISION_GROUP_FILE, extra_args=["-k", name], env_overrides=env_alone
            )
            self.assertEqual(
                0,
                alone.returncode,
                msg=(
                    f"{name!r} run alone does not reach the same (passing) "
                    f"verdict it reaches as part of the group.\nstdout:\n"
                    f"{alone.stdout}"
                ),
            )

    # ------------------------------------------------------------------
    # Test 4 -- discrimination. THIS IS THE DESCRIPTOR THAT CANNOT BE
    # DROPPED (TQ-600a-9-i's own test_spec entry).
    # ------------------------------------------------------------------
    def test_tq600a_9_i_breaking_one_members_subject_reddens_only_that_member(
        self,
    ):
        # covers: TQ-600a-9-i
        # angle: discrimination
        """Four runs, one per member of the four-way group, each in its own
        child session and each breaking only that member's named property
        via the test-side break-property plugin. Exactly one member is red
        in each run.

        must_catch (TQ-600a-9-i.yaml):
          - breaking the planted adopter file leaves the survival member
            green (the shared preparation re-supplies it regardless).
          - breaking the collision message leaves the message member green.
          - breaking the declared winner leaves the declared-winner member
            green.
          - breaking the cross-platform winner leaves the cross-platform
            member green.
          - breaking any one subject reddens more than one member (the
            four runs shared a preparation instead of each producing their
            own).

        RED TODAY: the per-run build count (asserted first) is 0, not 2,
        for every one of the four break-runs -- sharing does not exist
        yet, so the per-property isolation check is unreached.

        NOTE: deliberately NOT using self.subTest() -- see TQ-600a-9's
        sibling test for why: a subTest failure can be reported by pytest
        as a separate "SUBFAILED" entry while the outer test's own plain
        node id is still read "passed" by this file's own mechanical
        red-baseline classifier, confirmed empirically while authoring
        this build set.
        """
        plugin_dir = self.tmp_path / "break_plugin"
        modname = write_collision_break_plugin(plugin_dir)
        for prop in ("survival", "message", "declared_winner", "cross_platform_winner"):
            log_path = self.tmp_path / f"exec_log_{prop}.jsonl"
            result = run_child_session(
                COLLISION_GROUP_FILE,
                extra_args=["-k", COLLISION_GROUP_KEXPR, "-p", modname],
                env_overrides=break_env(plugin_dir, log_path, break_property=prop),
            )
            count = count_events(log_path)
            self.assertEqual(
                2,
                count,
                msg=(
                    f"[{prop}] expected exactly 2 real builds even in a "
                    f"broken run (sharing scoped per OS process), "
                    f"measured {count}.\nstdout:\n{result.stdout}"
                ),
            )
            failed = [
                line[len("FAILED ") :].split(" ")[0]
                for line in result.stdout.splitlines()
                if line.startswith("FAILED ")
            ]
            self.assertEqual(
                1,
                len(failed),
                msg=(
                    f"[{prop}] expected exactly one member to go red, "
                    f"got {failed}.\nstdout:\n{result.stdout}"
                ),
            )

    # ------------------------------------------------------------------
    # Test 5 -- criterion (paired control)
    # ------------------------------------------------------------------
    def test_tq600a_9_i_a_sound_group_passes_whole_MANUAL(self):
        # covers: TQ-600a-9-i
        # angle: criterion
        """The paired control: with nothing broken, every member of the
        four-way group passes, and the shared build count is 2 -- without
        this, test 4's four red-demanding runs are satisfiable by a group
        that fails everything regardless of what is broken. Shares the same
        cached plain run as test 3's forward arrangement and TQ-600a-9's
        own descriptor."""
        result, log_path, _ = run_plain_once(
            "collision_group", COLLISION_GROUP_FILE, extra_args=["-k", COLLISION_GROUP_KEXPR]
        )
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        count = count_events(log_path)
        self.assertEqual(
            2,
            count,
            msg=f"expected exactly 2 real builds for the sound, unbroken group, measured {count}.",
        )


if __name__ == "__main__":
    unittest.main()
