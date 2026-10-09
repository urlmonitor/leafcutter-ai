"""
MODULE: test_bp_100k_3_ii
GOAL: BP-100k-3-ii -- the remedy a drift gate names for an artifact it could not
    compare must be one that, carried out, clears the report. For a file no
    build run can produce, the remedy is NOT "run build.py"; it is declaring the
    file exempt on a stated ground, or removing it. For a file the build really
    does produce and has merely not recorded, the remedy stays "run build.py".
BUSINESS CONTEXT: Both gates today print ``UNCOMPARABLE: GAP <key> action=run
    build.py to register it`` for every unrecorded file. For a lockfile the
    tooling writes, a machine-local settings file, or a project's own config,
    running the build changes nothing, so the reader gets the same message back
    and concludes the gate is broken.
ARCHITECTURE: Every verdict is taken by executing the DEPLOYED check_output_drift.py
    as a subprocess over a synthesized tree of real files on disk, then CARRYING
    OUT the named remedy and running the gate AGAIN as a separate process. No
    verdict reads gate source or inspects a message for "better wording" alone.
    The "build" remedy is carried out by recording the file in the manifest with
    its real hash (exactly what a build run does); the "exempt" remedy is carried
    out through the real, documented drift_gate_exemption_registry in the
    deployed commit_guardian.json; the "remove" remedy deletes the file.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from . import _bp_100k_3_iii_harness as h

GAP_LINE_RE = re.compile(r"UNCOMPARABLE: GAP (\S+) action=(.*)")
RESULT_RE = re.compile(
    r"check-output-drift:\s*RESULT\s+verified=(\d+)\s+uncomparable=(\d+)\s+"
    r"exempt=(\d+)\s+gaps=(\d+)"
)

ANCHOR_ROOT = ".claude/anchor_root.md"
ANCHOR_AGENT = ".claude/agents/anchor_agent.md"
# A file the build genuinely produces (an agent deployed from a template) that
# has merely not been recorded in the manifest.
BUILDABLE = ".claude/agents/zz_new_buildable_agent_9c1.md"
# Files no build run can produce. One uses a name nobody would hardcode.
# (not .claude/scheduled_tasks.lock: the real registry already exempts that one.)
LOCKFILE = ".claude/zz_tool_session_5a2.lock"
NOVEL = ".claude/zz_novel_runtime_state_7f3.bin"

LOCKFILE_BYTES = b"pid=4242 written by the tool while running\n"
NOVEL_BYTES = b"\x00\x01novel runtime state\n"
BUILDABLE_BYTES = b"# agent the build deploys from a template\n"

GROUND = "Written by the tooling itself while running; no build phase produces it."


def _gaps(output: str) -> dict[str, str]:
    """Map each reported GAP key to the remedy text the gate attached to it."""
    return {m.group(1): m.group(2).strip() for m in GAP_LINE_RE.finditer(output)}


def _result(output: str) -> tuple[int, int, int, int]:
    """Return (verified, uncomparable, exempt, gaps) from the RESULT line."""
    m = RESULT_RE.search(output)
    assert m is not None, f"gate emitted no RESULT line:\n{output}"
    return tuple(int(g) for g in m.groups())  # type: ignore[return-value]


def _prescribes_build(remedy: str) -> bool:
    """True when the remedy names running the build as the thing to do."""
    return bool(re.search(r"\b(run|re-?run|rebuild|execute)\b[^.;]*build", remedy, re.I))


def _build_tree(workspace: Path, runtime_files: dict[str, bytes], with_buildable: bool) -> Path:
    """Synthesize a worked-in tree and return the deployed gate path.

    Two anchors are recorded in the manifest (matching hashes) so that
    ``.claude/`` and ``.claude/agents/`` are scanned by construction. Template
    counterparts are written for every build-produced file. ``runtime_files``
    are written to disk but have no template and no manifest record.
    """
    pkg = workspace / "leafcutter-ai"
    (pkg / "templates" / "scripts" / "commit_guardian").mkdir(parents=True)
    mappings: dict[str, dict] = {}
    anchors = {ANCHOR_ROOT: b"# root anchor\n", ANCHOR_AGENT: b"# agent anchor\n"}
    for rel, content in anchors.items():
        h.write_file(workspace / rel, content)
        tmpl = "templates/" + rel.removeprefix(".claude/")
        h.write_file(pkg / tmpl, content)
        mappings[rel] = {"template": tmpl, "expected_output_hash": h.sha256_bytes(content)}
    if with_buildable:
        h.write_file(workspace / BUILDABLE, BUILDABLE_BYTES)
        h.write_file(pkg / "templates" / "agents" / Path(BUILDABLE).name, BUILDABLE_BYTES)
    for rel, content in runtime_files.items():
        h.write_file(workspace / rel, content)
    _write_manifest(workspace, mappings)
    deployed = workspace / ".leafcutter" / "scripts" / "commit_guardian"
    shutil.copytree(h.CG_TEMPLATES_SRC, deployed, ignore=shutil.ignore_patterns("__pycache__"))
    return deployed / "check_output_drift.py"


def _write_manifest(workspace: Path, mappings: dict[str, dict]) -> None:
    """Write the manifest through the real JSON serializer."""
    manifest = {"output_mappings": mappings, "package_root": "leafcutter-ai"}
    (workspace / ".build_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _read_mappings(workspace: Path) -> dict[str, dict]:
    """Read output_mappings back from the manifest on disk."""
    data = json.loads((workspace / ".build_manifest.json").read_text(encoding="utf-8"))
    return data["output_mappings"]


def _carry_out_build_remedy(workspace: Path, key: str, content: bytes) -> None:
    """Do what a build run does for a build-produced file: record it with its hash."""
    mappings = _read_mappings(workspace)
    mappings[key] = {
        "template": "templates/agents/" + Path(key).name,
        "expected_output_hash": h.sha256_bytes(content),
    }
    _write_manifest(workspace, mappings)


def _carry_out_exempt_remedy(hook: Path, key: str, ground: str) -> None:
    """Declare *key* exempt through the real registry in the deployed guardian config."""
    cfg_path = hook.parent / "commit_guardian.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg.setdefault("drift_gate_exemption_registry", []).append({"path": key, "ground": ground})
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")


class TestBp100k3ii(unittest.TestCase):
    """Behavioural proof, by carrying remedies out, of BP-100k-3-ii."""

    def _workspace(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def test_unbuildable_file_remedy_is_not_run_the_build(self):
        # covers: BP-100k-3-ii
        # angle: criterion
        """AC: for a file no build can produce, the named remedy is not to run the build."""
        ws = self._workspace()
        hook = _build_tree(ws, {LOCKFILE: LOCKFILE_BYTES, NOVEL: NOVEL_BYTES}, True)
        proc = h.run_gate_with_real_registry(hook, ws)
        out = proc.stdout + proc.stderr
        gaps = _gaps(out)
        # Non-vacuity: the uncomparable set is exactly these three files.
        self.assertEqual(set(gaps), {LOCKFILE, NOVEL, BUILDABLE}, out)
        self.assertEqual(_result(out)[3], 3, out)
        self.assertNotEqual(proc.returncode, 0, out)
        for key in (LOCKFILE, NOVEL):
            remedy = gaps[key]
            self.assertFalse(_prescribes_build(remedy), f"{key}: {remedy}")
            self.assertRegex(remedy, r"(?i)exempt", f"{key}: {remedy}")
            self.assertRegex(remedy, r"(?i)remov|delet", f"{key}: {remedy}")
            self.assertRegex(remedy, r"(?i)not .*(produc|build)", f"{key}: {remedy}")

    def test_exempt_remedy_carried_out_clears_the_file(self):
        # covers: BP-100k-3-ii
        # angle: reachability
        """AC: declaring exempt as the gate names, then re-running, changes report and outcome."""
        ws = self._workspace()
        hook = _build_tree(ws, {LOCKFILE: LOCKFILE_BYTES, NOVEL: NOVEL_BYTES}, False)
        first = h.run_gate_with_real_registry(hook, ws)
        out1 = first.stdout + first.stderr
        self.assertEqual(set(_gaps(out1)), {LOCKFILE, NOVEL}, out1)
        self.assertNotEqual(first.returncode, 0, out1)
        self.assertRegex(_gaps(out1)[LOCKFILE], r"(?i)exempt", out1)

        for key in (LOCKFILE, NOVEL):
            _carry_out_exempt_remedy(hook, key, GROUND)
        second = h.run_gate_with_real_registry(hook, ws)  # separate run
        out2 = second.stdout + second.stderr
        self.assertEqual(_gaps(out2), {}, out2)
        for key in (LOCKFILE, NOVEL):
            self.assertEqual(h.extract_exempt_ground(out2, key), GROUND, out2)
        verified, uncomparable, exempt, gaps = _result(out2)
        self.assertEqual((exempt, gaps), (2, 0), out2)
        self.assertEqual(second.returncode, 0, out2)

    def test_remove_remedy_carried_out_clears_the_file(self):
        # covers: BP-100k-3-ii
        # angle: failure
        """AC: removing the file as the gate names makes the gate stop reporting it."""
        ws = self._workspace()
        hook = _build_tree(ws, {LOCKFILE: LOCKFILE_BYTES}, False)
        first = h.run_gate_with_real_registry(hook, ws)
        out1 = first.stdout + first.stderr
        self.assertEqual(set(_gaps(out1)), {LOCKFILE}, out1)
        self.assertRegex(_gaps(out1)[LOCKFILE], r"(?i)remov|delet", out1)
        self.assertNotEqual(first.returncode, 0, out1)

        (ws / LOCKFILE).unlink()
        second = h.run_gate_with_real_registry(hook, ws)
        out2 = second.stdout + second.stderr
        self.assertNotIn(LOCKFILE, out2)
        self.assertEqual(_result(out2)[3], 0, out2)
        self.assertEqual(second.returncode, 0, out2)

    def test_buildable_file_still_told_to_build_and_build_clears_only_it(self):
        # covers: BP-100k-3-ii
        # angle: discrimination
        """AC: same tree, same session -- build-produced file keeps the build remedy;
        carrying it out clears that file only; the runtime file keeps its non-build advice.

        Wrong versions caught: a gate that stopped prescribing the build for everyone;
        a gate that says exempt/remove for everyone; a gate that special-cases a
        hardcoded filename (the novel-named runtime file defeats that).
        """
        ws = self._workspace()
        hook = _build_tree(ws, {LOCKFILE: LOCKFILE_BYTES, NOVEL: NOVEL_BYTES}, True)
        first = h.run_gate_with_real_registry(hook, ws)
        out1 = first.stdout + first.stderr
        gaps1 = _gaps(out1)
        self.assertEqual(set(gaps1), {BUILDABLE, LOCKFILE, NOVEL}, out1)
        self.assertTrue(_prescribes_build(gaps1[BUILDABLE]), gaps1[BUILDABLE])
        for key in (LOCKFILE, NOVEL):
            self.assertFalse(_prescribes_build(gaps1[key]), gaps1[key])
        verified1 = _result(out1)[0]

        _carry_out_build_remedy(ws, BUILDABLE, BUILDABLE_BYTES)
        second = h.run_gate_with_real_registry(hook, ws)  # separate run
        out2 = second.stdout + second.stderr
        gaps2 = _gaps(out2)
        self.assertEqual(set(gaps2), {LOCKFILE, NOVEL}, out2)
        self.assertEqual(_result(out2)[0], verified1 + 1, out2)
        for key in (LOCKFILE, NOVEL):
            self.assertFalse(_prescribes_build(gaps2[key]), gaps2[key])
        self.assertNotEqual(second.returncode, 0, out2)


if __name__ == "__main__":
    unittest.main()
