"""AR-400d-4 -- the how-to for supplying a project ability is falsifiable against a real run (TDD red
phase: the how-to does not exist yet).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400d-4.yaml.
The guide is FOUND by content (a file under docs/how-to/ that documents ``provided_by`` and
``.leafcutter/skills``), then its own fenced blocks are executed against a scratch consumer project
that holds the REAL package at ``<project>/leafcutter-ai`` (sql-coder grants postgres / sql-test
``provided_by: project``, project area empty):

  * fenced blocks tagged ``bash`` / ``sh`` / ``shell`` are COMMANDS, run in order with cwd = the
    project (``python`` / ``python3`` is the test interpreter); every command must exit 0;
  * the FIRST fenced block tagged ``text`` / ``output`` is the build output line(s) the adopter
    sees BEFORE adding the ability.

Contract for the guide's author: write the steps so they run unattended from the project root
(create the ability with commands, e.g. ``mkdir`` + ``cp``/``printf`` of a SKILL.md written inline),
name the build as ``python leafcutter-ai/scripts/build.py --target-dir .``, and quote the lines
copied from a real run.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "prompt_assembly"))

import _ar400_3a_fixtures as F  # noqa: E402
import _ar400_3b_fixtures as G  # noqa: E402

HOWTO_DIR = F.REPO_ROOT / "docs" / "how-to"
BLOCK_RE = re.compile(r"^```(\w*)\n(.*?)^```", re.DOTALL | re.MULTILINE)
COMMAND_LANGS = {"bash", "sh", "shell"}
OUTPUT_LANGS = {"text", "output"}


def find_howto() -> Path | None:
    hits = [p for p in sorted(HOWTO_DIR.rglob("*.md"))
            if "provided_by" in (t := p.read_text(encoding="utf-8")) and ".leafcutter/skills" in t]
    return hits[0] if hits else None


def parse_blocks(path: Path) -> list[tuple[str, str]]:
    return [(m.group(1).lower(), m.group(2)) for m in BLOCK_RE.finditer(path.read_text(encoding="utf-8"))]


def consumer_with_real_package() -> G.Scenario:
    sc = G.fresh("real_empty")
    renamed = sc.project / "leafcutter-ai"
    sc.root.rename(renamed)
    return G.Scenario(root=renamed, project=sc.project)


def commands_of(blocks: list[tuple[str, str]]) -> list[list[str]]:
    cmds = []
    for lang, body in blocks:
        if lang not in COMMAND_LANGS:
            continue
        for raw in body.splitlines():
            line = raw.strip().removeprefix("$ ").strip()
            if line and not line.startswith("#"):
                cmds.append(shlex.split(line))
    return cmds


def run_command(cmd: list[str], project: Path) -> tuple[int, str]:
    argv = [sys.executable, *cmd[1:]] if cmd[0] in ("python", "python3") else cmd
    cp = subprocess.run(argv, cwd=str(project), capture_output=True, text=True, timeout=G.BUILD_TIMEOUT, check=False)
    return cp.returncode, cp.stdout + "\n" + cp.stderr


def is_build(cmd: list[str]) -> bool:
    return any(part.endswith("build.py") for part in cmd)


class TestHowToIsFalsifiable(unittest.TestCase):
    def test_project_ability_howto_commands_reproduce_stated_output(self):
        # covers: AR-400d-4
        # angle: real_artifact
        # must_catch: the guide's quoted output line differs from what the build prints
        """Run the guide's commands against a scratch consumer in order: each quoted 'before' line
        appears in the FIRST build's output and is absent from the LAST build (after the ability was
        added by the guide's own steps)."""
        guide = find_howto()
        self.assertIsNotNone(guide, "no how-to under docs/how-to/ documents provided_by and .leafcutter/skills")
        blocks = parse_blocks(guide)
        first_block = next((b for lang, b in blocks if lang in OUTPUT_LANGS), "")
        before = [ln.strip() for ln in first_block.splitlines() if ln.strip()]
        self.assertTrue(before, "the guide quotes no build output line to expect before the ability is added")
        cmds = commands_of(blocks)
        self.assertGreaterEqual(sum(map(is_build, cmds)), 2, "the guide must show a build before AND after adding the ability")
        sc = consumer_with_real_package()
        builds = []
        for cmd in cmds:
            rc, out = run_command(cmd, sc.project)
            self.assertEqual(rc, 0, f"guide command {cmd} failed: {out[-800:]}")
            if is_build(cmd):
                builds.append(out)
        for line in before:
            self.assertIn(line, builds[0], "a quoted 'before' line is not what the first build prints")
            self.assertNotIn(line, builds[-1], "a quoted 'before' line survives after the ability was added")

    def test_project_ability_howto_survival_claim_holds_under_clean_build(self):
        # covers: AR-400d-4
        # angle: real_artifact
        """Following the guide's steps, run a --clean build on the scratch consumer; every non-packaged
        ability the steps created under .leafcutter/skills is still present and byte-identical."""
        guide = find_howto()
        self.assertIsNotNone(guide, "no how-to under docs/how-to/ documents provided_by and .leafcutter/skills")
        cmds = commands_of(parse_blocks(guide))
        builds = [c for c in cmds if is_build(c)]
        self.assertTrue(builds, "the guide shows no build command")
        sc = consumer_with_real_package()
        for cmd in cmds:
            rc, out = run_command(cmd, sc.project)
            self.assertEqual(rc, 0, f"guide command {cmd} failed: {out[-800:]}")
        packaged = {d.name for d in (sc.root / "templates" / "skills").iterdir() if d.is_dir()}
        area = sc.project / ".leafcutter" / "skills"
        mine = {p: p.read_bytes() for d in area.iterdir() if d.is_dir() and d.name not in packaged
                for p in d.rglob("*") if p.is_file()}
        self.assertTrue(mine, "the guide's steps created no project ability under .leafcutter/skills")
        rc, out = run_command([*builds[-1], "--clean"], sc.project)
        self.assertEqual(rc, 0, out[-800:])
        for path, content in mine.items():
            self.assertTrue(path.is_file() and path.read_bytes() == content, f"--clean removed or changed {path}")


if __name__ == "__main__":
    unittest.main()
